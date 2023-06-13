#!/usr/bin/env python

import logging
import os
import sys
from subprocess import CalledProcessError
from unittest.mock import patch

import pytest

import gitflow_merge as gm

LOG = logging.getLogger("gitflow_merge_test")


@pytest.fixture(autouse=True)
def mock_os_makedirs(mocker):
    mocker.patch("os.makedirs")
    mocker.patch("os.chdir")
    mocker.patch.dict("os.environ", {"REPO_LIST": "backend,mobile"})


@patch("argparse.ArgumentParser.parse_args")
def test_init(parse_args_mock):
    parse_args_mock.return_value.verbose = 1
    gm.init()


def execute_shell_func(command):
    assert command is not None
    return "hotfix/1.0.1\nhotfix/1.0.2\nrelease/2.3.0"


def test_configure_logging():
    gm.configure_logging(0)
    assert logging.INFO == logging.getLogger("").level


def test_configure_logging_verbose():
    gm.configure_logging(1)
    assert logging.DEBUG == logging.getLogger("").level


@patch("utils.execute_shell")
def test_main(execute_shell_mock):
    sys.argv = ["-d"]
    gm.main()
    execute_shell_mock.assert_called()


def test_merge_item():
    branch_name = "main"
    merge_item = gm.MergeItem(branch_name)
    assert str(merge_item) == "None -> main"


@pytest.mark.skip("temp")
def test_sort_and_convert_versioned_to_strings():
    hotfixes = ["hotfix/11.0.1", "hotfix/1.0.2", "hotfix/22.0.1", "hotfix/2.0.2"]
    versioned_hotfixes = gm.get_versioned(hotfixes)
    releases = ["release/11.1.0", "release/1.1.0", "release/22.2.0", "release/2.2.0"]
    versioned_releases = gm.get_versioned(releases)
    all_versioned = versioned_hotfixes + versioned_releases
    all_versioned.sort()
    sorted_versioned = gm.convert_versioned_to_strings(all_versioned)
    expected = [
        "hotfix/1.0.2",
        "release/1.1.0",
        "hotfix/2.0.2",
        "release/2.2.0",
        "hotfix/11.0.1",
        "release/11.1.0",
        "hotfix/22.0.1",
        "release/22.2.0",
    ]
    print("expected = " + str(expected))
    print("actual   = " + str(sorted_versioned))
    assert expected == sorted_versioned


@patch("utils.execute_shell")
def test_clone(execute_shell_mock):
    gm.clone()
    execute_shell_mock.assert_called()


@patch("utils.execute_shell")
def test_merge(execute_shell_mock):
    gm.merge("asdf", "asdf", "asdf")
    execute_shell_mock.assert_called()


def test_merge_problem():
    err = Exception("test error")
    mp1 = gm.MergeProblem("repo", "merge_from", "merge_to", err)
    assert str(mp1)


def raise_merge_error(command):
    if "git merge" in command:
        raise CalledProcessError(0, command)
    return "asdf\nasdf"


@patch("utils.execute_shell")
def test_merge(execute_shell_mock):
    execute_shell_mock.side_effect = raise_merge_error
    errors = gm.merge("from", "to", "repo")
    assert errors


@patch("sys.exit")
def test_validate_environment(sys_exit_mock):
    del os.environ["REPO_LIST"]
    gm.validate_environment()
    sys_exit_mock.assert_called_with(1)


def exists_func(path):
    if path == "reports":
        return False
    else:
        return True


@patch("os.mkdir")
@patch("os.remove")
@patch("os.path.exists")
@patch("sys.exit")
@patch("gitflow_merge.LOG.info")
def test_handle_errors(log_info_mock, sys_exit_mock, exists_mock, remove_mock, mkdir_mock):
    exists_mock.side_effect = exists_func
    err1 = Exception("test error1")
    mp1 = gm.MergeProblem("repo1", "merge_from1", "merge_to1", err1)
    gm.handle_errors([mp1])
    log_info_mock.assert_called_with(mp1)
    sys_exit_mock.assert_called()
    remove_mock.assert_called()
    mkdir_mock.assert_called()


@pytest.mark.skip("temp")
@patch("gitflow_merge.get_branch_list_raw")
def test_main_branch_supported(branches_mock):
    branches_mock.side_effect = get_branch_list_raw
    actual = gm.get_merge_down_branch_list()
    expected = [
        "main",
        "release/2.3.0",
        "hotfix/2.3.1-codename",
        "release/2.4.0",
        "hotfix/2.4.2",
        "release/prefix-1000.1000.1000-codename",
        "develop",
    ]
    assert expected == actual


def test_load_config():
    gm.load_config()


@patch("gitflow_merge.init")
@patch("utils.execute_shell")
@pytest.mark.skip("temp")
def test_main(init_mock, execute_shell_mock):
    gm.main()


@patch("gitflow_merge.get_branch_list_raw")
def test_build_plan(branches_mock):
    branches_mock.side_effect = get_branch_list_raw
    config = gm.load_config()
    LOG.info(f"config = {config}")
    plan = gm.build_plan(config)
    LOG.warning(f"plan = {plan}")
    raise AssertionError()


def get_branch_list_raw():
    return (
        "      as/TICKET-1087\n"
        "      as/TICKET-912\n"
        "      cm/formatting\n"
        "      cm/hotfix/TICKET-1456\n"
        "      develop\n"
        "      feature/DOK-126\n"
        "      feature/DOK-254-logging-nodeploy\n"
        "      feature/DOK-545-staticdb\n"
        "      feature/TICKET-1087\n"
        "      feature/TICKET-1087-staticdb\n"
        "      feature/TICKET-1128\n"
        "      feature/TICKET-1224\n"
        "      feature/TICKET-1224-cleanup\n"
        "      feature/TICKET-1331\n"
        "      feature/TICKET-1368\n"
        "      feature/TICKET-1397-staticdb\n"
        "      feature/TICKET-1422-staticdb\n"
        "      feature/TICKET-1441\n"
        "      feature/TICKET-922\n"
        "      feature/default-staticdb\n"
        "      feature/demo-staticdb\n"
        "      feature/unpin-pylint\n"
        "      hotfix/TICKET-1162-staticdb\n"
        "      hotfix/TICKET-1411\n"
        "      hotfix/TICKET-1411-income-widget-remove-pending-transactions\n"
        "      hotfix/TICKET-1441\n"
        "      hotfix/TICKET-1456\n"
        "      hotfix/TICKET-916\n"
        "      hotfix/TICKET-916-followup\n"
        "      hotfix/sponsored-offers-optimizations\n"
        "      hotfix/sponsored-offers-optimizations-2\n"
        "      main\n"
        "      mati/model_1.5\n"
        "      mati/model_1.5.2\n"
        "      staging\n"
        "      release/2.3.0\n"
        "      release/2.4.0\n"
        "      hotfix/2.3.1-codename\n"
        "      hotfix/2.4.2\n"
        "      release/prefix-1000.1000.1000-codename\n"
        "      test/20210210-staticdb\n"
    )
