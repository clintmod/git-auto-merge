import pytest
from click.testing import CliRunner

import git_auto_merge


@pytest.fixture(autouse=True)
def args():
    return ["--repo", "git@github.com:clintmod/git_auto_merge_test.git"]


def test_cli_works(args):
    runner = CliRunner()
    result = runner.invoke(git_auto_merge.cli, args)
    assert "Merge complete" in result.output
    assert result.exit_code == 0


def test_cli_skips_push_when_dry_run(args):
    runner = CliRunner()
    args += ["--dry-run"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert "dry run: skipping push" in result.output
    assert "Merge complete" in result.output
    assert result.exit_code == 0


def test_cli_logs_everything_when_debug(args):
    runner = CliRunner()
    args += ["--log-level", "DEBUG"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert "--- executing shell command ---" in result.output
    assert "Merge complete" in result.output
    assert result.exit_code == 0


def test_cli_exits_non_zero_on_error(args):
    runner = CliRunner()
    args += ["--repo", "git@github.com:clintmod/git_auto_merge_test_conflict.git"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert result.exit_code != 0


def test_cli_help():
    runner = CliRunner()
    args = ["--help"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert result.exit_code == 0
