# Copyright 2025 Google Inc.
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

import sqlalchemy as sa
import ibis.expr.datatypes as dt
from ibis.backends.base.sql.alchemy.registry import _cast as sa_fixed_cast


def sa_cast(t, op):
    # Add cast from numeric to string
    arg = op.arg
    typ = op.to
    arg_dtype = arg.output_dtype

    # Specialize going from numeric(p,s>0) to string
    if (
        arg_dtype.is_decimal()
        and arg_dtype.scale
        and arg_dtype.scale > 0
        and typ.is_string()
    ):
        # When casting a number to string MySQL includes the full scale, e.g.:
        #   SELECT CAST(CAST(100 AS DECIMAL(5,2)) AS CHAR);
        #     100.00
        # This doesn't match most engines which would return "100".
        # We've used a workaround from StackOverflow:
        #   https://stackoverflow.com/a/20111398
        return sa_fixed_cast(t, op) + sa.literal(0)

    # Follow the original Ibis code path.
    return sa_fixed_cast(t, op)


def strftime(translator, op):
    arg = op.arg
    format_string = op.format_str
    arg_formatted = translator.translate(arg)
    arg_type = arg.output_dtype
    fmt_string = translator.translate(format_string)
    if isinstance(arg_type, dt.Timestamp):
        fmt_string = "%Y-%m-%d %H:%i:%S"
    return sa.func.date_format(arg_formatted, fmt_string)


def sa_format_hashbytes(translator, op):
    arg = translator.translate(op.arg)
    hash_func = sa.func.sha2(arg, sa.sql.literal_column("'256'"))
    return hash_func


def to_hex(t, op):
    # Binary to string is a "to hex" conversion for DVT.
    sa_arg = t.translate(op.arg)
    return sa.func.lower(sa.func.hex(sa_arg))


def from_hex(t, op):
    # Binary to string is a "from hex" conversion for DVT.
    sa_arg = t.translate(op.arg)
    return sa.func.unhex(sa_arg)
