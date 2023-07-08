#!/usr/bin/env python

import argparse
import json
import logging
import os
import re
import sys
from argparse import Namespace
from subprocess import CalledProcessError
from typing import Any

from packaging.version import Version

import utils

ARGS: Namespace | None | Any = None
GIT_AUTO_MERGE_CONFIG_BRANCH = None
GIT_AUTO_MERGE_JSON = ".git-auto-merge.json"
GIT_AUTO_MERGE_REPO_BASE_DIR = "repos"
LOG = logging.getLogger("git_auto_merge")

# pylint: disable=anomalous-backslash-in-string
SEMVER_PATTERN = r"(\d+\.\d+\.\d+)"


class MergeItem:
    branch_name = ""
    upstream = None
    downstream = []

    def __init__(self, branch_name="", upstream=None, downstream=None):
        self.branch_name = branch_name
        self.upstream = upstream
        self.downstream = downstream or []

    def add_downstream_branch(self, branch):
        assert branch is not None
        assert self.branch_name != branch
        merge_item = MergeItem(branch_name=branch, upstream=self)
        self.downstream.append(merge_item)
        return merge_item

    def depth(self):
        if self.upstream is None:
            return 0
        return self.upstream.depth() + 1

    def __str__(self):
        return_val = ""
        if self.upstream is not None:
            return_val = f"{self.upstream.branch_name} -> {self.branch_name}"
        else:
            return_val = f"<root> {self.branch_name}"
        for merge_item in self.downstream:
            return_val += "\n{}{}".format("  " * self.depth(), str(merge_item))
        return return_val


class VersionedBranch:
    name = ""
    version = ""

    def __init__(self, name):
        assert name is not None and name != ""
        self.name = name
        match = re.search(SEMVER_PATTERN, name)
        if match:
            version = match.group(1)
            self.version = version
        else:
            raise AssertionError(f"No semver version found {name}")

    def __str__(self):
        return self.name

    def __lt__(self, item):
        return Version(self.version) < Version(item.version)


class MergeProblem:
    merge_from = ""
    merge_to = ""
    error = None

    def __init__(self, merge_from, merge_to, error):
        self.merge_from = merge_from
        self.merge_to = merge_to
        self.error = error

    def __str__(self):
        return self.to_string()

    def to_string(self):
        return_val = "An error occurred merging"
        return_val += " from {} to {}."
        return_val += " The error message was: {}"
        return_val = return_val.format(self.merge_from, self.merge_to, self.error)
        return return_val


def configure_logging():
    stream = logging.StreamHandler(sys.stdout)
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(log_format)
    stream.setFormatter(formatter)
    root_logger = logging.getLogger("")
    root_logger.addHandler(stream)
    verbosity = ARGS.verbose or 0
    LOG.info('verbosity = "%s"', verbosity)
    if verbosity or "DEBUG" in os.environ:
        root_logger.setLevel(logging.DEBUG)
        root_logger.info("Verbose logging enabled")
    else:
        root_logger.setLevel(logging.INFO)


def get_branch_list_raw():
    command = "git branch -r | sed 's|origin/||' | grep -v HEAD"
    branches_string = utils.execute_shell(command)
    return branches_string


def get_branch_list():
    orig_dir = os.getcwd()
    os.chdir(get_repo_path())
    branches_raw = get_branch_list_raw()
    branches = branches_raw.split("\n")
    while "" in branches:
        branches.remove("")
    LOG.debug("split branches = %s", branches)
    branches = [branch.strip() for branch in branches]
    os.chdir(orig_dir)
    return branches


def parse_args():
    parser = argparse.ArgumentParser(
        prog="git-auto-merge", description="Merge git flow branches down"
    )
    parser.add_argument("--verbose", "-v", action="count", help="LOG everything to the console")
    parser.add_argument(
        "--should-use-default-plan",
        "-u",
        action="store_true",
        help="Use the default plan from the .git-auto-merge.json config file in this repo",
    )
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="dry run. This will not push to github."
    )
    global ARGS
    ARGS = parser.parse_args()


def get_repo():
    return_val = ""
    if "GIT_AUTO_MERGE_REPO" in os.environ:
        return_val = os.environ["GIT_AUTO_MERGE_REPO"]
        assert return_val != ""
    return return_val


def get_repo_name():
    repo_name = get_repo().split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return repo_name


def get_repo_path():
    return f"{GIT_AUTO_MERGE_REPO_BASE_DIR}/{get_repo_name()}"


def clone():
    err = None
    os.makedirs("repos", exist_ok=True)
    orig_dir = os.getcwd()
    os.chdir("repos")
    repo = get_repo()
    repo_name = get_repo_name()
    try:
        LOG.info("Attempting cloning repo = %s", repo)
        LOG.info("This may fail if the repo already exists")
        command = f" git clone {repo}"
        utils.execute_shell(command)
    except CalledProcessError as err:  #  pylint: disable=broad-exception-caught
        if "already exists" in err.output:
            LOG.info("Trying to fetch repo %s instead", repo)
            command = f"cd {repo_name} && git fetch --prune"
            utils.execute_shell(command)
        else:
            raise
    os.chdir(repo_name)
    default_branch = utils.execute_shell(
        "git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'"
    )
    utils.execute_shell(f"git reset --hard HEAD && git checkout {default_branch} && git pull")
    if GIT_AUTO_MERGE_CONFIG_BRANCH is not None:
        LOG.info("checking out config branch %s", GIT_AUTO_MERGE_CONFIG_BRANCH)
        utils.execute_shell(f"git checkout {GIT_AUTO_MERGE_CONFIG_BRANCH}")
    os.chdir(orig_dir)


def git_push(branch):
    if ARGS.dry_run:
        LOG.info(f"dry run: skipping push for {branch}")
        return False
    utils.execute_shell(f"git push origin {branch}")
    return True


def merge_all(merge_item: MergeItem, errors=None):
    errors = errors or []
    assert merge_item is not None
    if merge_item.upstream is not None:
        errors += merge_branches(merge_item.upstream.branch_name, merge_item.branch_name)
    for downstream in merge_item.downstream:
        merge_all(downstream, errors)
    return errors


def merge_branches(merge_from, merge_to):
    errors = []
    LOG.info("Merging from %s to %s", merge_from, merge_to)
    command = "git reset --hard HEAD"
    command += f" && git clean -fdx && git checkout {merge_to}"
    command += f" && git reset --hard origin/{merge_to}"
    command += " && git submodule update --init --recursive"
    utils.execute_shell(command)
    try:
        message = utils.execute_shell(f"git merge origin/{merge_from}")
    except CalledProcessError as err:
        LOG.info(
            "Merging failed from %s to %s",
            merge_from,
            merge_to,
        )
        errors.append(MergeProblem(merge_from, merge_to, err))
    else:
        if "Already up to date" not in message:
            git_push(merge_to)
        else:
            LOG.info("Nothing to do: %s", message)
    return errors


def validate_environment():
    errors_found = False
    if "GIT_AUTO_MERGE_REPO" not in os.environ:
        message = "Expected the GIT_AUTO_MERGE_REPO environment variable to contain a"
        message += " git repo url."
        LOG.error(message)
        errors_found = True
    if errors_found:
        sys.exit(1)


def handle_errors(merge_errors):
    if not merge_errors:
        return
    LOG.info("Printing error report and writing it to ./reports:")
    if os.path.exists("reports/errors.txt"):
        os.remove("reports/errors.txt")
    if not os.path.exists("reports"):
        os.mkdir("reports")
    with open("reports/errors.txt", "w", encoding="utf-8") as file:
        for merge_error in merge_errors:
            LOG.info(merge_error)
            file.write(str(merge_error) + "\n")
    sys.exit(1)


def load_env():
    if os.environ.get("GIT_AUTO_MERGE_JSON"):
        global GIT_AUTO_MERGE_JSON
        GIT_AUTO_MERGE_JSON = os.environ["GIT_AUTO_MERGE_JSON"]
    if os.environ.get("GIT_AUTO_MERGE_REPO_BASE_DIR"):
        global GIT_AUTO_MERGE_REPO_BASE_DIR
        GIT_AUTO_MERGE_REPO_BASE_DIR = os.environ["GIT_AUTO_MERGE_REPO_BASE_DIR"]
    if os.environ.get("GIT_AUTO_MERGE_CONFIG_BRANCH"):
        global GIT_AUTO_MERGE_CONFIG_BRANCH
        GIT_AUTO_MERGE_CONFIG_BRANCH = os.environ["GIT_AUTO_MERGE_CONFIG_BRANCH"]


def load_config():
    config = {}
    path = f"{get_repo_path()}/{GIT_AUTO_MERGE_JSON}"
    if os.path.exists(path):
        config = load_config_from_path(path)
    elif os.path.exists(GIT_AUTO_MERGE_JSON) and ARGS.should_use_default_plan:
        config = load_config_from_path(GIT_AUTO_MERGE_JSON)
    else:
        raise ValueError(
            f"No config file found at {path} and --should-use-default-plan was not specified."
        )
    return config


def load_config_from_path(path):
    LOG.info("Loading config from path %s", path)
    with open(path, encoding="utf-8") as file:
        config = json.load(file)
    return config


def process_regex_selector_config(regex, branch_list):
    selected_branches = [branch for branch in branch_list if re.search(regex, branch)]
    return selected_branches


def process_versioned_branches(selected_branches, upstream: MergeItem):
    versioned_branches = []
    for branch in selected_branches:
        versioned_branches.append(VersionedBranch(branch))
    versioned_branches.sort()
    new_merge_item = upstream
    for branch in versioned_branches:
        new_merge_item = new_merge_item.add_downstream_branch(str(branch))
    return new_merge_item


def process_branches(selected_branches, upstream: MergeItem):
    for branch in selected_branches:
        upstream.add_downstream_branch(branch)


def process_selector_config(selector_config, branch_list):
    selected_branches = []
    if "regex" in selector_config:
        selected_branches += process_regex_selector_config(
            regex=selector_config["regex"], branch_list=branch_list
        )
    elif "name" in selector_config:
        if selector_config["name"] in branch_list:
            selected_branches.append(selector_config["name"])
    return selected_branches


def select_branches(branch_list, selectors_config) -> list:
    selected_branches = []
    for selector_config in selectors_config:
        selected_branches += process_selector_config(
            selector_config=selector_config, branch_list=branch_list
        )
    return selected_branches


def process_selectors_config(
    selectors_config, branch_list, upstream: MergeItem, sort_type=""
) -> MergeItem:
    LOG.debug("selectors_config = %s, upstream = %s", selectors_config, upstream)
    return_val = upstream or MergeItem()
    selected_branches = select_branches(branch_list=branch_list, selectors_config=selectors_config)
    if len(selected_branches) == 0:
        LOG.warning(f"No branches matched for {selectors_config}")
    if len(selected_branches) == 1:
        if upstream is not None:
            return_val = upstream.add_downstream_branch(selected_branches[0])
        else:
            return_val.branch_name = str(selected_branches[0])
    else:
        if sort_type == "version":
            return_val = process_versioned_branches(
                selected_branches=selected_branches, upstream=return_val
            )
        else:
            process_branches(selected_branches=selected_branches, upstream=return_val)
    return return_val


def process_branches_config(branches_config, branch_list, upstream: MergeItem):
    for key in branches_config:
        branch_config = branches_config[key]
        process_branch_config(
            branch_config=branch_config, branch_list=branch_list, upstream=upstream
        )


def process_branch_config(branch_config, branch_list, upstream) -> MergeItem:
    selectors_config = branch_config.get("selectors")
    sort_type = branch_config.get("sort")
    merge_item = process_selectors_config(
        selectors_config=selectors_config,
        upstream=upstream,
        branch_list=branch_list,
        sort_type=sort_type,
    )
    downstream_branches_config = branch_config.get("downstream", {})
    process_branches_config(
        branches_config=downstream_branches_config, upstream=merge_item, branch_list=branch_list
    )
    return merge_item


def build_plan(config) -> MergeItem:
    branch_list = get_branch_list()
    plan_config = config["plan"]
    if not plan_config:
        raise ValueError("No plan found in config")
    root_config = plan_config["root"]
    plan = process_branch_config(branch_config=root_config, branch_list=branch_list, upstream=None)
    return plan


def main():
    parse_args()
    configure_logging()
    validate_environment()
    load_env()
    clone()
    config = load_config()
    plan = build_plan(config)
    LOG.info("Plan: %s", plan)
    cur_dir = os.curdir
    os.chdir(f"{get_repo_path()}")
    errors = merge_all(plan)
    os.chdir(cur_dir)
    handle_errors(errors)


if __name__ == "__main__":
    main()
