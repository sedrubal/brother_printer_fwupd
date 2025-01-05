"""Test the utils module."""

import logging
import unittest

from brother_printer_fwupd.utils import sluggify


class TestUtils(unittest.TestCase):
    """Test the utils module."""

    def test_sluggify(self):
        """Test the sluggify function."""
        self.assertEqual(sluggify("Hello World!"), "hello_world")
        self.assertEqual(sluggify("../foo/bar.exe"), "foobarexe")

    def test_logger(self):
        """Test modifications to the logging module."""
        self.assertEqual(logging.SUCCESS, 25)  # pylint: disable=no-member
        self.assertTrue(hasattr(logging.Logger, "success"))
