"""Receive printer info via SNMP."""

import argparse
import asyncio  # pylint: disable=import-outside-toplevel
import ipaddress
import logging
import re
import sys
import typing

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    bulk_cmd,
    is_end_of_mib,
)

from .common import common_args
from .models import FWInfo, IPAddress, SNMPPrinterInfo
from .utils import CONSOLE_LOG_HANDLER, DEFAULT_SNMP_PORT, LOGGER, get_default_port

SNMP_ROOT_OID = "1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2"

SNMP_RE = re.compile(r'(?P<name>[A-Z]+) ?= ?"(?P<value>.*)"')


async def snmp_walk(
    target: IPAddress,
    community: str = "public",
    port: int = DEFAULT_SNMP_PORT,
    root_oid: str = SNMP_ROOT_OID,
) -> typing.AsyncGenerator[str, None]:
    """Do a SNMP walk over a MIB given by it's start OID."""

    if isinstance(target, str):
        target = ipaddress.ip_address(target)

    if isinstance(target, ipaddress.IPv6Address):
        udp_target = await Udp6TransportTarget.create((str(target), port))
    elif isinstance(target, ipaddress.IPv4Address):
        udp_target = await UdpTransportTarget.create((str(target), port))
    else:
        assert False

    engine = SnmpEngine()
    var_binds = [ObjectType(ObjectIdentity(root_oid))]

    while True:
        error_indication, error_status, error_index, var_bind_table = await bulk_cmd(
            engine,
            CommunityData(community, mpModel=0),
            udp_target,
            ContextData(),
            0,
            50,
            *var_binds,
        )

        if error_indication:
            LOGGER.critical("%s", error_indication)
            sys.exit(1)
        elif error_status:
            if is_end_of_mib(var_bind_table):
                break
            LOGGER.critical(
                "%s at %s",
                error_status.prettyPrint(),
                var_binds[int(error_index) - 1][0] if error_index else "?",
            )
        else:
            for var_bind in var_bind_table:
                LOGGER.debug(" = ".join([x.prettyPrint() for x in var_bind]))
                # TODO this is ugly
                payload = str(var_bind[1]).strip()

                if not payload:
                    break

                yield payload

        var_binds = var_bind_table

        if is_end_of_mib(var_binds):
            break


async def get_snmp_info(
    target: IPAddress,
    community: str = "public",
    port: int = DEFAULT_SNMP_PORT,
) -> SNMPPrinterInfo:
    """
    Get the required info about the printer via SNMP.

    Equals to:
    snmpwalk -v 2c -c public lp.local 1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2
    :return: A tuple of:
        - the model / series
        - the spec
        - a list of firmware infos, which are tuples of the id and their version.
        (Whatever this information means).
    """
    printer_info = SNMPPrinterInfo()
    firm_id: typing.Optional[str] = None
    firm_ver: typing.Optional[str] = None

    async for payload in snmp_walk(target, community, port, SNMP_ROOT_OID):
        match = SNMP_RE.match(payload)

        if not match:
            LOGGER.critical('Payload "%s" does not match the regex.', payload)

            continue
            #  sys.exit(1)
        name = match.group("name")
        value = match.group("value")

        if name == "MODEL":
            printer_info.model = value
        elif name == "SERIAL":
            printer_info.serial = value
        elif name == "SPEC":
            printer_info.spec = value
        elif name in ("FIRMID", "FIRMVER"):
            if name == "FIRMID":
                firm_id = value
            elif name == "FIRMVER":
                firm_ver = value

            if firm_id is not None and firm_ver is not None:
                printer_info.fw_versions.append(FWInfo(firmid=firm_id, firmver=firm_ver))
                firm_id = None
                firm_ver = None
        else:
            LOGGER.debug("Ignoring SNMP info %s=%s", name, value)

    if firm_id is not None or firm_ver is not None:
        LOGGER.critical(
            "Did not receive firmid or firmver from printer via SNMP: firm_id=%s, firm_ver=%s",
            firm_id,
            firm_ver,
        )
        sys.exit(1)

    return printer_info


def get_snmp_info_sync(
    target: IPAddress,
    community: str = "public",
    port: int = DEFAULT_SNMP_PORT,
) -> SNMPPrinterInfo:
    """Synchoronous version of get_snmp_info."""
    return asyncio.run(get_snmp_info(target=target, community=community, port=port))


def snmp_args(parser: argparse.ArgumentParser) -> None:
    """Add command line arguments for SNMP to an argparse parser."""
    parser.add_argument(
        "-c",
        "--community",
        dest="community",
        default="public",
        help="SNMP Community string for the printer (default: '%(default)s').",
    )
    parser.add_argument(
        "--snmp-port",
        dest="snmp_port",
        metavar="port",
        type=int,
        default=get_default_port("snmp"),
        help="The UDP port for SNMP at the printer (default: %(default)s).",
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
    )

    common_args(parser, ip_required=True)
    snmp_args(parser)

    return parser.parse_args()


def main() -> None:
    """Run the SNMP info module."""

    args = parse_args()

    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    result = get_snmp_info_sync(
        target=args.ip,
        community=args.community,
        port=args.snmp_port,
    )
    LOGGER.success("%s", result)
