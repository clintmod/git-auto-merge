#!/usr/bin/env python

import os
import sys
from subprocess import CalledProcessError
from unittest.mock import ANY, patch

import click
import pytest

import git_auto_merge as gam


@pytest.fixture(autouse=True)
def mock_os_makedirs(mocker):
    mocker.patch("os.makedirs")
    mocker.patch("os.chdir")


@pytest.fixture(autouse=True, name="click_context")
def create_click_context():
    click_context = click.Context(click.Command("git-auto-merge"))
    click_context.params = dict(
        dry_run=False,
        log_level="INFO",
        use_default_plan=True,
        repo=os.getenv("GIT_AUTO_MERGE_REPO"),
    )
    return click_context


def test_get_repo_name(click_context):
    with click_context:
        assert "git_auto_merge_test" == gam.get_repo_name()


def execute_shell_func(command):
    assert command is not None
    return "hotfix/1.0.1\nhotfix/1.0.2\nrelease/2.3.0"


@patch("git_auto_merge.log.add")
def test_configure_logging(add_logger_mock, click_context):
    with click_context:
        level = "ERROR"
        click_context.params["log_level"] = level
        gam.configure_logging()
        add_logger_mock.assert_called_with(sink=sys.stderr, format=ANY, level=level)


@patch("git_auto_merge.log.add")
def test_configure_logging_verbose(add_logger_mock, click_context):
    with click_context:
        level = "VERBOSE"
        click_context.params["log_level"] = level
        gam.configure_logging()
        add_logger_mock.assert_called_with(sink=sys.stderr, format=ANY, level=level)


def test_merge_item():
    branch_name = "main"
    merge_item = gam.MergeItem(group="", branch_name=branch_name)
    assert merge_item.branch_name == "main"


def test_versioned_branch_raises_assertion_error():
    with pytest.raises(AssertionError):
        gam.VersionedBranch("asdf")


def test_sorting_versioned_branches_works():
    hotfixes = ["hotfix/11.0.1", "hotfix/1.0.2", "hotfix/22.0.1", "hotfix/2.0.2"]
    versioned_hotfixes = [gam.VersionedBranch(branch) for branch in hotfixes]
    releases = ["release/11.1.0", "release/1.1.0", "release/22.2.0", "release/2.2.0"]
    versioned_releases = [gam.VersionedBranch(branch) for branch in releases]
    all_versioned = versioned_hotfixes + versioned_releases
    all_versioned.sort()
    sorted_versioned = [str(branch) for branch in all_versioned]
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
@patch("git_auto_merge.get_branch_list_raw")
def test_merge_all(raw_branches_mock, execute_shell_mock, click_context):
    with click_context:
        raw_branches_mock.return_value = "  develop\n" + "  main\n"
        config = gam.load_config()
        plan = gam.build_plan(config)
        errors = gam.merge_all(plan)
        assert not errors
        execute_shell_mock.assert_called()


def test_git_push_does_not_push_when_dryrun_is_true():
    context = click.Context(click.Command("git-auto-merge"))
    context.params = {"dry_run": True}
    with context:
        assert not gam.git_push("asdf", "asdf")


@patch("utils.execute_shell")
def test_clone(execute_shell_mock, click_context):
    with click_context:
        gam.clone()
        execute_shell_mock.assert_called()


@patch("utils.execute_shell")
def test_merge_branches(execute_shell_mock, click_context):
    with click_context:
        gam.merge_branches("asdf", "asdf")
        execute_shell_mock.assert_called()


@patch("utils.execute_shell")
def test_merge_branches_does_not_push_when_up_to_date(execute_shell_mock, click_context):
    with click_context:
        execute_shell_mock.return_value = "Already up to date"
        gam.merge_branches("asdf", "asdf")


def test_merge_problem():
    err = CalledProcessError(returncode=1, cmd="asdf", output="test error")
    mp1 = gam.MergeError(merge_from="merge_from", merge_to="merge_to", error=err)
    assert str(mp1)


def raise_merge_error(command):
    if "git merge" in command:
        raise CalledProcessError(0, command, output="asdf\nasdf")


@patch("utils.execute_shell")
def test_merge_branches_reports_errors(execute_shell_mock):
    execute_shell_mock.side_effect = raise_merge_error
    errors = gam.merge_branches(merge_from="from", merge_to="to")
    assert errors


@patch("utils.execute_shell")
@patch("git_auto_merge.get_branch_list_raw")
def test_merge_all_reports_errors(raw_branches_mock, execute_shell_mock, click_context):
    with click_context:
        raw_branches_mock.side_effect = get_branch_list_raw
        config = gam.load_config()
        plan = gam.build_plan(config)
        execute_shell_mock.side_effect = raise_merge_error
        gam.log.info("Plan: {}", plan)
        errors = gam.merge_all(merge_item=plan)
        assert errors


@patch("sys.exit")
@patch("git_auto_merge.log.error")
def test_handle_errors(log_err_mock, sys_exit_mock):
    err1 = Exception("test error1")
    mp1 = gam.MergeError(merge_from="merge_from", merge_to="merge_to", error=err1)
    gam.handle_errors([mp1])
    log_err_mock.assert_called_with(mp1)
    sys_exit_mock.assert_called()


def test_load_config(click_context):
    with click_context:
        gam.load_config()


@patch("git_auto_merge.get_branch_list_raw")
def test_build_plan(raw_branches_mock, snapshot, click_context):
    with click_context:
        raw_branches_mock.side_effect = get_branch_list_raw
        config = gam.load_config()
        plan = gam.build_plan(config)
        snapshot.assert_match(f"{str(plan)}\n", "test_build_plan.txt")


@patch("git_auto_merge.get_branch_list_raw")
def test_build_plan_works_when_only_main(raw_branches_mock, snapshot, click_context):
    with click_context:
        raw_branches_mock.return_value = "      main\n"
        config = gam.load_config()
        plan = gam.build_plan(config)
        snapshot.assert_match(f"{str(plan)}\n", "test_build_plan_works_when_only_main.txt")


@patch("git_auto_merge.get_branch_list_raw")
def test_build_plan_works_when_only_main_and_develop(raw_branches_mock, snapshot, click_context):
    with click_context:
        raw_branches_mock.return_value = "  develop\n" + "  main\n"
        config = gam.load_config()
        plan = gam.build_plan(config)
        snapshot.assert_match(f"{str(plan)}\n", "test_build_plan_works_for_main_and_develop.txt")


@patch("git_auto_merge.get_branch_list_raw")
def test_build_plan_works_when_multi_project(raw_branches_mock, snapshot, click_context):
    with click_context:
        raw_branches_mock.side_effect = multi_project_branch_list_raw
        config = gam.load_config("tests/unit/multi-project-config.json")
        plan = gam.build_plan(config)
        snapshot.assert_match(f"{str(plan)}\n", "test_build_plan_works_when_multi_project.txt")


@patch("git_auto_merge.get_branch_list_raw")
def test_weird_branch_bug(raw_branches_mock, snapshot, click_context):
    with click_context:
        click_context.params["config_file_name"] = "tests/unit/test_files/weird_branch_bug.json"
        raw_branches_mock.side_effect = get_weird_branch_bug
        config = gam.load_config()
        plan = gam.build_plan(config)
        snapshot.assert_match(f"{str(plan)}\n", "test_weird_branch_bug.txt")


def get_branch_list_raw():
    return (
        "      as/TICKET-1087\n"
        "      as/TICKET-912\n"
        "      cm/formatting\n"
        "      cm/hotfix/TICKET-1456\n"
        "      develop\n"
        "      feature/DOK-126\n"
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
        "      bugfix/2.4.0/asdf2\n"
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


def multi_project_branch_list_raw():
    return (
        "      production\n"
        "      feature/DOK-126\n"
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
        "      bugfix/bank/2.4.0/asdf2\n"
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
        "      staging\n"
        "      release/bank/2.3.0\n"
        "      release/bank/2.3\n"
        "      release/bank/2.4.0\n"
        "      hotfix/bank/2.3.1-codename\n"
        "      hotfix/bank/2.4.2\n"
        "      release/auto/2.2.0\n"
        "      release/auto/2.1.0\n"
        "      hotfix/auto/2.1.1-codename\n"
        "      hotfix/auto/2.2.2\n"
    )


def get_weird_branch_bug():
    return (
        "      develop\n"
        "      release/avengers-24.1.1\n"
        "      release/batgirl-24.2.1\n"
        "      release/batman-24.2.0\n"
        "      release/carnage-24.3.1\n"
        "      release/catwoman-24.3.0\n"
        "      release/deadpool-24.4.0\n"
        "      release/donkeykong-24.4.1\n"
        "      release/eggman-24.5.2\n"
        "      release/electro-24.5.1\n"
        "      release/flash-24.6.0\n"
    )
