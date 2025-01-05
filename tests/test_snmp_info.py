"""Unit tests for SNMP info."""

import ipaddress
import unittest

from brother_printer_fwupd.models import FWInfo
from brother_printer_fwupd.snmp_info import get_snmp_info_sync


class TestSNMPInfo(unittest.TestCase):
    """Test the snmp_info module."""

    def test_get_snmp_info_sync(self):
        """
        Test the get_snmp_info_sync function.

        This requires that the simulator is running.
        """
        info = get_snmp_info_sync(
            target=ipaddress.IPv4Address("127.0.0.1"),
            port=1161,
        )
        self.assertEqual(info.model, "MFC-9332CDW")
        self.assertEqual(info.serial, "E01234A5J678901")
        self.assertEqual(info.spec, "0403")
        self.assertEqual(
            info.fw_versions,
            [
                FWInfo(firmid="MAIN", firmver="R2311081154:E7E5"),
                FWInfo(firmid="SUB1", firmver="1.05"),
                FWInfo(firmid="SUB2", firmver="R2311081800"),
            ],
        )
