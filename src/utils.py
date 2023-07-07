import logging
from subprocess import PIPE, STDOUT, CalledProcessError, run

LOG = logging.getLogger("git_auto_merge.utils")


def execute_shell(command, is_shell=True, cwd=".", suppress_errors=False):
    output = ""
    LOG.debug("--- executing shell command ----")
    LOG.debug("setting working dir to: %s", cwd)
    LOG.info("command: %s", str(command))
    try:
        proc = run(
            command,
            shell=is_shell,
            cwd=cwd,
            stderr=STDOUT,
            check=True,
            stdout=PIPE,
            universal_newlines=True,
        )
        LOG.debug("proc = %s", str(proc))
        output = proc.stdout.strip()
        LOG.info("output = %s", output)
    except CalledProcessError as err:
        LOG.error(
            "\nError Info:\nerror code = %s\ncmd %s\nerror message:%s",
            err.returncode,
            err.cmd,
            err.output,
        )
        if not suppress_errors:
            raise
    finally:
        LOG.debug("---- shell execution finished ---")
    return output
