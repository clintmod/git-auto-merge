#!/usr/bin/env python
import json
import os
import re
import sys
from subprocess import CalledProcessError
from typing import Optional, Self

import click
import jsonpickle
from loguru import logger as log
from packaging.version import Version

import utils

# pylint: disable=anomalous-backslash-in-string
SEMVER_PATTERN = r"(\d+\.\d+\.\d+)"


class MergeItem:
    branch_name = ""
    version = ""
    group = ""
    upstream: Optional[Self] = None
    downstream = []

    def __init__(self, group, branch_name="", version="", upstream=None, downstream=None):
        self.branch_name = branch_name
        self.upstream = upstream
        self.group = group
        self.version = version
        self.downstream = downstream or []

    def add_downstream_branch(self, branch, group, version=""):
        assert branch is not None
        assert self.branch_name != branch
        merge_item = MergeItem(branch_name=branch, group=group, version=version, upstream=self)
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


class MergeError:
    merge_from = ""
    merge_to = ""
    error: CalledProcessError | None = None
    conflict = False
    emails = []

    def __init__(self, merge_from, merge_to, error, conflict=False, emails=None):
        self.merge_from = merge_from
        self.merge_to = merge_to
        self.error = error
        self.conflict = conflict
        self.emails = emails or []

    def __json__(self):
        return_val = {}
        return_val["merge_from"] = self.merge_from
        return_val["merge_to"] = self.merge_to
        if self.error:
            return_val["error"] = self.error.output
        return_val["conflict"] = self.conflict
        return_val["emails"] = self.emails
        return return_val

    def __str__(self):
        return_val = "An error occurred merging"
        return_val += f" from {self.merge_from} to {self.merge_to}."
        if self.error:
            first_two_lines = self.error.output.split("\n")[:2]
            return_val += f"\nThe error message was:\n{first_two_lines}"
        return_val += f"\nThe following emails were found via the diff: {self.emails}"
        return return_val


def configure_logging():
    log_level = get_log_level()
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss,SSS}</green> <level>{level: <8}</level>"
    log_format += "<cyan>src/{file}:{line}</cyan> : "
    log_format += "<level>{message}</level>"
    log.remove()
    log.add(sink=sys.stderr, format=log_format, level=log_level)
    return log_level


def get_merge_items_in_group(merge_item, group):
    return_val = []
    if merge_item and merge_item.group == group:
        return_val.append(merge_item)
        return get_merge_items_in_group(merge_item.upstream, group) + return_val
    return return_val


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
    log.debug("split branches = {}", branches)
    branches = [branch.strip() for branch in branches]
    os.chdir(orig_dir)
    return branches


@click.pass_context
def get_log_level(click_context):
    return_val = click_context.params.get("log_level")
    if return_val is None:
        return_val = "INFO"
    return return_val


@click.pass_context
def get_config_file_name(click_context):
    name = click_context.params.get("config_file_name")
    if name is None:
        name = ".git-auto-merge.json"
    return name


@click.pass_context
def get_repo(click_context):
    return_val = click_context.params.get("repo")
    assert return_val != ""
    return return_val


def get_repo_name():
    repo_name = get_repo().split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return repo_name


@click.pass_context
def get_work_dir(click_context):
    return_val = click_context.params.get("work_dir")
    if return_val is None:
        return_val = "workdir"
    return return_val


def get_repo_path():
    return f"{get_work_dir()}/{get_repo_name()}"


@click.pass_context
def get_dry_run(click_context):
    return click_context.params.get("dry_run")


@click.pass_context
def get_config_branch(click_context):
    return click_context.params.get("config_branch")


@click.pass_context
def get_use_default_plan(click_context):
    return click_context.params.get("use_default_plan")


def clone():
    err = None
    work_dir = get_work_dir()
    os.makedirs(work_dir, exist_ok=True)
    orig_dir = os.getcwd()
    os.chdir(work_dir)
    repo = get_repo()
    repo_name = get_repo_name()
    try:
        log.info("Attempting to clone repo = {}", repo)
        log.warning("This may fail if the repo already exists")
        command = f" git clone {repo}"
        utils.execute_shell(command)
    except CalledProcessError as err:  #  pylint: disable=broad-exception-caught
        if "already exists" in err.output:
            log.info("Trying to fetch repo {} instead", repo)
            command = f"cd {repo_name} && git fetch --prune"
            utils.execute_shell(command)
        else:
            raise
    os.chdir(repo_name)
    default_branch = utils.execute_shell(
        "git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'"
    )
    utils.execute_shell(f"git reset --hard HEAD && git checkout {default_branch} && git pull")
    config_branch = get_config_branch()
    if config_branch is not None:
        log.info("checking out config branch {}", config_branch)
        utils.execute_shell(f"git checkout {config_branch}")
    os.chdir(orig_dir)


def git_push(branch, merge_output):
    dry_run = get_dry_run()
    if dry_run:
        log.info(f"dry run: skipping push for {branch}")
        return False
    if "Already up to date" not in merge_output:
        utils.execute_shell(f"git push origin {branch}")
    else:
        log.info("Nothing to do: {}", merge_output)
    return True


def merge_all(merge_item: MergeItem) -> list[MergeError]:
    errors = []
    assert merge_item is not None
    if merge_item.upstream is not None:
        errors += merge_branches(merge_item.upstream.branch_name, merge_item.branch_name)
    for downstream in merge_item.downstream:
        errors += merge_all(downstream)
    return errors


def merge_branches(merge_from: str, merge_to: str) -> list[MergeError]:
    errors = []
    log.info("Merging from {} to {}", merge_from, merge_to)
    command = "git reset --hard HEAD"
    command += f" && git clean -fdx && git checkout {merge_to}"
    command += f" && git reset --hard origin/{merge_to}"
    command += " && git submodule update --init --recursive"
    utils.execute_shell(command)
    try:
        merge_output = utils.execute_shell(f"git merge origin/{merge_from}")
    except CalledProcessError as err:
        log.error(
            f"Merging failed from {merge_from} to {merge_to} with error: {err.output}",
        )
        merge_error = MergeError(merge_from, merge_to, err)
        if "conflict" in err.output:
            log.info("Merge conflict detected")
            merge_error.conflict = True
            command = f"git log origin/{merge_to}..origin/{merge_from}"
            command += " --no-merges --pretty=format:'%ae' | sort | uniq"
            merge_error.emails = utils.execute_shell(command).split("\n")
        errors.append(merge_error)
    else:
        git_push(merge_to, merge_output)
    return errors


def handle_errors(merge_errors: list[MergeError]):
    if not merge_errors:
        return
    reports_dir = "reports"
    reports_path = os.path.join(reports_dir, "errors.json")
    if os.path.exists(reports_path):
        os.remove(reports_path)
    assert not os.path.exists(reports_path)
    if not os.path.exists(reports_dir):
        os.mkdir(reports_dir)
    log.info("Logging error report")
    for merge_error in merge_errors:
        log.error(merge_error)
    log.info(f"Writing error report to {reports_path}")
    with open(reports_path, "w", encoding="utf-8") as file:
        result = str(jsonpickle.encode(merge_errors, unpicklable=False, indent=2))
        file.write(result)
        log.info("Error report written to {}", reports_path)
    sys.exit(1)


def load_config(path=None):
    config = {}
    config_file_name = get_config_file_name()
    use_default_plan = get_use_default_plan()
    config_file_in_repo_path = f"{get_repo_path()}/{config_file_name}"
    if path:
        config = load_config_from_path(path)
    elif os.path.exists(config_file_name) and use_default_plan:
        config = load_config_from_path(config_file_name)
    elif os.path.exists(config_file_in_repo_path):
        config = load_config_from_path(config_file_in_repo_path)
    else:
        msg = f"No config file found at {config_file_in_repo_path} \
                and --use-default-plan was not specified."
        raise ValueError(msg)
    return config


def load_config_from_path(path):
    log.info("Loading config from path {}", path)
    with open(path, encoding="utf-8") as file:
        config = json.load(file)
    return config


def process_regex_selector_config(regex, branch_list):
    selected_branches = [branch for branch in branch_list if re.search(regex, branch)]
    return selected_branches


def process_versioned_branches(selected_branches, group, upstream: MergeItem):
    versioned_branches = []
    for branch in selected_branches:
        version = VersionedBranch(branch)
        versioned_branches.append(version)
    versioned_branches.sort()
    new_merge_item = upstream
    for branch in versioned_branches:
        new_merge_item = new_merge_item.add_downstream_branch(
            group=group, branch=str(branch), version=branch.version
        )
    return new_merge_item


def process_branches(selected_branches, group, upstream: MergeItem):
    for branch in selected_branches:
        upstream.add_downstream_branch(branch=branch, group=group)


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
    selectors_config, branch_list, upstream: MergeItem, group, sort_type=""
) -> MergeItem:
    log.debug("selectors_config = {}, upstream = {}", selectors_config, upstream)
    return_val = upstream or MergeItem(group=group)
    return_val.group = group
    selected_branches = select_branches(branch_list=branch_list, selectors_config=selectors_config)
    if len(selected_branches) == 0:
        log.warning(f"No branches matched for {selectors_config}")
    if len(selected_branches) == 1:
        if upstream is not None:
            return_val = upstream.add_downstream_branch(branch=selected_branches[0], group=group)
        else:
            return_val.branch_name = str(selected_branches[0])
    else:
        if sort_type == "version":
            return_val = process_versioned_branches(
                selected_branches=selected_branches, group=group, upstream=return_val
            )
        else:
            process_branches(selected_branches=selected_branches, group=group, upstream=return_val)
    return return_val


def process_branches_config(branches_config, branch_list, upstream: MergeItem):
    for group in branches_config:
        branch_config = branches_config[group]
        process_branch_config(
            branch_config=branch_config, branch_list=branch_list, upstream=upstream, group=group
        )


def process_downstream_for_each_config(
    merge_item: MergeItem, group, downstream_for_each_config, branch_list
):
    match_on = downstream_for_each_config.get("matchOn")
    selector_config = downstream_for_each_config.get("matchedSelectors")
    matching_branches = select_branches(branch_list=branch_list, selectors_config=selector_config)
    merge_items_in_group = get_merge_items_in_group(merge_item, merge_item.group)
    for item in merge_items_in_group:
        for branch in matching_branches:
            if match_on == "version":
                versioned_branch = VersionedBranch(branch)
                if item.version == versioned_branch.version:
                    item.add_downstream_branch(branch=branch, group=group)
            if match_on == "branch":
                if branch in item.branch_name:
                    item.add_downstream_branch(branch=branch, group=group)


def process_branch_config(branch_config, branch_list, upstream, group) -> MergeItem:
    selectors_config = branch_config.get("selectors")
    sort_type = branch_config.get("sort")
    merge_item = process_selectors_config(
        selectors_config=selectors_config,
        upstream=upstream,
        branch_list=branch_list,
        sort_type=sort_type,
        group=group,
    )
    downstream_for_each_config = branch_config.get("downstreamForEach")
    if downstream_for_each_config:
        process_downstream_for_each_config(
            merge_item=merge_item,
            group=group,
            downstream_for_each_config=downstream_for_each_config,
            branch_list=branch_list,
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
    plan = process_branch_config(
        branch_config=root_config, branch_list=branch_list, upstream=None, group="root"
    )
    return plan


@click.command(
    context_settings=dict(auto_envvar_prefix="GIT_AUTO_MERGE", max_content_width=500),
    epilog="Check out the docs at https://github.com/clintmod/git-auto-merge for more details",
)
@click.option(
    "-r",
    "--repo",
    required=True,
    help="The git repository to operate on",
)
@click.option(
    "-w",
    "--work-dir",
    default="workdir",
    show_default=True,
    help="The directory to use for the git repo",
)
@click.option(
    "-l",
    "--log-level",
    default="INFO",
    help="The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "-cb",
    "--config-brach",
    default="main",
    show_default=True,
    help="The branch in the git repository to use for the .git-auto-merge.json config file",
)
@click.option(
    "-c",
    "--config-file-name",
    default=".git-auto-merge.json",
    show_default=True,
    help="The name of the config file to use",
)
@click.option(
    "-udp",
    "--use-default-plan",
    is_flag=True,
    default=False,
    show_default=True,
    help="Use the default plan from the .git-auto-merge.json config file in this git repository",
)
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="This mode will do everything except git push",
)
def cli(**args):
    """
    A tool to automatically merge git branches.
    """
    cur_dir = os.getcwd()
    configure_logging()
    log.info("args = {}", args)
    clone()
    config = load_config()
    plan = build_plan(config)
    log.info("Plan: {}", plan)
    os.chdir(f"{get_repo_path()}")
    errors = merge_all(plan)
    os.chdir(cur_dir)
    handle_errors(errors)
    log.info("Merge complete")
