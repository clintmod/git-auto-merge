#!/usr/bin/env python

import argparse
import json
import logging
import os
import re
import sys
from argparse import Namespace
from subprocess import CalledProcessError

from packaging.version import Version

import utils

ARGS: Namespace | None = None

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


def configure_logging(verbose):
    stream = logging.StreamHandler(sys.stdout)
    LOG.addHandler(stream)
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(log_format)
    stream.setFormatter(formatter)
    root_logger = logging.getLogger("")
    if verbose is not None and verbose > 0 or "VERBOSE" in os.environ:
        root_logger.setLevel(logging.DEBUG)
        root_logger.debug("Verbose logging enabled")
    else:
        root_logger.setLevel(logging.INFO)


def get_branch_list_raw():
    command = "git branch -r | sed 's|origin/||' | grep -v HEAD"
    branches_string = utils.execute_shell(command)
    return branches_string


def get_branch_list(config):
    orig_dir = os.getcwd()
    os.chdir(get_repo_path(config))
    branches_raw = get_branch_list_raw()
    branches = branches_raw.split("\n")
    while "" in branches:
        branches.remove("")
    LOG.debug("split branches = %s", branches)
    branches = [branch.strip() for branch in branches]
    os.chdir(orig_dir)
    return branches


def init():
    parser = argparse.ArgumentParser(
        prog="git-auto-merge", description="Merge git flow branches down"
    )
    parser.add_argument("--verbose", "-v", action="count", help="LOG everything to the console")
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="dry run. This will not push to github."
    )
    global ARGS
    ARGS = parser.parse_args()
    verbosity = 0 if ARGS.verbose == "None" else ARGS.verbose
    configure_logging(verbosity)


def get_repo():
    return_val = ""
    if "GIT_REPO" in os.environ:
        return_val = os.environ["GIT_REPO"]
        assert return_val != ""
    return return_val


def get_repo_name():
    return get_repo().split("/")[-1]


def get_repo_path(config):
    assert "repo_path" in config
    return f"{config['repo_path']}/{get_repo_name()}"


def clone():
    os.makedirs("repos", exist_ok=True)
    orig_dir = os.getcwd()
    os.chdir("repos")
    command = ""
    repo = get_repo()
    repo_name = get_repo_name()
    LOG.info("cloning/fetching repo = %s", repo)
    command = f"git clone {repo}"
    command += f" || cd {repo_name} && git fetch --prune && cd .."
    utils.execute_shell(command)
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
    if "GIT_REPO" not in os.environ:
        message = "Expected the GIT_REPO environment variable to contain a"
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


def load_config(path=None):
    path = path or ".git-auto-merge.json"
    config = {}
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
    branch_list = get_branch_list(config)
    plan_config = config["plan"]
    root_config = plan_config["root"]
    plan = process_branch_config(branch_config=root_config, branch_list=branch_list, upstream=None)
    return plan


def main():
    init()
    validate_environment()
    clone()
    config = load_config()
    plan = build_plan(config)
    LOG.info("Plan: %s", plan)
    cur_dir = os.curdir
    os.chdir(f"{get_repo_path(config)}")
    errors = merge_all(plan)
    os.chdir(cur_dir)
    handle_errors(errors)


if __name__ == "__main__":
    main()
