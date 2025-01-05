"""Common helper functions."""

import argparse

from .models import FWInfo


def common_args(parser: argparse.ArgumentParser, ip_required: bool):
    """Add common args to a argparse parser."""
    from . import __version__  # pylint: disable=import-outside-toplevel

    if ip_required:
        blurb = "required, because zeroconf is not available"
    else:
        blurb = "default: autodiscover via mdns"

    parser.add_argument(
        "--ip",
        "--printer",
        required=ip_required,
        dest="ip",
        metavar="host",
        default=None,
        help=f"IP Address or hostname of the printer ({blurb})).",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print debug messages",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )


def printer_info_args(parser: argparse.ArgumentParser, required: bool = False) -> None:
    """
    Add arguments with printer info to an argparse parser.

    These arguments are required, if SNMP was skipped.
    """
    parser.add_argument(
        "--model",
        dest="model",
        required=required,
        type=str,
        help="Skip SNMP scanning by directly specifying the printer model.",
    )
    parser.add_argument(
        "--serial",
        dest="serial",
        required=required,
        type=str,
        help="Skip SNMP scanning by directly specifying the printer serial.",
    )
    parser.add_argument(
        "--spec",
        dest="spec",
        required=required,
        type=str,
        help="Skip SNMP scanning by directly specifying the printer spec.",
    )
    parser.add_argument(
        "--fw",
        "--fw-versions",
        dest="fw_versions",
        nargs="+" if required else "*",
        default=None if required else [],  # In Python 3.10+: list[FWInfo]()
        required=required,
        type=FWInfo.from_str,
        help="Skip SNMP scanning by directly specifying the firmware parts to update.",
    )
