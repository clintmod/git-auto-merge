import logging
from subprocess import PIPE, STDOUT, CalledProcessError, run

# pylint: disable=invalid-name
log = logging.getLogger("git_auto_merge.utils")


def execute_shell(command, is_shell=True, cwd=".", suppress_errors=False):
    output = ""
    log.debug("--- executing shell command ----")
    log.debug("setting working dir to: %s", cwd)
    log.info("command: %s", str(command))
    try:
        cp = run(
            command,
            shell=is_shell,
            cwd=cwd,
            stderr=STDOUT,
            check=True,
            stdout=PIPE,
            universal_newlines=True,
        )
        log.debug("cp = %s", str(cp))
        output = cp.stdout.strip()
        log.info("output = %s", output)
    except CalledProcessError as err:
        log.error(
            "Error Info:\nerror code = %s\ncmd %s\nerror message:%s",
            err.returncode,
            err.cmd,
            err.output,
        )
        if not suppress_errors:
            raise
    finally:
        log.debug("---- shell execution finished ---")
    return output
