# Copyright 2023 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

from typing import Literal

import pandas
import warnings

import sqlalchemy as sa
from ibis.backends.base.sql.alchemy import BaseAlchemyBackend
from ibis.backends.mssql.compiler import MsSqlCompiler
from ibis.backends.mssql.datatypes import _type_from_result_set_info

import third_party.ibis.ibis_mssql.datatypes
import json


# The MSSQL backend uses the Ibis MSSQL compiler, but overrides
# the Backend class to use pyodbc instead of pymssql
class Backend(BaseAlchemyBackend):
    name = "mssql"
    compiler = MsSqlCompiler
    supports_create_or_replace = False
    LOCK_SQL = "WITH (ROWLOCK)"

    _sqlglot_dialect = "tsql"

    def do_connect(
        self,
        host: str = "localhost",
        user: str = None,
        password: str = None,
        port: int = 1433,
        database: str = None,
        url: str = None,
        driver: Literal["pyodbc"] = "pyodbc",
        odbc_driver: str = "ODBC Driver 17 for SQL Server",
        query: str = None,
    ) -> None:
        if url is None:
            if driver != "pyodbc":
                raise NotImplementedError(
                    "pyodbc is currently the only supported driver"
                )

            if query:
                query = json.loads(query)
            else:
                query = {"driver": odbc_driver}

            alchemy_url = sa.engine.url.URL.create(
                f"mssql+{driver}",
                host=host,
                port=port,
                username=user,
                password=password,
                database=database,
                query=query,
            )
        else:
            alchemy_url = sa.engine.url.make_url(url)

        self.database_name = alchemy_url.database
        engine = sa.create_engine(
            alchemy_url,
            poolclass=sa.pool.StaticPool,
            # Pessimistic disconnect handling
            pool_pre_ping=True,
        )

        @sa.event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cur:
                cur.execute("SET DATEFIRST 1")

        self.client = engine
        return super().do_connect(engine)

    def _metadata(self, query):
        if query in self.list_tables():
            query = f"SELECT * FROM [{query}]"

        query = sa.text("EXEC sp_describe_first_result_set @tsql = :query").bindparams(
            query=query
        )
        with self.begin() as bind:
            for column in bind.execute(query).mappings():
                yield column["name"], _type_from_result_set_info(column)

    def list_primary_key_columns(self, database: str, table: str) -> list:
        """Return a list of primary key column names."""
        list_pk_col_sql = """
            SELECT COL_NAME(ic.object_id, ic.column_id) AS column_name
            FROM sys.tables t
            INNER JOIN sys.indexes i ON (t.object_id = i.object_id)
            INNER JOIN sys.index_columns ic ON (i.object_id = ic.object_id AND i.index_id  = ic.index_id)
            INNER JOIN sys.schemas s ON (t.schema_id = s.schema_id)
            WHERE  s.name = ?
            AND    t.name = ?
            AND    i.is_primary_key = 1
            ORDER BY ic.column_id"""
        with self.begin() as con:
            result = con.exec_driver_sql(list_pk_col_sql, parameters=(database, table))
            return [_[0] for _ in result.cursor.fetchall()]

    LIST_DATABASE_SQL = """
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name LIKE '%{schema_like}%'
    """

    def list_databases(self, like=None):
        schema_like = like or ""

        list_database_sql = self.LIST_DATABASE_SQL.format(schema_like=schema_like)
        databases_df = self._execute(list_database_sql, results=True)

        return list(databases_df.schema_name.str.rstrip())

    LIST_TABLE_SQL = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema LIKE '%{schema_like}%'
        AND table_name LIKE '%{table_like}%'
        AND table_type LIKE '{type_like}'
    """

    def list_tables(self, like=None, schema=None, type_like: str = "%") -> list:
        schema = schema or ""
        table = like or ""

        list_table_sql = self.LIST_TABLE_SQL.format(
            schema_like=schema, table_like=table, type_like=type_like
        )
        tables_df = self._execute(list_table_sql, results=True)
        return list(tables_df.table_name.str.rstrip())

    def dvt_list_tables(self, like=None, database=None) -> list:
        """Duplicate of list_tables() but only returning tables in the output."""
        return self.list_tables(like=like, schema=database, type_like="BASE TABLE")

    def _execute(self, sql, results=False, params=None):
        import re

        def add_rowlock_to_select(sql):
            # Only add ROWLOCK to SELECTs from user tables, not system views
            # This regex matches: FROM [schema.]table (with optional alias)
            pattern = re.compile(
                r"(FROM\s+(\[?\w+\]?\.)?\[?\w+\]?)(\s+AS\s+\w+)?", re.IGNORECASE
            )
            # Do not add ROWLOCK to information_schema or sys tables
            if (
                "information_schema" in sql.lower()
                or "sys." in sql.lower()
                or "sysobjects" in sql.lower()
            ):
                return sql

            # Insert 'WITH (ROWLOCK)' after the table name
            def replacer(match):
                return f"{match.group(1)}{ self.LOCK_SQL}{match.group(3) or ''}"

            return pattern.sub(replacer, sql, count=1)

        if self.LOCK_SQL and sql.strip().upper().startswith("SELECT"):
            sql = add_rowlock_to_select(sql)

        with warnings.catch_warnings():
            # Suppress pandas warning of SQLAlchemy connectable DB support
            warnings.simplefilter("ignore")
            df = pandas.read_sql(sql, self.client, params=params)

        if results:
            return df

        return None
