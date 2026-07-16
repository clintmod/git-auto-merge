# pytest fixtures are injected by shadowing the fixture-function name
# pylint: disable=redefined-outer-name

import os
import subprocess

import pytest
from click.testing import CliRunner

import git_auto_merge

REPO_DIR = "workdir/git_auto_merge_test"


@pytest.fixture(autouse=True)
def args():
    return ["--repo", os.getenv("GIT_AUTO_MERGE_REPO")]


@pytest.fixture(autouse=True)
def conflict_args():
    return ["--repo", os.getenv("GIT_AUTO_MERGE_REPO_CONFLICT")]


def git(git_args, cwd="."):
    return subprocess.run(["git"] + git_args, cwd=cwd, capture_output=True, text=True, check=False)


def remote_refs():
    out = git(["ls-remote", "--heads", os.getenv("GIT_AUTO_MERGE_REPO")]).stdout
    return dict(reversed(line.split()) for line in out.strip().splitlines())


def local_branches():
    out = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=REPO_DIR).stdout
    return out.split()


def is_ancestor(upstream, downstream):
    return git(["merge-base", "--is-ancestor", upstream, downstream], cwd=REPO_DIR).returncode == 0


def test_cli_works(args):
    runner = CliRunner()
    result = runner.invoke(git_auto_merge.cli, args)
    assert "Merge complete" in result.output
    assert result.exit_code == 0


def test_cli_skips_push_when_dry_run(args):
    runner = CliRunner()
    args += ["--dry-run"]
    refs_before = remote_refs()
    result = runner.invoke(git_auto_merge.cli, args)
    assert "dry run: skipping push" in result.output
    assert "Merge complete" in result.output
    assert result.exit_code == 0
    # the merges really happened in the local clone: per the fixture repo's
    # plan (main -> hotfix/release -> develop -> feature/*), every upstream
    # must now be an ancestor of its downstream; ignore local branches that
    # a stale workdir may carry but the remote no longer has
    remote_branches = {ref.removeprefix("refs/heads/") for ref in refs_before}
    branches = [b for b in local_branches() if b in remote_branches]
    assert "main" in branches and "develop" in branches
    assert is_ancestor("main", "develop")
    versioned = [b for b in branches if b.startswith(("release/", "hotfix/"))]
    assert versioned, "fixture repo should select at least one release/hotfix branch"
    for branch in versioned:
        assert is_ancestor("main", branch), f"main not merged into {branch}"
        assert is_ancestor(branch, "develop"), f"{branch} not merged into develop"
    for branch in (b for b in branches if b.startswith("feature/")):
        assert is_ancestor("develop", branch), f"develop not merged into {branch}"
    # and dry run means the remote was left untouched
    assert remote_refs() == refs_before


def test_cli_logs_everything_when_debug(args):
    runner = CliRunner()
    args += ["--log-level", "DEBUG"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert "--- executing shell command ---" in result.output
    assert "Merge complete" in result.output
    assert result.exit_code == 0


def test_cli_exits_non_zero_on_error(conflict_args):
    runner = CliRunner()
    result = runner.invoke(git_auto_merge.cli, conflict_args)
    assert result.exit_code != 0


def test_cli_help():
    runner = CliRunner()
    args = ["--help"]
    result = runner.invoke(git_auto_merge.cli, args)
    assert result.exit_code == 0
