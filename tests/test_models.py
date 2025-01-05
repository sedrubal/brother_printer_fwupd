"""Test the data structures."""

import argparse
import unittest

from brother_printer_fwupd.models import FWInfo, SNMPPrinterInfo


class TestModels(unittest.TestCase):
    """Test the models file."""

    def test_fwinfo(self):
        """Test the FWInfo model."""
        firmid = "MAIN"
        firmver = "10.1.1"
        value = f"{firmid}@{firmver}"
        fw = FWInfo.from_str(value)
        self.assertEqual(str(fw), value)
        self.assertEqual(fw.firmid, firmid)
        self.assertEqual(fw.firmver, firmver)

    def test_snmp_printer_info(self):
        """Test the SNMPPrinterInfo model."""
        model = "DUMMY"
        serial = "E01234A5J678901"
        spec = "0403"
        fw_version = FWInfo.from_str("SUB2@R2311081154:E7E5")

        args = argparse.Namespace()
        args.model = model
        args.serial = serial
        args.spec = spec
        args.fw_versions = [fw_version]

        printer_info = SNMPPrinterInfo.from_args(args)

        self.assertEqual(printer_info.model, model)
        self.assertEqual(printer_info.serial, serial)
        self.assertEqual(printer_info.spec, spec)
        self.assertEqual(printer_info.fw_versions, [fw_version])
