# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The Ibis Addons Operations are intended to help facilitate new expressions
when required before they can be pushed upstream to Ibis.

Raw SQL Filters:
The ability to inject RawSQL into a query DNE in Ibis.  It must be built out
and applied to each Ibis Data Source directly as each has
extended its own registry.  Eventually this can potentially be pushed to
Ibis as an override, though it would not apply for Pandas and other
non-textual languages.
"""
import datetime
import dateutil
import numpy as np
import string

import google.cloud.bigquery as bq
import ibis
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.rules as rlz
import pandas as pd
import sqlalchemy as sa
from ibis.backends.base.sql.alchemy import BaseAlchemyBackend
from ibis.backends.base.sql.alchemy.registry import fixed_arity as sa_fixed_arity
from ibis.backends.base.sql.alchemy.translator import AlchemyExprTranslator
from ibis.backends.base.sql.compiler.translator import ExprTranslator
from ibis.backends.base.sql.registry import fixed_arity
from ibis.backends.bigquery.client import (
    _DTYPE_TO_IBIS_TYPE as _BQ_DTYPE_TO_IBIS_TYPE,
    _LEGACY_TO_STANDARD as _BQ_LEGACY_TO_STANDARD,
)
from ibis.backends.bigquery.compiler import BigQueryExprTranslator
from ibis.backends.bigquery.registry import bigquery_cast
from ibis.backends.impala.compiler import ImpalaExprTranslator
from ibis.backends.mssql.compiler import MsSqlExprTranslator
from ibis.backends.mysql.compiler import MySQLExprTranslator
from ibis.backends.pandas.dispatch import execute_node
from ibis.backends.pandas.execution.temporal import execute_epoch_seconds
from ibis.backends.postgres.compiler import PostgreSQLExprTranslator
from ibis.expr.types import BinaryValue, NumericValue, StringValue, TemporalValue

# Do not remove these lines, they trigger patching of Ibis code.
import third_party.ibis.ibis_bigquery.api  # noqa
from third_party.ibis.ibis_bigquery import registry as bigquery_registry
import third_party.ibis.ibis_mysql.compiler  # noqa
from third_party.ibis.ibis_impala import registry as impala_registry
from third_party.ibis.ibis_mssql import registry as mssql_registry
from third_party.ibis.ibis_mysql import registry as mysql_registry
from third_party.ibis.ibis_postgres import registry as postgres_registry
import third_party.ibis.ibis_postgres.client  # noqa

from third_party.ibis.ibis_cloud_spanner.compiler import SpannerExprTranslator
from third_party.ibis.ibis_redshift.compiler import RedShiftExprTranslator

# DB2 requires ibm_db_dbi
try:
    from third_party.ibis.ibis_db2.compiler import Db2ExprTranslator
    from third_party.ibis.ibis_db2 import registry as db2_registry
except Exception:
    Db2ExprTranslator = None

# Oracle requires oracledb
try:
    from third_party.ibis.ibis_oracle.compiler import OracleExprTranslator
    from third_party.ibis.ibis_oracle import registry as oracle_registry
except Exception:
    OracleExprTranslator = None

# TD requires teradatasql
try:
    from third_party.ibis.ibis_teradata.compiler import TeradataExprTranslator
    from third_party.ibis.ibis_teradata import registry as teradata_registry
except Exception:
    TeradataExprTranslator = None

# Snowflake requires snowflake-connector-python and snowflake-sqlalchemy
try:
    from ibis.backends.snowflake import SnowflakeExprTranslator
    from third_party.ibis.ibis_snowflake import registry as snowflake_registry
except Exception:
    SnowflakeExprTranslator = None


# Cast of datetime64 NaT to int64 and then in seconds results in the value below.
# We need to use this value in the datetime.date simulation of the datetime64 behaviour.
NAT_INT64_MIN_IN_SECONDS = np.iinfo(np.int64).min // 1_000_000_000


class BinaryLength(ops.Value):
    arg = rlz.one_of([rlz.value(dt.Binary)])
    output_dtype = dt.int32
    output_shape = rlz.shape_like("arg")


class PaddedCharLength(ops.Value):
    arg = rlz.one_of([rlz.value(dt.String)])
    output_dtype = dt.int32
    output_shape = rlz.shape_like("arg")


class ToChar(ops.Value):
    arg = rlz.one_of(
        [
            rlz.value(dt.Decimal),
            rlz.value(dt.float64),
            rlz.value(dt.Date),
            rlz.value(dt.Time),
            rlz.value(dt.Timestamp),
        ]
    )
    fmt = rlz.string
    output_type = rlz.shape_like("arg")


class ToHex(ops.Value):
    arg = rlz.one_of([rlz.value(dt.Binary)])
    output_dtype = dt.String
    output_shape = rlz.shape_like("arg")


class FromHex(ops.Value):
    arg = rlz.one_of([rlz.value(dt.String)])
    output_dtype = dt.Binary
    output_shape = rlz.shape_like("arg")


class RawSQL(ops.Comparison):
    pass


def compile_binary_length(binary_value):
    return BinaryLength(binary_value).to_expr()


def compile_padded_char_length(char_value):
    return PaddedCharLength(char_value).to_expr()


def compile_to_char(numeric_value, fmt):
    return ToChar(numeric_value, fmt=fmt).to_expr()


def compile_to_hex(binary_value):
    return ToHex(binary_value).to_expr()


def compile_from_hex(string_value):
    return FromHex(string_value).to_expr()


@bigquery_cast.register(str, dt.Binary, dt.String)
def bigquery_cast_from_binary_generate(compiled_arg, from_, to):
    """Cast of binary to string should be hex conversion."""
    return f"TO_HEX({compiled_arg})"


@bigquery_cast.register(str, dt.String, dt.Binary)
def bigquery_cast_to_binary_generate(compiled_arg, from_, to):
    """Cast of binary to string should be hex conversion."""
    return f"FROM_HEX({compiled_arg})"


def format_hashbytes_alchemy(translator, op):
    arg = translator.translate(op.arg)
    if op.how == "sha256":
        return f"sha2({arg}, 256)"
    elif op.how == "md5":
        return f"md5({arg})"
    else:
        raise ValueError(f"unexpected value for 'how': {op.how}")


def format_hashbytes_base(translator, op):
    arg = translator.translate(op.arg)
    return f"sha2({arg}, 256)"


def compile_raw_sql(table, sql):
    op = RawSQL(table[table.columns[0]].cast(dt.string), ibis.literal(sql))
    return op.to_expr()


def format_raw_sql(translator, op):
    rand_col, raw_sql = op.args
    return raw_sql.args[0]


def sa_format_raw_sql(translator, op):
    rand_col, raw_sql = op.args
    return sa.text(raw_sql.args[0])


def sa_format_hashbytes_redshift(translator, op):
    arg = translator.translate(op.arg)
    return sa.sql.literal_column(f"sha2({arg}, 256)")


def sa_format_to_char(translator, op):
    arg = translator.translate(op.arg)
    fmt = translator.translate(op.fmt)
    return sa.func.to_char(arg, fmt)


def sa_format_binary_length(translator, op):
    arg = translator.translate(op.arg)
    return sa.func.length(arg)


def sa_format_random(t, op):
    return sa.func.RANDOM()


_BQ_DTYPE_TO_IBIS_TYPE["TIMESTAMP"] = dt.Timestamp(timezone="UTC")


@dt.dtype.register(bq.schema.SchemaField)
def _bigquery_field_to_ibis_dtype(field):
    """Convert BigQuery `field` to an ibis type.
    Taken from ibis.backends.bigquery.client.py for issue:
        https://github.com/GoogleCloudPlatform/professional-services-data-validator/issues/926
    """
    typ = field.field_type
    if typ == "RECORD":
        fields = field.fields
        assert fields, "RECORD fields are empty"
        names = [el.name for el in fields]
        ibis_types = list(map(dt.dtype, fields))
        ibis_type = dt.Struct(dict(zip(names, ibis_types)))
    elif typ == "NUMERIC":
        if not field.precision and not field.scale:
            return dt.Decimal(precision=38, scale=9, nullable=field.is_nullable)
        return dt.Decimal(
            precision=field.precision,
            scale=field.scale or 0,
            nullable=field.is_nullable,
        )
    elif typ == "BIGNUMERIC":
        if not field.precision and not field.scale:
            return dt.Decimal(precision=76, scale=38, nullable=field.is_nullable)
        return dt.Decimal(
            precision=field.precision,
            scale=field.scale or 0,
            nullable=field.is_nullable,
        )
    else:
        ibis_type = _BQ_LEGACY_TO_STANDARD.get(typ, typ)
        if ibis_type in _BQ_DTYPE_TO_IBIS_TYPE:
            ibis_type = _BQ_DTYPE_TO_IBIS_TYPE[ibis_type](nullable=field.is_nullable)
        else:
            ibis_type = ibis_type
    if field.mode == "REPEATED":
        ibis_type = dt.Array(ibis_type)
    return ibis_type


def string_to_epoch(ts: str) -> int:
    """Function to convert string timestamp to epoch seconds"""
    try:
        if pd.isna(ts):
            # Casting datetime64 to int64 uses the minimum possible int64 when it
            # encounters NaT. Simulating the same here for when auto cast fails.
            return NAT_INT64_MIN_IN_SECONDS
        parsed_ts = dateutil.parser.isoparse(ts).astimezone(dateutil.tz.UTC)
        return (
            parsed_ts - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        ).total_seconds()
    except (ValueError, OSError):
        # Support DATE '0001-01-01' which throws error when converted to UTC
        # Catching OSError above because all dates prior to 1970 fail in astimezone on Windows.
        parsed_ts = dateutil.parser.isoparse(ts)
        return (parsed_ts - datetime.datetime(1970, 1, 1)).total_seconds()


@execute_node.register(ops.ExtractEpochSeconds, (datetime.datetime, pd.Series))
def execute_epoch_seconds_new(op, data, **kwargs):
    convert = getattr(data, "view", data.astype)
    try:
        series = convert(np.int64)
        # We need int64 below because NaT overflows int32.
        return (series // 1_000_000_000).astype(np.int64)
    except TypeError:
        # Catch 'TypeError' for large timestamps beyond max datetime64[ns] as per Issue #1053
        # Cast to string instead to work around datetime64[ns] limitation
        series = data.astype("string")
        epoch_series = series.map(string_to_epoch)
        return epoch_series


def _dvt_list_tables(self, like=None, database=None) -> list:
    """Alternative to BaseAlchemyBackend.list_tables that does not include views in the result."""
    tables = self.inspector.get_table_names(schema=database)
    return self._filter_with_like(tables, like)


def _sa_whitespace_rstrip(t, op):
    sa_arg = t.translate(op.arg)
    return sa.func.rtrim(sa_arg, string.whitespace)


execute_epoch_seconds = execute_epoch_seconds_new

BinaryValue.byte_length = compile_binary_length
BinaryValue.to_hex = compile_to_hex

StringValue.padded_char_length = compile_padded_char_length
StringValue.from_hex = compile_from_hex

NumericValue.to_char = compile_to_char
TemporalValue.to_char = compile_to_char

# This is an additional DVT only method. We tag this onto BaseAlchemyBackend
# so we can piggy back Ibis code rather than writing metadata queries for all engines.
BaseAlchemyBackend.dvt_list_tables = _dvt_list_tables

BigQueryExprTranslator._registry[ops.HashBytes] = bigquery_registry.format_hashbytes
BigQueryExprTranslator._registry[RawSQL] = format_raw_sql
BigQueryExprTranslator._registry[ops.Strftime] = bigquery_registry.strftime
BigQueryExprTranslator._registry[BinaryLength] = sa_format_binary_length
BigQueryExprTranslator._registry[ToHex] = bigquery_registry.to_hex
BigQueryExprTranslator._registry[FromHex] = bigquery_registry.from_hex

AlchemyExprTranslator._registry[RawSQL] = format_raw_sql
AlchemyExprTranslator._registry[ops.HashBytes] = format_hashbytes_alchemy
AlchemyExprTranslator._registry[PaddedCharLength] = AlchemyExprTranslator._registry[
    ops.StringLength
]
ExprTranslator._registry[RawSQL] = format_raw_sql
ExprTranslator._registry[ops.HashBytes] = format_hashbytes_base
# Base length of padded string is the same as for a standard string.
ExprTranslator._registry[PaddedCharLength] = ExprTranslator._registry[ops.StringLength]

ImpalaExprTranslator._registry[ops.Cast] = impala_registry.sa_cast
ImpalaExprTranslator._registry[RawSQL] = format_raw_sql
ImpalaExprTranslator._registry[ops.HashBytes] = impala_registry.format_hashbytes
ImpalaExprTranslator._registry[ops.RandomScalar] = fixed_arity("RAND", 0)
ImpalaExprTranslator._registry[ops.Strftime] = impala_registry.strftime
ImpalaExprTranslator._registry[BinaryLength] = sa_format_binary_length
ImpalaExprTranslator._registry[ToHex] = impala_registry.to_hex
ImpalaExprTranslator._registry[FromHex] = impala_registry.from_hex

if OracleExprTranslator:
    OracleExprTranslator._registry[RawSQL] = sa_format_raw_sql
    OracleExprTranslator._registry[ops.HashBytes] = oracle_registry.sa_format_hashbytes
    OracleExprTranslator._registry[ToChar] = sa_format_to_char
    OracleExprTranslator._registry[BinaryLength] = (
        oracle_registry.sa_format_binary_length
    )
    OracleExprTranslator._registry[ops.RStrip] = _sa_whitespace_rstrip
    OracleExprTranslator._registry[PaddedCharLength] = OracleExprTranslator._registry[
        ops.StringLength
    ]
    OracleExprTranslator._registry[ToHex] = oracle_registry.to_hex
    OracleExprTranslator._registry[FromHex] = oracle_registry.from_hex

PostgreSQLExprTranslator._registry[ops.HashBytes] = (
    postgres_registry.sa_format_hashbytes
)
PostgreSQLExprTranslator._registry[RawSQL] = sa_format_raw_sql
PostgreSQLExprTranslator._registry[ToChar] = sa_format_to_char
PostgreSQLExprTranslator._registry[ops.Cast] = postgres_registry.sa_cast
PostgreSQLExprTranslator._registry[BinaryLength] = sa_format_binary_length
PostgreSQLExprTranslator._registry[ops.ExtractEpochSeconds] = (
    postgres_registry.sa_epoch_seconds
)
PostgreSQLExprTranslator._registry[PaddedCharLength] = (
    postgres_registry.sa_format_postgres_padded_char_length
)
PostgreSQLExprTranslator._registry[ToHex] = postgres_registry.to_hex
PostgreSQLExprTranslator._registry[FromHex] = postgres_registry.from_hex


MsSqlExprTranslator._registry[ops.HashBytes] = mssql_registry.sa_format_hashbytes
MsSqlExprTranslator._registry[RawSQL] = sa_format_raw_sql
MsSqlExprTranslator._registry[ops.IfNull] = sa_fixed_arity(sa.func.isnull, 2)
MsSqlExprTranslator._registry[ops.StringJoin] = mssql_registry.sa_string_join
MsSqlExprTranslator._registry[ops.RandomScalar] = mssql_registry.sa_format_new_id
MsSqlExprTranslator._registry[ops.Strftime] = mssql_registry.strftime
MsSqlExprTranslator._registry[ops.Cast] = mssql_registry.sa_cast_mssql
MsSqlExprTranslator._registry[BinaryLength] = mssql_registry.sa_format_binary_length
MsSqlExprTranslator._registry[ops.TableColumn] = mssql_registry.sa_table_column
MsSqlExprTranslator._registry[ops.ExtractEpochSeconds] = mssql_registry.sa_epoch_seconds
MsSqlExprTranslator._registry[ops.RStrip] = mssql_registry.sa_whitespace_rstrip
MsSqlExprTranslator._registry[PaddedCharLength] = MsSqlExprTranslator._registry[
    ops.StringLength
]
MsSqlExprTranslator._registry[ToHex] = mssql_registry.to_hex
MsSqlExprTranslator._registry[FromHex] = mssql_registry.from_hex

MySQLExprTranslator._registry[ops.Cast] = mysql_registry.sa_cast
MySQLExprTranslator._registry[RawSQL] = sa_format_raw_sql
MySQLExprTranslator._registry[ops.HashBytes] = mysql_registry.sa_format_hashbytes
MySQLExprTranslator._registry[ops.Strftime] = mysql_registry.strftime
MySQLExprTranslator._registry[BinaryLength] = sa_format_binary_length
MySQLExprTranslator._registry[ToHex] = mysql_registry.to_hex
MySQLExprTranslator._registry[FromHex] = mysql_registry.from_hex

RedShiftExprTranslator._registry[ops.HashBytes] = sa_format_hashbytes_redshift
RedShiftExprTranslator._registry[RawSQL] = sa_format_raw_sql
RedShiftExprTranslator._registry[BinaryLength] = sa_format_binary_length
RedShiftExprTranslator._registry[PaddedCharLength] = RedShiftExprTranslator._registry[
    ops.StringLength
]
RedShiftExprTranslator._registry[ToHex] = postgres_registry.to_hex
RedShiftExprTranslator._registry[FromHex] = postgres_registry.from_hex

if Db2ExprTranslator:
    Db2ExprTranslator._registry[ops.HashBytes] = db2_registry.sa_format_hashbytes
    Db2ExprTranslator._registry[RawSQL] = sa_format_raw_sql
    Db2ExprTranslator._registry[BinaryLength] = sa_format_binary_length
    Db2ExprTranslator._registry[ops.Strftime] = db2_registry.strftime
    Db2ExprTranslator._registry[ops.RStrip] = _sa_whitespace_rstrip
    Db2ExprTranslator._registry[PaddedCharLength] = Db2ExprTranslator._registry[
        ops.StringLength
    ]
    Db2ExprTranslator._registry[ToHex] = db2_registry.to_hex
    Db2ExprTranslator._registry[FromHex] = db2_registry.from_hex

SpannerExprTranslator._registry[RawSQL] = format_raw_sql
SpannerExprTranslator._registry[ops.HashBytes] = bigquery_registry.format_hashbytes
SpannerExprTranslator._registry[BinaryLength] = sa_format_binary_length
SpannerExprTranslator._registry[ToHex] = bigquery_registry.to_hex
SpannerExprTranslator._registry[FromHex] = bigquery_registry.from_hex

if TeradataExprTranslator:
    TeradataExprTranslator._registry[RawSQL] = format_raw_sql
    TeradataExprTranslator._registry[ops.HashBytes] = teradata_registry.format_hashbytes
    TeradataExprTranslator._registry[BinaryLength] = sa_format_binary_length
    TeradataExprTranslator._registry[PaddedCharLength] = (
        TeradataExprTranslator._registry[ops.StringLength]
    )
    TeradataExprTranslator._registry[ToHex] = teradata_registry.to_hex
    TeradataExprTranslator._registry[FromHex] = teradata_registry.from_hex

if SnowflakeExprTranslator:
    SnowflakeExprTranslator._registry[ops.Cast] = snowflake_registry.sa_cast
    SnowflakeExprTranslator._registry[ops.HashBytes] = (
        snowflake_registry.sa_format_hashbytes
    )
    SnowflakeExprTranslator._registry[RawSQL] = sa_format_raw_sql
    SnowflakeExprTranslator._registry[ops.IfNull] = sa_fixed_arity(sa.func.ifnull, 2)
    SnowflakeExprTranslator._registry[ops.ExtractEpochSeconds] = (
        snowflake_registry.sa_epoch_time
    )
    SnowflakeExprTranslator._registry[ops.RandomScalar] = sa_format_random
    SnowflakeExprTranslator._registry[BinaryLength] = sa_format_binary_length
    SnowflakeExprTranslator._registry[ops.RStrip] = _sa_whitespace_rstrip
    SnowflakeExprTranslator._registry[ToHex] = snowflake_registry.to_hex
    SnowflakeExprTranslator._registry[FromHex] = snowflake_registry.from_hex
