from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import patch

import utils


@patch("utils.run")
def test_execute_shell(run_mock):
    run_mock.side_effect = run_func
    utils.execute_shell(["asdf"])


# pylint: disable=unused-argument,too-many-arguments
def run_func(command, shell, cwd, stderr, check, stdout, universal_newlines):
    length = len(command)
    assert length > 0
    assert command[0] == "asdf"
    return CompletedProcess(args=command, returncode=0, stdout="")


@patch("utils.run")
def test_execute_shell_handles_errors(run_mock):
    run_mock.side_effect = run_error_func
    try:
        utils.execute_shell(["expecting error"])
        assert False, "expected CalledProcessError"
    except CalledProcessError:
        pass


# pylint: disable=unused-argument,too-many-arguments
def run_error_func(command, shell, cwd, stderr, check, stdout, universal_newlines):
    raise CalledProcessError(0, command)


def test_execute_shell_handles_pwd():
    pwd = utils.execute_shell(["pwd"])
    assert pwd
