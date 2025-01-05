"""Upload firmware to the brinter."""

import argparse
import logging
import socket
from pathlib import Path

from .common import common_args
from .models import IPAddress
from .utils import (
    CONSOLE_LOG_HANDLER,
    DEFAULT_PDL_DATASTREAM_PORT,
    LOGGER,
    get_default_port,
)


def upload_fw(
    target: IPAddress,
    port: int = DEFAULT_PDL_DATASTREAM_PORT,
    fw_file_path: Path = Path("firmware.djf"),
):
    """
    Upload the firmware to the printer via PDL Datastream / JetDirect.

    Equals:
    ```
    cat LZ5413_P.djf | nc lp.local 9100
    ```
    """

    LOGGER.info(
        "Uploading firmware file %s to printer via jetdirect at %s:%i.",
        fw_file_path,
        target,
        port,
    )

    addr_info = socket.getaddrinfo(str(target), port, 0, 0, socket.SOL_TCP)[0]

    with socket.socket(addr_info[0], addr_info[1], 0) as sock:
        sock.connect(addr_info[4])

        with fw_file_path.open("rb") as fw_file:
            sock.sendfile(fw_file)

    LOGGER.success("Successfully uploaded the firmware file %s", fw_file_path)


def fw_uploader_args(parser: argparse.ArgumentParser, set_pdl_ds_port_default: bool = True) -> None:
    """Add command line arguments for the firmware uploader to an argparse parser."""
    if set_pdl_ds_port_default:
        default_blurb = "default: %(default)s"
    else:
        default_blurb = "determined using MDNS autodiscovery"

    parser.add_argument(
        "--pdl-ds-port",
        dest="pdl_ds_port",
        metavar="port",
        type=int,
        default=get_default_port("pdl-datastream") if set_pdl_ds_port_default else None,
        help=f"The TCP port for PDL Datastream / jetdirect at the printer ({default_blurb}).",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
    )

    common_args(parser, ip_required=True)
    fw_uploader_args(parser, set_pdl_ds_port_default=True)

    parser.add_argument(
        "fw_file",
        type=Path,
        help="The firmware file to send to the printer.",
    )

    return parser.parse_args()


def main():
    """Run the firmware uploader."""
    args = parse_args()

    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    upload_fw(
        target=args.ip,
        port=args.pdl_ds_port,
        fw_file_path=args.fw_file,
    )


if __name__ == "__main__":
    main()
