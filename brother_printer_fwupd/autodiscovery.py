"""Auto detect printer using zeroconf."""

# pylint: disable=C0103
# pylint: disable=R1723

import argparse
import ipaddress
import logging
import typing
from typing import Optional

import termcolor
import zeroconf

from .common import common_args
from .models import MDNSPrinterInfo
from .utils import CONSOLE_LOG_HANDLER, LOGGER, clear_screen

ZEROCONF_SERVICE_DOMAIN = "_pdl-datastream._tcp.local."

termcolor.ATTRIBUTES["italic"] = 3  # type: ignore


class PrinterDiscoverer(zeroconf.ServiceListener):
    """Discoverer of printers."""

    def __init__(self) -> None:
        self._printers: list[MDNSPrinterInfo] = []
        self._zc = zeroconf.Zeroconf()
        self._invalid_answer = False
        self._browser: Optional[zeroconf.ServiceBrowser] = None

    def remove_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Called when a service disappears."""
        LOGGER.debug("Service %s removed", name)
        self._remove_printer_infos_by_name(name)
        self._update_screen()

    @staticmethod
    def _zc_info_to_mdns_printer_infos(
        service_info: zeroconf.ServiceInfo,
        name: str,
    ) -> typing.Iterator[MDNSPrinterInfo]:
        """Convert the info from zeroconf into MDNSPrinterInfo instances."""

        for addr in service_info.addresses:
            try:
                ip_addr = ipaddress.ip_address(addr)
            except ValueError as err:
                LOGGER.critical(err)

                return

            product_raw = service_info.properties.get(b"product", None)

            if product_raw:
                product = product_raw.decode("utf8")
            else:
                product = None

            note_raw = service_info.properties.get(b"note", None)

            if note_raw:
                note = note_raw.decode("utf8")
            else:
                note = None

            uuid_raw = service_info.properties.get(b"UUID", None)

            if uuid_raw:
                uuid = uuid_raw.decode("utf8")
            else:
                uuid = None

            yield MDNSPrinterInfo(
                ip_addr=ip_addr,
                name=name,
                port=service_info.port,
                product=product,
                note=note,
                uuid=uuid,
            )

    def _remove_printer_infos_by_name(self, name: str):
        """Remove all known printer infos by their name."""
        printers_to_remove = [p for p in self._printers if p.name == name]

        for printer in printers_to_remove:
            self._printers.remove(printer)

    def _add_printer_infos(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Add printer info."""
        service_info = zc.get_service_info(type_, name)

        if not service_info:
            LOGGER.error(
                "Received empty add_service request. Ignoring: %s %s",
                type_,
                name,
            )

            return

        for printer_info in PrinterDiscoverer._zc_info_to_mdns_printer_infos(service_info, name):
            self._printers.append(printer_info)

        self._update_screen()

    def add_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Called, when a new service appears."""
        LOGGER.debug("Service %s added", name)
        self._add_printer_infos(zc, type_, name)

    def update_service(self, zc: zeroconf.Zeroconf, type_: str, name: str):
        """Update a service."""
        LOGGER.debug("Service {name} updated")
        self._remove_printer_infos_by_name(name)
        self._add_printer_infos(zc, type_, name)

    def _update_screen(self):
        """Update the CLI printer selection screen."""
        clear_screen()

        termcolor.cprint("Choose a printer", attrs=["bold"], end=" ")
        termcolor.cprint("Scanning Network via MDNS...", attrs=["italic"])

        if self._invalid_answer:
            LOGGER.error("Invalid answer.")
        print()

        if self._printers:
            max_str_len = len(str(len(self._printers) - 1))
            max_ip_len = max(len(str(info.ip_addr)) for info in self._printers)

            for i, info in enumerate(self._printers):
                num_str = termcolor.colored(
                    f"[{str(i).rjust(max_str_len)}]", color="blue", attrs=["bold"]
                )
                ip_addr_str = termcolor.colored(str(info.ip_addr).rjust(max_ip_len), color="yellow")
                port_str = termcolor.colored(f"Port {info.port}")
                name_str = termcolor.colored(info.name, color="white")
                product_str = (
                    termcolor.colored(f"- Product: {info.product}") if info.product else ""
                )
                note_str = (
                    termcolor.colored(f"- Note: {info.note}", attrs=["italic"]) if info.note else ""
                )
                uuid_str = (
                    termcolor.colored(f"- UUID: {info.uuid}", attrs=["italic"]) if info.uuid else ""
                )
                print(
                    " ".join(
                        (
                            num_str,
                            ip_addr_str,
                            port_str,
                            name_str,
                            product_str,
                            note_str,
                            uuid_str,
                        )
                    )
                )

            print()

            if len(self._printers) > 1:
                range_str = f"[0 - {len(self._printers) - 1}; Enter: Cancel]"
            else:
                range_str = "[0 / Enter: Use first entry; ^C: Cancel]"

            range_str = termcolor.colored(range_str, color="blue")
            termcolor.cprint(
                f"Your choice {range_str}:",
                attrs=["bold"],
                end=" ",
                flush=True,
            )
        else:
            termcolor.cprint("No printers found yet.", "yellow", attrs=["italic"], end=" ")
            termcolor.cprint(
                "Run with --printer=<ip> to skip autodiscovery. [Enter: Cancel]",
                attrs=["italic"],
            )

    def run_cli(self) -> Optional[MDNSPrinterInfo]:
        """Run as interactive terminal application."""
        self._run()
        self._update_screen()

        try:
            while True:
                inpt = input()

                if not inpt.strip():
                    # Enter
                    if len(self._printers) == 1:
                        return self._printers[0]
                    else:
                        return None

                try:
                    return self._printers[int(inpt)]
                except (ValueError, IndexError):
                    self._invalid_answer = True
                    self._update_screen()
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        finally:
            self._stop()
            clear_screen()

    def _run(self):
        """Auto detect printer using zeroconf."""
        self._browser = zeroconf.ServiceBrowser(
            zc=self._zc,
            type_=ZEROCONF_SERVICE_DOMAIN,
            handlers=self,
        )

    def _stop(self):
        """Stop discovering."""
        self._zc.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
    )

    common_args(parser, ip_required=False)

    return parser.parse_args()


def main() -> None:
    """Run the autodiscoverer module."""
    args = parse_args()
    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    discoverer = PrinterDiscoverer()
    mdns_printer_info = discoverer.run_cli()
    LOGGER.success("Found %s", mdns_printer_info)
