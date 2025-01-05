"""Tool to update the firmware of some Brother printers (e. g. MFC)."""

import importlib.metadata as importlib_metadata

try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:
    __version__ = "unknown"


ISSUE_URL = "https://github.com/sedrubal/brother_printer_fwupd/issues/new"
