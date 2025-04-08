from sqlalchemy import sql
from sqlalchemy.sql import sqltypes
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.engine import reflection
from sqlalchemy.engine.default import DefaultDialect


PG_TYPE_MAP = {
    "int8": "bigint",
    "numeric": "numeric",
    "float4": "real",
    "float8": "double precision",
    "varchar": "character varying",
    "date": "date",
    "timestamptz": "timestamp with time zone",
}


class SpannerPostgresDialectMixin(DefaultDialect):
    """
    Define Spanner-PostgreSQL-specific behavior.

    Most public methods are overrides of the underlying interfaces defined in
    :class:`~sqlalchemy.engine.interfaces.Dialect` and
    :class:`~sqlalchemy.engine.Inspector`.
    """

    name = "spanner_postgres"

    def _format_type(self, pg_type_str, pg_type_mod) -> str:
        """In Spanner the format_type() UDF is not present, this method converts pg_type values to something "similar" to format_type() output."""
        type_str = PG_TYPE_MAP[pg_type_str]
        if pg_type_mod != -1:
            type_str = f"{type_str}({pg_type_mod})"
        return type_str

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        table_oid = self.get_table_oid(
            connection, table_name, schema, info_cache=kw.get("info_cache")
        )
        # Why has table_oid got single quotes inside it?
        SQL_COLS = """
            SELECT a.attname,
              t.typname, a.atttypmod,
              a.attnotnull
            FROM pg_catalog.pg_attribute a
            INNER JOIN pg_catalog.pg_type t ON (t.oid = a.atttypid)
            WHERE a.attrelid = :table_oid
            AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """
        # s = sql.text(f"SELECT * FROM {table_oid} t0 LIMIT 0")
        # c = connection.execute(s)
        s = sql.text(SQL_COLS).bindparams(
            sql.bindparam("table_oid", type_=sqltypes.Integer)
        )
        c = connection.execute(s, dict(table_oid=table_oid))
        rows = c.fetchall()
        breakpoint()
        columns = []
        for name, pg_type_str, pg_type_mod, notnull in rows:
            column_info = self._get_column_info(
                name,
                self._format_type(pg_type_str, pg_type_mod),
                None,  # default_,
                notnull,
                None,  # domains,
                None,  # enums,
                schema,
                None,  # comment,
                None,  # generated,
                None,  # identity,
            )
            columns.append(column_info)
        return columns

    @reflection.cache
    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        return []

    @reflection.cache
    def get_foreign_keys(
        self,
        connection,
        table_name,
        schema=None,
        postgresql_ignore_search_path=False,
        **kw,
    ):
        return []

    @reflection.cache
    def get_indexes(self, connection, table_name, schema, **kw):
        return []

    @reflection.cache
    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        return []


class SpannerPostgresDialect_psycopg2(SpannerPostgresDialectMixin, PGDialect_psycopg2):
    pass
