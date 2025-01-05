"""Unittests for autodiscover module."""

import ipaddress
import socket
import unittest

import zeroconf

from brother_printer_fwupd.autodiscovery import (
    ZEROCONF_SERVICE_DOMAIN,
    PrinterDiscoverer,
)

# pylint: disable=protected-access


class TestAutodiscovery(unittest.TestCase):
    """Test the PrinterDiscoverer class."""

    def test_printer_discoverer(self):
        """Test the PrinterDiscoverer class."""
        discoverer = PrinterDiscoverer()

        address = ipaddress.IPv4Address("127.0.0.1")
        pdl_ds_port = 8080

        class DummyZeroconf:
            def get_service_info(self, type_: str, name: str):
                return zeroconf.ServiceInfo(
                    type_,
                    name,
                    addresses=[socket.inet_aton(str(address))],
                    port=pdl_ds_port,
                    properties={
                        b"product": b"DUMMY",
                        b"note": b"Printer",
                    },
                )

        zc = DummyZeroconf()
        name = f"DUMMY.{ZEROCONF_SERVICE_DOMAIN}"
        discoverer.add_service(zc, ZEROCONF_SERVICE_DOMAIN, name)

        self.assertEqual(discoverer._printers[0].name, name)
        self.assertEqual(discoverer._printers[0].ip_addr, address)
        self.assertEqual(discoverer._printers[0].port, pdl_ds_port)
        self.assertEqual(discoverer._printers[0].product, "DUMMY")
        self.assertEqual(discoverer._printers[0].note, "Printer")
