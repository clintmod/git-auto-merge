#!/usr/bin/env python

import argparse
import logging
import os
import re
import sys
from distutils.version import LooseVersion
from subprocess import CalledProcessError

import utils

# pylint: disable=invalid-name
log = logging.getLogger("gitflow_merge")

# pylint: disable=anomalous-backslash-in-string,line-too-long
SEMVER_PATTERN = r"(?:(\d+\.[.\d]*\d+))"


def is_semver(version_string):
    return re.match(SEMVER_PATTERN, version_string) is not None


class VersionedBranch:
    prefix = ""
    version = ""

    def __init__(self, prefix, version):
        assert prefix is not None and prefix != ""
        assert version is not None and version != ""
        self.prefix = prefix
        self.version = version

    def __str__(self):
        return self.prefix + self.version

    def __repr__(self):
        return self.prefix + self.version

    def __lt__(self, item):
        return LooseVersion(self.version) < LooseVersion(item.version)


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
        "git branch -r | grep -E '(origin/main|origin/master)' | sed 's|origin/||'"
    )
    main_branch_name = utils.execute_shell(command)
    return main_branch_name


def get_branch_list():
    command = "git branch -r | sed 's|origin/||' | grep -v HEAD"
    branches = utils.execute_shell(command)
    return branches


def get_branch_list_for_prefix(prefix, versioned=False, regex_str=None):
    regex_str = regex_str or prefix + ".*"
    branches_string = get_branch_list()
    branches = branches_string.split("\n")
    while "" in branches:
        branches.remove("")
    log.debug("split branches = %s", branches)
    branches = [branch.strip() for branch in branches]
    branches = [branch for branch in branches if branch.startswith(prefix)]
    if regex_str:
        branches = [branch for branch in branches if re.match(regex_str, branch)]
    if versioned:
        branches = get_versioned(branches, prefix)
    return branches


def get_merge_down_branch_list():
    main_branch_name = get_main_branch_name()
    hotfix_versioned = get_branch_list_for_prefix(
        "hotfix/", versioned=True, regex_str=f"hotfix/{SEMVER_PATTERN}"
    )
    log.debug("hotfix_versioned = %s", hotfix_versioned)
    releases = get_branch_list_for_prefix(
        "release/", versioned=True, regex_str=f"release/{SEMVER_PATTERN}"
    )
    release_next = get_branch_list_for_prefix(
        "release/next", versioned=False, regex_str="release/next"
    )
    log.debug("releases = %s", releases)
    all_versioned = hotfix_versioned + releases
    all_versioned.sort()
    log.debug("all_versioned = %s", all_versioned)
    all_versioned = convert_versioned_to_strings(all_versioned)
    log.debug("sorted stringed all_versioned = %s", all_versioned)
    branches = [main_branch_name, "staging"] + all_versioned
    branches = branches + release_next + ["develop"]
    return branches


def get_feature_branch_list():
    features = get_branch_list_for_prefix("feature/")
    log.debug("features = %s", features)
    return features


def get_unversioned_hotfix_branch_list():
    features = get_branch_list_for_prefix("hotfix", False, "hotfix/(?![0-9]).*")
    log.debug("unversioned hotfix = %s", features)
    return features


def get_versioned(branches, prefix):
    versions = []
    for branch in branches:
        version = branch.replace(prefix, "")
        versions.append(VersionedBranch(prefix, version))
    return versions


def convert_versioned_to_strings(branches):
    if branches is None:
        return []
    for idx, item in enumerate(branches):
        branches[idx] = str(item)
    return branches


def init():
    parser = argparse.ArgumentParser(
        prog="gitflow-merge", description="Merge git flow branches down"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", help="log everything to the console"
    )
    parser.add_argument(
        "--dry-run", "-d", action="count", help="dry run. This will not push to github."
    )
    args = parser.parse_args()
    verbosity = 0 if args.verbose == "None" else args.verbose
    configure_logging(verbosity)


def get_repo_list():
    return_val = ""
    if "REPO_LIST" in os.environ:
        return_val = os.environ["REPO_LIST"]
    return return_val.split(",")


def fetch_all():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    command = ""
    for repo in repo_list:
        log.info("Fetching repo = %s", repo)
        command = f"git clone git@github.com:flowcast/{repo}.git"
        command += f" || cd {repo} && git fetch --prune && cd .."
        utils.execute_shell(command)
    os.chdir("..")


def merge_down():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    errors = []
    for repo in repo_list:
        os.chdir(repo)
        log.debug("repo = %s", repo)
        branches = get_merge_down_branch_list()
        branches_length = len(branches)
        idx = 1
        while idx < branches_length:
            merge_from = branches[idx - 1]
            merge_to = branches[idx]
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
                    log.info("Pushing to origin/%s", merge_to)
                    utils.execute_shell("git push")
                else:
                    log.info("Nothing to do: %s", message)

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
        os.chdir(repo)
        log.debug("repo = %s", repo)
        branches = get_feature_branch_list()
        for branch in branches:
            log.info("Merging from develop to %s in repo %s", branch, repo)
            command = "git reset --hard HEAD"
            command += f" && git clean -fdx && git checkout {branch}"
            command += f" && git reset --hard origin/{branch}"
            command += " && git submodule update --init --recursive"
            utils.execute_shell(command)
            message = ""
            try:
                message = utils.execute_shell("git merge origin/develop")
            except CalledProcessError as e:
                log.info("Merging failed from develop to %s in repo %s", branch, repo)
                errors.append(MergeProblem(repo, "develop", branch, e))
            else:
                if "Already up to date" not in message:
                    log.info("Pushing to origin/%s", branch)
                    utils.execute_shell("git push")
                else:
                    log.info("Nothing to do: %s", message)
        os.chdir("..")
    os.chdir("..")
    return errors


def merge_master_to_unversioned_hotfix_branches():
    repo_list = get_repo_list()
    os.makedirs("repos", exist_ok=True)
    os.chdir("repos")
    errors = []
    for repo in repo_list:
        os.chdir(repo)
        main_branch_name = get_main_branch_name()
        log.debug("repo = %s", repo)
        branches = get_unversioned_hotfix_branch_list()
        for branch in branches:
            log.info("Merging from %s to %s in repo %s", main_branch_name, branch, repo)
            command = "git reset --hard HEAD"
            command += f" && git clean -fdx && git checkout {branch}"
            command += f" && git reset --hard origin/{branch}"
            command += " && git submodule update --init --recursive"
            utils.execute_shell(command)
            message = ""
            try:
                message = utils.execute_shell(f"git merge origin/{main_branch_name}")
            except CalledProcessError as e:
                log.info(
                    "Merging failed from %s to %s in repo %s",
                    main_branch_name,
                    branch,
                    repo,
                )
                errors.append(MergeProblem(repo, main_branch_name, branch, e))
            else:
                if "Already up to date" not in message:
                    log.info("Pushing to origin/%s", branch)
                    utils.execute_shell("git push")
                else:
                    log.info("Nothing to do: %s", message)
        os.chdir("..")
    os.chdir("..")
    return errors


def merge_all():
    unversioned_errors = merge_master_to_unversioned_hotfix_branches()
    down_errors = merge_down()
    feature_errors = merge_develop_to_feature_branches()
    return unversioned_errors + down_errors + feature_errors


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


def set_git_config_push_matching():
    utils.execute_shell("git config --global push.default current")


def main():
    validate_environment()
    set_git_config_push_matching()
    init()
    fetch_all()
    errors = merge_all()
    handle_errors(errors)


if __name__ == "__main__":
    main()
