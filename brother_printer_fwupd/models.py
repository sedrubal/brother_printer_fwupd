"""Types and model classes / definitions."""

import argparse
import ipaddress
import typing
from dataclasses import dataclass, field

import termcolor

IPAddress = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


@dataclass
class FWInfo:
    """Firmware fragment info."""

    firmid: str
    firmver: str

    def __str__(self):
        return f"{self.firmid}@{self.firmver}"

    @classmethod
    def from_str(cls, value: str):
        """Parse FW info from string from command line argument."""
        try:
            firmid, firmver = value.split("@", 1)
        except ValueError as err:
            raise argparse.ArgumentTypeError(
                termcolor.colored(
                    f"Invalid firmware ID {value}. Format: firmid@firmver",
                    "red",
                )
            ) from err
        return cls(firmid, firmver)


@dataclass
class SNMPPrinterInfo:
    """Information about a printer."""

    model: typing.Optional[str] = field(default=None)
    serial: typing.Optional[str] = field(default=None)
    spec: typing.Optional[str] = field(default=None)
    fw_versions: list[FWInfo] = field(default_factory=list)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "SNMPPrinterInfo":
        """Create a printer info instance from command line arguments."""
        return cls(
            model=args.model,
            serial=args.serial,
            spec=args.spec,
            fw_versions=args.fw_versions,
        )


@dataclass
class MDNSPrinterInfo:
    """Information about a printer received via MDNS."""

    ip_addr: IPAddress
    name: str
    port: typing.Optional[int]
    product: typing.Optional[str]
    note: typing.Optional[str]
    uuid: typing.Optional[str]
