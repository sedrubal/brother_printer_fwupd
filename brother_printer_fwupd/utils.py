"""Some utilities used in other modules."""

# pylint: disable=R1705

import io
import logging
import os
import shlex
import socket
import string
import sys
import traceback
import typing
from pathlib import Path
from urllib.parse import urlencode

import termcolor


class GitHubIssueReporter:
    """Wrapper around code that helps with reporting issues to GitHub."""

    def __init__(
        self,
        logger: logging.Logger,
        issue_url: str,
        handler_cb: typing.Callable[[str], None],
    ):
        self.logger = logger
        self.issue_url = issue_url
        self.handler_cb = handler_cb
        self._handler = logging.StreamHandler(stream=io.StringIO())
        self._handler.setLevel(logging.DEBUG)

        self._context: dict[str, typing.Union[str, bool, list[str]]] = {}

    def __enter__(self):
        self._handler.stream.seek(0)
        self._handler.stream.truncate()
        self.logger.addHandler(self._handler)

        return self

    def __exit__(self, exc_class, exc, tb):
        if not exc_class or exc_class in (SystemExit, KeyboardInterrupt):
            return

        if isinstance(exc, ExceptionGroupCompat):
            LOGGER.error("%s  Errors:", exc.message)

            for err in exc.exceptions:
                LOGGER.error("  - %s", err)
        else:
            LOGGER.error(exc)
        self.logger.removeHandler(self._handler)
        self._handler.stream.seek(0)
        exc_io = io.StringIO()
        traceback.print_exception(exc, file=exc_io)
        exc_io.seek(0)
        report_url = self._generate_github_issue_url(
            title=str(exc),
            log_output=self._handler.stream.read(),
            exception_traceback=exc_io.read(),
        )
        self.handler_cb(report_url)
        sys.exit(1)

    def _generate_github_issue_url(
        self, title: str, log_output: str, exception_traceback: str
    ) -> str:
        """Generate the URL to open an issue on GitLab."""
        prog = Path(sys.argv[0]).name
        cmd = f"{prog} {shlex.join(sys.argv[1:])}"

        emulation_cmd_parts = [prog]

        for key, value in self._context.items():
            if isinstance(value, bool):
                if value is True:
                    emulation_cmd_parts.append(key)
            elif isinstance(value, list):
                emulation_cmd_parts.extend([key, *value])
            else:
                emulation_cmd_parts.extend([key, value])

        emulation_cmd = shlex.join(emulation_cmd_parts)
        emulation_block = (
            ""
            if not self._context
            else f"""
**Command to emulate scenario:**

```sh
{emulation_cmd}
```

"""
        )

        return (
            self.issue_url
            + "?"
            + urlencode(
                {
                    "title": title,
                    "body": f"""
**Description:**

*please describe the issue*

**Command:**

```sh
{cmd}
```
{emulation_block}
**Output:**

```
{log_output}
```

**Exception:**

```python
{exception_traceback}
```
""".strip(),
                }
            )
        )

    def set_context_data(self, key: str, value: typing.Union[str, bool, list[str]]):
        """
        Add some context info that helps crafting a command, which simulates the current scenario.

        Autodetection of most information can be bypassed by using command line arguments.
        """
        self._context[key] = value


def get_running_os() -> (
    typing.Union[typing.Literal["WINDOWS"], typing.Literal["MAC"], typing.Literal["LINUX"]]
):
    """:return: "WINDOWS", "MAC", or "LINUX" according to the currently running OS."""

    if sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
        return "WINDOWS"
    elif sys.platform.startswith("darwin"):
        return "MAC"
    else:
        return "LINUX"


def add_logging_level(level_name: str, level_num: int, method_name: typing.Optional[str] = None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `level_name` becomes an attribute of the `logging` module with the value
    `level_num`. `method_name` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `method_name` is not specified, `level_name.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> add_logging_level('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """

    if not method_name:
        method_name = level_name.lower()

    if hasattr(logging, level_name):
        raise AttributeError(f"{level_name} already defined in logging module")

    if hasattr(logging, method_name):
        raise AttributeError(f"{method_name} already defined in logging module")

    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError(f"{method_name} already defined in logger class")

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(level_num):
            self._log(  # pylint: disable=protected-access
                level_num, message, args, **kwargs
            )

    def log_to_root(message, *args, **kwargs):
        logging.log(level_num, message, *args, **kwargs)

    logging.addLevelName(level_num, level_name)
    setattr(logging, level_name, level_num)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)


add_logging_level("SUCCESS", logging.INFO + 5)


class TerminalFormatter(logging.Formatter):
    """Logging formatter with colors."""

    colors = {
        logging.DEBUG: "grey",
        logging.INFO: "cyan",
        logging.SUCCESS: "green",  # type: ignore  # pylint: disable=no-member
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "red",
    }
    prefix = {
        logging.DEBUG: "[d]",
        logging.INFO: "[i]",
        logging.SUCCESS: "[i]",  # type: ignore  # pylint: disable=no-member
        logging.WARNING: "[!]",
        logging.ERROR: "[!]",
        logging.CRITICAL: "[!]",
    }
    attrs = {
        logging.CRITICAL: ["bold"],
    }

    def __init__(self, fmt="%(message)s"):
        super().__init__(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record):
        return termcolor.colored(
            f"{self.prefix[record.levelno]} {super().format(record)}",
            color=self.colors[record.levelno],
            attrs=self.attrs.get(record.levelno),
        )


class LoggerWithSuccess(logging.Logger):
    """A logger with success() method."""

    def success(self, msg: str, *args, **kwargs) -> None:
        """Log a success message."""


CONSOLE_LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
CONSOLE_LOG_HANDLER.setFormatter(TerminalFormatter())
LOGGER = typing.cast(LoggerWithSuccess, logging.getLogger(name="brother_printer_fwupd"))
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(CONSOLE_LOG_HANDLER)


def clear_screen():
    """Clear the terminal screen."""
    os.system("clear")
    #  print(chr(27) + '[2j')
    #  print('\033c')
    #  print('\x1bc')


def sluggify(value: str) -> str:
    """Convert value to a string that can be safely used as file name."""
    trans_tab = {
        " ": "_",
        "@": "-",
        ":": "-",
    }
    trans = str.maketrans(trans_tab)
    allowed_chars = string.ascii_letters + string.digits + "".join(trans_tab.values())
    assert "/" not in allowed_chars
    assert "." not in allowed_chars
    value = value.strip().lower().translate(trans)
    value = "".join(c for c in value if c in allowed_chars)

    return value


#: The default port for SNMP (UDP)
DEFAULT_SNMP_PORT = 161

#: The default port for PDL Datastream  / jetdirect (TCP)
DEFAULT_PDL_DATASTREAM_PORT = 9100

#: A mapping of service names (according to /etc/services) to port numbers.
DEFAULT_PORTS = {
    "snmp": DEFAULT_SNMP_PORT,
    "pdl-datastream": DEFAULT_PDL_DATASTREAM_PORT,
}


def get_default_port(name: str) -> int:
    """
    Get the default port by service name by querying the system or use a known fallback.

    :raises: `KeyError` if the lookup on the system failed and the service is unknown.
    """
    try:
        return socket.getservbyname(name)
    except OSError:
        return DEFAULT_PORTS[name]


class ExceptionGroupCompat(BaseException):
    """Compatibility for ExceptionGroup (introduced in python 3.11."""

    def __init__(self, msg: str, exceptions: list[Exception]):
        super().__init__(msg)
        self.message = msg
        self.exceptions = exceptions

    def __str__(self) -> str:
        return self.message + "\n - " + "\n - ".join(str(err) for err in self.exceptions)
