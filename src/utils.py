from subprocess import PIPE, STDOUT, CalledProcessError, run

from loguru import logger as log


def execute_shell(command, is_shell=True, cwd=".", suppress_errors=False):
    output = ""
    log.debug("--- executing shell command ---")
    log.debug("setting working dir to: {}", cwd)
    log.info("command: {}", str(command))
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
        log.debug("proc = {}", str(proc))
        output = proc.stdout.strip()
        log.info("output = {}", output)
    except CalledProcessError as err:
        log.error(
            "\nError Info:\nerror code = {}\ncmd {}\nerror message:{}",
            err.returncode,
            err.cmd,
            err.output,
        )
        if not suppress_errors:
            raise
    finally:
        log.debug("---- shell execution finished ---")
    return output
