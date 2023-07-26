from subprocess import PIPE, STDOUT, CalledProcessError, run

from loguru import logger


def execute_shell(command, is_shell=True, cwd=".", suppress_errors=False):
    output = ""
    logger.debug("--- executing shell command ----")
    logger.debug("setting working dir to: {}", cwd)
    logger.info("command: {}", str(command))
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
        logger.debug("proc = {}", str(proc))
        output = proc.stdout.strip()
        logger.info("output = {}", output)
    except CalledProcessError as err:
        logger.error(
            "\nError Info:\nerror code = {}\ncmd {}\nerror message:{}",
            err.returncode,
            err.cmd,
            err.output,
        )
        if not suppress_errors:
            raise
    finally:
        logger.debug("---- shell execution finished ---")
    return output
