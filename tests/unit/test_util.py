# Copyright 2024 Google LLC
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

import logging
import pytest


@pytest.fixture
def module_under_test():
    from data_validation import util

    return util


def test_timed_call_fn_no_args(module_under_test, caplog):
    """Test timed_call works with no parameters."""
    caplog.set_level(logging.DEBUG)

    caplog.clear()

    def fn():
        return 1

    assert fn() == module_under_test.timed_call("Pure fn", fn)
    assert any(_ for _ in caplog.messages if "Pure fn" in _)


def test_timed_call_fn_args(module_under_test, caplog):
    """Test timed_call works with positional parameters."""
    caplog.set_level(logging.DEBUG)

    caplog.clear()

    def fn_args(a1: int, a2: int):
        return a1

    assert fn_args(1, 2) == module_under_test.timed_call("args fn", fn_args, 1, 2)
    assert any(_ for _ in caplog.messages if "args fn" in _)


def test_timed_call_fn_cwargs(module_under_test, caplog):
    """Test timed_call works with named parameters."""
    caplog.set_level(logging.DEBUG)

    caplog.clear()

    def fn_cwargs(c1: int = None):
        return c1

    assert fn_cwargs(3) == module_under_test.timed_call("cwargs fn", fn_cwargs, c1=3)
    assert any(_ for _ in caplog.messages if "cwargs fn" in _)
