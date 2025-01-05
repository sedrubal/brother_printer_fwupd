"""
Script to update the firmware of some Brother printers (e. g. MFC).
"""

import argparse
import logging
import sys
import typing
import webbrowser

import termcolor

from . import ISSUE_URL
from .common import common_args, printer_info_args
from .firmware_downloader import fw_downloader_args, get_info_and_download_fw
from .firmware_uploader import fw_uploader_args, upload_fw
from .models import SNMPPrinterInfo
from .snmp_info import get_snmp_info_sync, snmp_args
from .utils import CONSOLE_LOG_HANDLER, LOGGER, GitHubIssueReporter

try:
    from .autodiscovery import PrinterDiscoverer

    PRINTER_DISCOVERER: typing.Optional[typing.Type[PrinterDiscoverer]] = PrinterDiscoverer
except ImportError:
    PRINTER_DISCOVERER = None

if typing.TYPE_CHECKING:
    from .models import IPAddress


def main():
    """Run the program."""

    def handler_cb(report_url: str):
        LOGGER.error("This might be a bug.")

        while True:
            ret = (
                input(
                    termcolor.colored(
                        "Do you want to open an issue on Github? [yN] ", color="yellow"
                    )
                )
                .strip()
                .lower()
            )

            if ret.lower() == "y":
                webbrowser.open(report_url)

                return
            elif ret.lower() == "n" or not ret:
                return

    try:
        with GitHubIssueReporter(
            logger=LOGGER,
            issue_url=ISSUE_URL,
            handler_cb=handler_cb,
        ) as issue_reporter:
            run(issue_reporter)
    except KeyboardInterrupt:
        print()
        LOGGER.critical("Quit")
        sys.exit(0)


def run(issue_reporter: GitHubIssueReporter):
    """Do a firmware upgrade."""
    args = parse_args()

    issue_reporter.set_context_data("--community", args.community)
    issue_reporter.set_context_data("--fw-dir", str(args.fw_dir))
    issue_reporter.set_context_data("--os", args.os)
    issue_reporter.set_context_data("--download-only", args.download_only)
    issue_reporter.set_context_data("--debug", args.debug)

    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    printer_ip: "typing.Optional[IPAddress]" = args.ip
    upload_port: typing.Optional[int] = args.pdl_ds_port
    use_snmp = not args.model or not args.serial or not args.spec or not args.fw_versions
    printer_ip_required = use_snmp or not args.download_only

    if not printer_ip and printer_ip_required:
        LOGGER.info("Discovering printer via MDNS.")
        assert PRINTER_DISCOVERER
        discoverer = PRINTER_DISCOVERER()
        mdns_printer_info = discoverer.run_cli()

        if mdns_printer_info:
            printer_ip = mdns_printer_info.ip_addr
            if not upload_port:
                upload_port = mdns_printer_info.port

    if not printer_ip and printer_ip_required:
        LOGGER.critical("No printer given or found.")
        sys.exit(1)

    if printer_ip:
        issue_reporter.set_context_data("--printer", str(printer_ip))

    if use_snmp:
        LOGGER.info("Querying printer info via SNMP.")
        assert printer_ip, "Printer IP is required but not given."
        printer_info: SNMPPrinterInfo = get_snmp_info_sync(
            target=printer_ip, community=args.community, port=args.snmp_port
        )
    else:
        printer_info = SNMPPrinterInfo.from_args(args)

    if printer_info.model:
        issue_reporter.set_context_data("--model", printer_info.model)

    if printer_info.serial:
        issue_reporter.set_context_data("--serial", printer_info.serial)

    if printer_info.spec:
        issue_reporter.set_context_data("--spec", printer_info.spec)

    if printer_info.fw_versions:
        issue_reporter.set_context_data(
            "--fw-versions",
            [str(fw_version) for fw_version in printer_info.fw_versions],
        )

    versions_str = ", ".join(str(fw_info) for fw_info in printer_info.fw_versions)
    LOGGER.success(
        "%s %s with following firmware version(s): %s",
        "Detected" if use_snmp else "Using",
        printer_info.model,
        versions_str,
    )
    LOGGER.info("Querying firmware download URL from Brother update API.")

    for fw_part in printer_info.fw_versions:
        fw_file_path = get_info_and_download_fw(
            printer_info=printer_info,
            fw_part=fw_part,
            os=args.os,
            fw_dir=args.fw_dir,
        )

        if not fw_file_path:
            continue

        if args.download_only:
            LOGGER.info("Skipping firmware upload due to --download-only")
        else:
            assert printer_ip, "Printer IP is required but not given"
            try:
                upload_fw(
                    target=printer_ip,
                    port=args.pdl_ds_port,
                    fw_file_path=fw_file_path,
                )
            except OSError as err:
                LOGGER.error(
                    "Could not upload firmware %s to update part %s: %s",
                    fw_file_path,
                    fw_part,
                    str(err),
                )

                continue

            input("Continue? ")

    LOGGER.success("Done.")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
    )

    common_args(parser, ip_required=not PRINTER_DISCOVERER)
    snmp_args(parser)
    printer_info_args(parser)
    fw_downloader_args(parser)
    fw_uploader_args(parser, set_pdl_ds_port_default=not PRINTER_DISCOVERER)

    parser.add_argument(
        "--download-only",
        dest="download_only",
        action="store_true",
        help=(
            "Do no install update but download firmware and save it"
            " under the directory path given with --fw-dir."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
