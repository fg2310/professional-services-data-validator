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

import argparse
import logging
import os
from unittest import mock
import pytest

from data_validation import cli_tools, exceptions
from data_validation import __main__ as main


TEST_CONN = '{"source_type":"Example"}'
CLI_ARGS = {
    "command": "validate",
    "validate_cmd": "column",
    "source_conn": TEST_CONN,
    "target_conn": TEST_CONN,
    "tables_list": "my_schema.my_table",
    "sum": "col_a,col_b",
    "count": "col_a,col_b",
    "config_file": "example_test.yaml",
    "verbose": True,
}

CONFIG_RUNNER_ARGS_1 = {
    "verbose": False,
    "log_level": "INFO",
    "command": "configs",
    "validation_config_cmd": "run",
    "dry_run": False,
    "config_file": "gs://pso-kokoro-resources/resources/test/unit/test__main/3validations/first.yaml",
    "config_dir": None,
    "kube_completions": True,
}
CONFIG_RUNNER_ARGS_2 = {
    "verbose": False,
    "log_level": "INFO",
    "dry_run": False,
    "command": "configs",
    "validation_config_cmd": "run",
    "kube_completions": True,
    "config_dir": "gs://pso-kokoro-resources/resources/test/unit/test__main/3validations",
}
CONFIG_RUNNER_ARGS_3 = {
    "verbose": False,
    "log_level": "INFO",
    "dry_run": False,
    "command": "configs",
    "kube_completions": True,
    "validation_config_cmd": "run",
    "config_dir": "gs://pso-kokoro-resources/resources/test/unit/test__main/4partitions",
}
CONFIG_RUNNER_ARGS_4 = {
    "verbose": False,
    "log_level": "INFO",
    "dry_run": False,
    "command": "configs",
    "kube_completions": False,
    "validation_config_cmd": "run",
    "config_dir": "gs://pso-kokoro-resources/resources/test/unit/test__main/4partitions",
}

CONFIG_RUNNER_EXCEPTION_TEXT = (
    "Error '{}' occurred while running config file {}. Skipping it for now."
)


@mock.patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(**CLI_ARGS),
)
def test_configure_arg_parser(mock_args):
    """Test arg parser values."""
    args = cli_tools.get_parsed_args()
    file_path = main._get_arg_config_file(args)

    assert file_path == "example_test.yaml"


@mock.patch("data_validation.__main__.run_validations")
@mock.patch(
    "data_validation.__main__.build_config_managers_from_yaml",
    return_value=["config dict from one file"],
)
@mock.patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(**CONFIG_RUNNER_ARGS_1),
)
def test_config_runner_1(mock_args, mock_build, mock_run, caplog):
    """config_runner, runs the validations, so we have to mock run_validations and examine the arguments
    passed to it. Build Config Managers reads the yaml files and builds the validation configs,
    which also includes creating a connection to the database. That is beyond a unit test, so mock
    build_config_managers_from_yaml.
    First test - run validation on a single file - and provide the -kc argument
    Expected result
    1. One config manager created
    2. Warning about inappropriate use of -kc
    Other test cases can be developed.
    """
    caplog.set_level(logging.WARNING)
    args = cli_tools.get_parsed_args()
    caplog.clear()
    main.config_runner(args)
    # assert warning is seen
    assert caplog.messages == [
        "--kube-completions or -kc specified, which requires a config directory, however a specific config file is provided."
    ]
    # assert that only one config manager object is present
    assert len(mock_run.call_args.args[1]) == 1


@mock.patch("data_validation.__main__.run_validations")
@mock.patch(
    "data_validation.__main__.build_config_managers_from_yaml",
    return_value=["config dict from one file"],
)
@mock.patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(**CONFIG_RUNNER_ARGS_2),
)
def test_config_runner_2(mock_args, mock_build, mock_run, caplog):
    """Second test - run validation on a directory - and provide the -kc argument,
    but not running in a Kubernetes Completion Configuration. Expected result
    1. Multiple (3) config manager created for validation
    2. Warning about inappropriate use of -kc"""
    caplog.set_level(logging.WARNING)
    args = cli_tools.get_parsed_args()
    caplog.clear()
    main.config_runner(args)
    # assert warning is seen
    assert caplog.messages == [
        "--kube-completions or -kc specified, however not running in Kubernetes Job completion, check your command line."
    ]
    # assert that validation is called thrice, once for each file
    assert mock_run.call_count == 3


@mock.patch("data_validation.__main__.run_validations")
@mock.patch(
    "data_validation.__main__.build_config_managers_from_yaml",
    return_value=["config dict from one file"],
)
@mock.patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(**CONFIG_RUNNER_ARGS_3),
)
def test_config_runner_3(mock_args, mock_build, mock_run, caplog):
    """Second test - run validation on a directory - and provide the -kc argument,
    have system believe it is running in a Kubernetes Completion Environment. Expected result
    1. No warnings
    2. run validation called as though config file is provided (config_dir is None)
    3. run validation config file name corresponds to value of JOB_COMPLETION_INDEX
    4. One config manager created for validation
    """
    caplog.set_level(logging.WARNING)
    os.environ["JOB_COMPLETION_INDEX"] = "2"
    args = cli_tools.get_parsed_args()
    caplog.clear()
    main.config_runner(args)
    # assert no warnings
    assert caplog.messages == []
    # assert that only one config manager and one validation corresponding to JOB_COMPLETION_INDEX is set.
    assert mock_run.call_args.args[0].config_dir is None
    assert os.path.basename(mock_run.call_args.args[0].config_file) == "0002.yaml"
    assert len(mock_run.call_args.args[1]) == 1


@mock.patch("data_validation.__main__.run_validations")
@mock.patch(
    "data_validation.__main__.build_config_managers_from_yaml",
    return_value=["config dict from one file"],
)
@mock.patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(**CONFIG_RUNNER_ARGS_4),
)
def test_config_runner_4(mock_args, mock_build, mock_run, caplog):
    """Third test - run validation on a directory with failures in one validation,
        Running in a non Kube completions environment. Expected Result:
    1. All 4 files are validated, even though one of them raises an exception.
    2. Exception from one validation is trapped, file skipped and raised at the end.
    """
    mock_run.side_effect = [10, ValueError("Boom!"), 12, 10]
    caplog.set_level(logging.WARNING)
    args = cli_tools.get_parsed_args()
    caplog.clear()
    with pytest.raises(exceptions.ValidationException) as e_info:
        main.config_runner(args)
    # assert that exception message was output for the failed validation
    # validation is called four times, once for each file
    # After all four files were validated, an exception was raised back to main to return status
    assert caplog.messages[0] == CONFIG_RUNNER_EXCEPTION_TEXT.format(
        "Boom!", "0001.yaml"
    )
    assert mock_run.call_count == 4
    assert e_info.value.args[0] == "Some of the validations raised an exception"
