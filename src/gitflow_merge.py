#!/usr/bin/env python

import argparse
import json
import logging
import os
import re
import sys
from packaging.version import Version
from subprocess import CalledProcessError

import utils

DRY_RUN = False

# pylint: disable=invalid-name
log = logging.getLogger("gitflow_merge")

# pylint: disable=anomalous-backslash-in-string,line-too-long
SEMVER_PATTERN = r"(\d+\.\d+\.\d+)"


def is_semver(version_string):
    return re.match(SEMVER_PATTERN, version_string) is not None


class VersionedBranch:
    name = ""
    version = ""

    def __init__(self, name, version):
        assert name is not None and name != ""
        assert version is not None and version != ""
        self.name = name
        self.version = version

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __lt__(self, item):
        return Version(self.version) < Version(item.version)


class MergeProblem:
    repo = ""
    merge_from = ""
    merge_to = ""
    error = None

    def __init__(self, repo, merge_from, merge_to, error):
        self.repo = repo
        self.merge_from = merge_from
        self.merge_to = merge_to
        self.error = error

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()

    def to_string(self):
        return_val = "An error occurred merging"
        return_val += " from {} to {} in repo {}."
        return_val += " The error message was: {}"
        return_val = return_val.format(
            self.merge_from, self.merge_to, self.repo, self.error
        )
        return return_val

    def to_string_short(self):
        return_val = "An error occurred merging"
        return_val += " from {} to {} in repo {}."
        return_val = return_val.format(self.merge_from, self.merge_to, self.repo)
        return return_val


def configure_logging(verbose):
    sh = logging.StreamHandler(sys.stdout)
    log.addHandler(sh)
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(log_format)
    sh.setFormatter(formatter)
    root_logger = logging.getLogger("")
    if verbose is not None and verbose > 0 or "VERBOSE" in os.environ:
        root_logger.setLevel(logging.DEBUG)
        root_logger.debug("Verbose logging enabled")
    else:
        root_logger.setLevel(logging.INFO)


def get_main_branch_name():
    command = (
        "git branch -r | grep -v HEAD | grep -E '(origin/main|origin/master)' | sed 's|origin/||'"
    )
    main_branch_name = utils.execute_shell(command)
    return main_branch_name

def get_branch_list_raw():
    command = "git branch -r | sed 's|origin/||' | grep -v HEAD"
    branches_string = utils.execute_shell(command)
    return branches_string

def get_branch_list():
    branches_raw = get_branch_list_raw()
    branches = branches_raw.split("\n")
    while "" in branches:
        branches.remove("")
    log.debug("split branches = %s", branches)
    branches = [branch.strip() for branch in branches]
    return branches


def get_branch_list_for_prefix(prefix, versioned=False):
    branches = get_branch_list()
    branches = [branch for branch in branches if branch.startswith(prefix)]
    if versioned:
        branches = get_versioned(branches)
    return branches


def get_merge_down_branch_list():
    main_branch_name = get_main_branch_name()
    hotfix_versioned = get_branch_list_for_prefix("hotfix/", versioned=True)
    log.debug("hotfix_versioned = %s", hotfix_versioned)
    releases = get_branch_list_for_prefix("release/", versioned=True)
    log.debug("releases = %s", releases)
    all_versioned = hotfix_versioned + releases
    all_versioned.sort()
    log.debug("all_versioned = %s", all_versioned)
    all_versioned = convert_versioned_to_strings(all_versioned)
    log.debug("sorted stringed all_versioned = %s", all_versioned)
    branches = [main_branch_name] + all_versioned
    branches = branches + ["develop"]
    return branches


def get_feature_branch_list():
    features = get_branch_list_for_prefix("feature/")
    log.debug("features = %s", features)
    return features


def get_versioned(branches):
    versions = []
    for branch in branches:
        match = re.search(SEMVER_PATTERN, branch)
        if match:
            version = match.group(1)
            versions.append(VersionedBranch(branch, version))
        else:
            log.debug(f"branch not matched {branch}")
    return versions


def convert_versioned_to_strings(branches):
    if branches is None:
        return []
    for idx, item in enumerate(branches):
        branches[idx] = str(item)
    return branches


def parse_args():
    parser = argparse.ArgumentParser(
        prog="gitflow-merge", description="Merge git flow branches down"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", help="log everything to the console"
    )
    parser.add_argument(
        "--dry-run", "-d", action='store_true', help="dry run. This will not push to github."
    )
    args = parser.parse_args()
    verbosity = 0 if args.verbose == "None" else args.verbose
    global DRY_RUN
    DRY_RUN = args.dry_run
    configure_logging(verbosity)


def get_repo_list():
    return_val = ""
    if "REPO_LIST" in os.environ:
        return_val = os.environ["REPO_LIST"]
    return return_val.split(",")

def get_repo_name(repo):
    return repo.split('/')[-1]

def clone_all():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    command = ""
    for repo in repo_list:
        repo_name = get_repo_name(repo)
        log.info("cloning/fetching repo = %s", repo)
        command = f"git clone {repo}"
        command += f" || cd {repo_name} && git fetch --prune && cd .."
        utils.execute_shell(command)
    os.chdir("..")

def git_push(branch):
    if DRY_RUN:
        log.info(f"dry run: skipping push for {branch}")
    else:
        utils.execute_shell(f"git push origin {branch}")

def merge(merge_from, merge_to, repo):
    errors = []
    log.info("Merging from %s to %s in repo %s", merge_from, merge_to, repo)
    command = "git reset --hard HEAD"
    command += f" && git clean -fdx && git checkout {merge_to}"
    command += f" && git reset --hard origin/{merge_to}"
    command += " && git submodule update --init --recursive"
    utils.execute_shell(command)
    try:
        message = utils.execute_shell(f"git merge origin/{merge_from}")
    except CalledProcessError as e:
        log.info(
            "Merging failed from %s to %s in repo %s",
            merge_from,
            merge_to,
            repo,
        )
        errors.append(MergeProblem(repo, merge_from, merge_to, e))
    else:
        if "Already up to date" not in message:
            git_push(merge_to)
        else:
            log.info("Nothing to do: %s", message)
    return errors

def merge_down():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    errors = []
    for repo in repo_list:
        repo_name = get_repo_name(repo)
        os.chdir(repo_name)
        log.debug("repo = %s", repo_name)
        branches = get_merge_down_branch_list()
        branches_length = len(branches)
        idx = 1
        while idx < branches_length:
            merge_from = branches[idx - 1]
            merge_to = branches[idx]
            errors += merge(merge_from, merge_to, repo_name)
            idx += 1
        os.chdir("..")
    os.chdir("..")
    return errors


def merge_develop_to_feature_branches():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    errors = []
    for repo in repo_list:
        repo_name = get_repo_name(repo)
        os.chdir(repo_name)
        log.debug("repo = %s", repo_name)
        branches = get_feature_branch_list()
        for branch in branches:
            errors += merge('develop', branch, repo_name)
        os.chdir("..")
    os.chdir("..")
    return errors


def merge_all():
    down_errors = merge_down()
    feature_errors = merge_develop_to_feature_branches()
    return down_errors + feature_errors


def validate_environment():
    errors_found = False
    if "REPO_LIST" not in os.environ:
        message = "Expected the REPO_LIST environment variable to contain a"
        message += " comma separated list of repos to operate on"
        log.error(message)
        errors_found = True
    if errors_found:
        sys.exit(1)


def handle_errors(merge_errors):
    if not merge_errors:
        return
    log.info("Printing error report and writing it to ./reports:")
    if not os.path.exists("reports"):
        os.mkdir("reports")
    if os.path.exists("reports/errors.txt"):
        os.remove("reports/errors.txt")
    # pylint: disable=unspecified-encoding
    with open("reports/errors.txt", "w") as file:
        for merge_error in merge_errors:
            log.info(merge_error)
            file.write(merge_error.to_string_short() + "\n")
    sys.exit(1)

def load_config(path=None):
    path = path or '.gitflow-merge.json'
    with open(path) as file:
        return json.load(file)

def safe_get(dict, key):
    if key in dict:
        return dict[key]
    else:
        return None

def merge_all_repos(config):
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    errors = []
    for repo in repo_list:
        repo_name = get_repo_name(repo)
        os.chdir(repo_name)
        branch_list = get_branch_list()
        merge_plan = {}
        branch_configs = config["branches"]
        for key in branch_configs:
            branch_config = branch_configs[key]
            name = safe_get(branch_config, "name")
            regex = safe_get(branch_config, "regex")
            parent = safe_get(branch_config, "parent")
            if name is not None and name in branch_list and parent is None:
                merge_plan[name] = branch_config
            #if regex is not None:

        os.chdir("..")
    os.chdir("..")
    return errors

def main():
    config = load_config()
    validate_environment()
    parse_args()
    clone_all()
    errors = merge_all_repos(config)
    handle_errors(errors)


if __name__ == "__main__":
    main()
