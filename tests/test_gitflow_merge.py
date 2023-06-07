#!/usr/bin/env python

import logging as log
import os
import pytest
import sys
from subprocess import CalledProcessError
from unittest.mock import patch

import gitflow_merge as gm

@pytest.fixture(autouse=True)
def mock_os_makedirs(mocker):
    mocker.patch('os.makedirs')
    mocker.patch('os.chdir')

@patch("argparse.ArgumentParser.parse_args")
def test_parse_args(parse_args_mock):
    parse_args_mock.return_value.verbose = 1
    gm.parse_args()

@patch("utils.execute_shell")
def test_get_branch_list_for_prefix(execute_shell_mock):
    execute_shell_mock.side_effect = execute_shell_func
    branches = gm.get_branch_list_for_prefix("hotfix")
    assert branches


def test_get_branch_list_for_prefix_works_for_no_matching_prefix():
    branches = gm.get_branch_list_for_prefix("asdf")
    assert not branches


def execute_shell_func(command):
    assert command is not None
    return "hotfix/1.0.1\nhotfix/1.0.2\nrelease/2.3.0"


def test_configure_logging():
    gm.configure_logging(0)
    assert log.INFO == log.getLogger("").level


def test_configure_logging_verbose():
    gm.configure_logging(1)
    assert log.DEBUG == log.getLogger("").level


def ensure_repo_dirs():
    os.environ["REPO_LIST"] = "backend,mobile"
    repos = gm.get_repo_list()
    for repo in repos:
        os.makedirs(f"repos/{repo}", exist_ok=True)


@patch("utils.execute_shell")
def test_main(execute_shell_mock):
    ensure_repo_dirs()
    sys.argv = ["-d"]
    gm.main()
    execute_shell_mock.assert_called()


def test_versioned_branch():
    branch_name = "hotfix/1.0.1"
    version = branch_name.replace("hotfix/", "")
    branch = gm.VersionedBranch(branch_name, version)
    assert branch.version == "1.0.1"
    assert str(branch) == "hotfix/1.0.1"


def test_convert_versioned_to_strings_works_with_empty_array():
    branches = gm.convert_versioned_to_strings([])
    assert not branches


def test_convert_versioned_to_strings_works_with_none():
    branches = gm.convert_versioned_to_strings(None)
    assert not branches


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


def test_sort_and_convert_versioned_to_strings_works_with_dates():
    hotfixes = [
        "hotfix/2020.01.06",
        "hotfix/2020.01.02",
        "hotfix/2020.06.01",
        "hotfix/2020.12.01",
    ]
    versioned_hotfixes = gm.get_versioned(hotfixes)
    releases = [
        "release/2021.01.01",
        "release/2020.01.01",
        "release/2022.02.01",
        "release/2020.02.01",
    ]
    versioned_releases = gm.get_versioned(releases)
    all_versioned = versioned_hotfixes + versioned_releases
    all_versioned.sort()
    sorted_versioned = gm.convert_versioned_to_strings(all_versioned)
    expected = [
        "release/2020.01.01",
        "hotfix/2020.01.02",
        "hotfix/2020.01.06",
        "release/2020.02.01",
        "hotfix/2020.06.01",
        "hotfix/2020.12.01",
        "release/2021.01.01",
        "release/2022.02.01",
    ]
    print("expected = " + str(expected))
    print("actual   = " + str(sorted_versioned))
    assert sorted_versioned == expected


@patch("utils.execute_shell")
def test_clone_all(execute_shell_mock):
    gm.clone_all()
    execute_shell_mock.assert_called()


@patch("utils.execute_shell")
def test_merge_all(execute_shell_mock):
    ensure_repo_dirs()
    gm.merge_all()
    execute_shell_mock.assert_called()


def test_merge_problem():
    err = Exception("test error")
    mp1 = gm.MergeProblem("repo", "merge_from", "merge_to", err)
    assert str(mp1)


@patch("utils.execute_shell")
def test_merge_down_handles_errors(execute_shell_mock):
    ensure_repo_dirs()
    execute_shell_mock.side_effect = raise_merge_error
    errors = gm.merge_down()
    assert errors


def raise_merge_error(command):
    if "git merge" in command:
        raise CalledProcessError(0, command)
    return "asdf\nasdf"


@patch("sys.exit")
def test_validate_environment(sys_exit_mock):
    del os.environ["REPO_LIST"]
    gm.validate_environment()
    sys_exit_mock.assert_called_with(1)


@patch("sys.exit")
@patch("gitflow_merge.log.info")
def test_handle_errors(log_info_mock, sys_exit_mock):
    err1 = Exception("test error1")
    mp1 = gm.MergeProblem("repo1", "merge_from1", "merge_to1", err1)
    gm.handle_errors([mp1])
    log_info_mock.assert_called_with(mp1)
    sys_exit_mock.assert_called()


@patch("gitflow_merge.get_branch_list_raw")
@patch("utils.execute_shell")
def test_merge_develop_to_feature_branches(execute_shell_mock, branches_mock):
    branches_mock.side_effect = get_branch_list_raw
    execute_shell_mock.side_effect = raise_merge_error
    ensure_repo_dirs()
    errors = gm.merge_develop_to_feature_branches()
    assert errors


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
        "develop"
    ]
    assert expected == actual


def test_get_main_branch_name_works():
    actual = gm.get_main_branch_name()
    expected = "main"
    assert expected == actual


def test_is_semver_works():
    assert gm.is_semver("3.0.0")
    assert not gm.is_semver("3")


def test_load_config():
    gm.load_config()


@patch("gitflow_merge.parse_args")
@patch("utils.execute_shell")
def test_main(parse_args_mock, execute_shell_mock):
    gm.main()


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
