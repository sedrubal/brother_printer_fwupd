"""Get the firmware download URL and download the firmare from the official Brother website."""

import argparse
import logging
import typing
from copy import copy
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from . import ISSUE_URL
from .common import common_args, printer_info_args
from .models import FWInfo, SNMPPrinterInfo
from .utils import (
    CONSOLE_LOG_HANDLER,
    LOGGER,
    ExceptionGroupCompat,
    get_running_os,
    sluggify,
)

FW_UPDATE_URL = "https://firmverup.brother.co.jp/kne_bh7_update_nt_ssl/ifax2.asmx/fileUpdate"

API_REQUEST_DATA_TEMPLATE = BeautifulSoup(
    """
<REQUESTINFO>
    <FIRMUPDATETOOLINFO>
        <FIRMCATEGORY></FIRMCATEGORY>
        <OS></OS>
        <INSPECTMODE>1</INSPECTMODE>
    </FIRMUPDATETOOLINFO>

    <FIRMUPDATEINFO>
        <MODELINFO>
            <SERIALNO></SERIALNO>
            <NAME></NAME>
            <SPEC></SPEC>
            <DRIVER></DRIVER>
            <FIRMINFO></FIRMINFO>
        </MODELINFO>
        <DRIVERCNT>1</DRIVERCNT>
        <LOGNO>2</LOGNO>
        <ERRBIT></ERRBIT>
        <NEEDRESPONSE>1</NEEDRESPONSE>
    </FIRMUPDATEINFO>
</REQUESTINFO>
""".strip(),
    "xml",
)

REQUESTS_TIMEOUT = 10


RUNNING_OS = get_running_os()


def get_download_url(
    printer_info: "SNMPPrinterInfo",
    reported_os: str,
    firmid: str = "MAIN",
) -> typing.Union[tuple[str, str], tuple[None, None]]:
    """
    Get the firmware download URL for the target printer.

    :return: Tuple of download latest version and URL.
    """

    api_request_data = copy(API_REQUEST_DATA_TEMPLATE)
    api_request_data.REQUESTINFO.FIRMUPDATETOOLINFO.FIRMCATEGORY.string = firmid
    api_request_data.REQUESTINFO.FIRMUPDATETOOLINFO.OS.string = reported_os
    api_request_data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.NAME.string = printer_info.model
    api_request_data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.SPEC.string = printer_info.spec

    for fw_info in printer_info.fw_versions:
        firm_info = Tag(name="FIRM", parser="xml")
        firm_info.append(Tag(name="ID", parser="xml"))
        firm_info.append(Tag(name="VERSION", parser="xml"))
        firm_info.ID.string = fw_info.firmid
        firm_info.VERSION.string = fw_info.firmver

        api_request_data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.FIRMINFO.append(firm_info)

    errors: list[Exception] = []

    for modification_callback in (copy, apply_driver_ews, apply_api_misspelling):
        api_request_data_str = str(modification_callback(api_request_data))

        # curl -X POST -d @hl3040cn-update.xml -H "Content-Type:text/xml"
        LOGGER.debug(
            "Sending POST request to %s with following content:\n%s",
            FW_UPDATE_URL,
            api_request_data_str,
        )
        resp = requests.post(
            FW_UPDATE_URL,
            data=api_request_data_str,
            headers={"Content-Type": "text/xml"},
            timeout=REQUESTS_TIMEOUT,
        )
        resp.raise_for_status()
        LOGGER.debug("Response:\n%s", resp.text)

        try:
            return parse_response(response=resp.text, firmid=firmid)
        except ValueError as err:
            errors.append(err)
            LOGGER.warning(err)
            continue

    raise ExceptionGroupCompat("Giving up fetching firmware.", errors)


def parse_response(response: str, firmid: str) -> typing.Union[tuple[str, str], tuple[None, None]]:
    """
    Parse the API response and return a tuple of the latest version and the download URL.
    """
    resp_xml = BeautifulSoup(response, "xml")

    def select_one(name: str) -> str:
        tags = resp_xml.select(name)
        if len(tags) > 1:
            raise ValueError(
                f"Invalid response: Expected only one tag of name '{name}' in response '{resp_xml}'."
            )
        elif len(tags) == 0:
            raise ValueError(
                f"Invalid response: Expected tag '{name}' to be in response '{resp_xml}'."
            )
        return tags[0].text

    versioncheck_val = select_one("VERSIONCHECK")
    if versioncheck_val == "1":
        LOGGER.success("Firmware part %s seems to be up to date.", firmid)
        return None, None
    elif versioncheck_val == "0":
        # Firmware update required
        pass
    elif versioncheck_val == "2":
        LOGGER.error(
            (
                "Received versioncheck value '2' for firmware part %s."
                " I'm sorry, but I don't know, what Brother wants to say with this code."
                " If you have any information, please open an issue on GitHub:"
                " %s"
            ),
            firmid,
            ISSUE_URL,
        )
        return None, None
    else:
        raise ValueError(
            f"Unknown value of 'versioncheck' in response for firmid={firmid}: '{resp_xml}'."
        )

    latest_version = select_one("LATESTVERSION")
    LOGGER.info("Update for firmware part '%s' available (version '%s')", firmid, latest_version)

    firmid_val = select_one("FIRMID")
    if firmid_val != firmid:
        LOGGER.warning(
            "Request for firmid=%s was answered with firmid=%s. Be careful!",
            firmid,
            firmid_val,
        )

    return latest_version, select_one("PATH")


def apply_driver_ews(data: BeautifulSoup) -> BeautifulSoup:
    """
    Modify the request data in the way it is required for MFC-L3750CDW, HL-L2360DW and others.

    1. Remove `<SERIALNO>` / `<SELIALNO>`
    2. Add "EWS" to `<DRIVER>`
    See https://github.com/sedrubal/brother_printer_fwupd/issues/19#issuecomment-2079813638
    """
    LOGGER.info("Trying again without <SERIALNO> in API request but with <DRIVER>EWS</DRIVER>...")
    data = copy(data)
    data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.DRIVER.string = "EWS"
    data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.SERIALNO.replace_with(
        Tag(name="SELIALNO", parser="xml")
    )
    return data


def apply_api_misspelling(data: BeautifulSoup) -> BeautifulSoup:
    """
    Another modification which works for MFC-L3750CDW, HL-L2360DW and others.

    1. Replace `<SERIALNO>` with typo `<SELIALNO>`
    2. Add "EWS" to `<DRIVER>`
    See https://github.com/sedrubal/brother_printer_fwupd/issues/19
    """
    LOGGER.info("Trying again with misspelling in API request...")
    data = copy(data)
    data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.DRIVER.string = "EWS"
    data.REQUESTINFO.FIRMUPDATEINFO.MODELINFO.SERIALNO.replace_with(
        Tag(name="SELIALNO", parser="xml")
    )
    return data


def download_fw(
    url: str,
    dst_dir: Path,
    printer_model: str,
    fw_part: typing.Union[str, FWInfo],
    latest_version: str,
):
    """Download the firmware."""
    resp = requests.get(url, stream=True, timeout=REQUESTS_TIMEOUT)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))
    size_written = 0
    chunk_size = 8192

    out_file = dst_dir / (sluggify(f"firmware-{printer_model}-{fw_part}-{latest_version}") + ".djf")

    with out_file.open("wb") as out:
        for chunk in resp.iter_content(chunk_size):
            size_written += out.write(chunk)
            progress = size_written / total_size * 100
            print(f"\r{progress: 5.1f} %", end="", flush=True)

    print()
    return out_file


def get_info_and_download_fw(
    printer_info,
    fw_part: FWInfo,
    os: str,
    fw_dir: Path,
) -> typing.Optional[Path]:
    """Try to get the update URL and download the new firmware."""
    LOGGER.info("Try to get information for firmware part %s", fw_part)

    latest_version, download_url = get_download_url(
        printer_info=printer_info,
        firmid=str(fw_part.firmid),
        reported_os=os,
    )

    if not download_url:
        return None

    assert latest_version
    assert download_url
    model = printer_info.model
    assert model

    LOGGER.debug("  Download URL is %s", download_url)
    LOGGER.success("Downloading firmware file.")
    fw_file_path = download_fw(
        url=download_url,
        dst_dir=fw_dir,
        printer_model=model,
        fw_part=fw_part,
        latest_version=latest_version,
    )

    return fw_file_path


def fw_downloader_args(parser: argparse.ArgumentParser) -> None:
    """Add command line arguments for the firmware downloader to an argparse parser."""
    parser.add_argument(
        "--os",
        dest="os",
        type=str.upper,
        default=RUNNING_OS,
        choices=["WINDOWS", "MAC", "LINUX"],
        help="Operating system to report when downloading firmware (default: '%(default)s').",
    )
    parser.add_argument(
        "-o",
        "--fw-dir",
        type=Path,
        dest="fw_dir",
        default=".",
        help="Directory, where the firmware will be downloaded (default: '%(default)s').",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
    )

    common_args(parser, ip_required=False)
    fw_downloader_args(parser)
    printer_info_args(parser, required=True)

    return parser.parse_args()


def main() -> None:
    """Run the downloader."""
    args = parse_args()

    CONSOLE_LOG_HANDLER.setLevel(logging.DEBUG if args.debug else logging.INFO)

    printer_info = SNMPPrinterInfo.from_args(args)

    for fw_part in printer_info.fw_versions:
        fw_file_path = get_info_and_download_fw(
            printer_info=printer_info,
            fw_part=fw_part,
            os=args.os,
            fw_dir=args.fw_dir,
        )

        if fw_file_path:
            LOGGER.success("Downloaded firmware for %s to %s", fw_part.firmid, fw_file_path)


if __name__ == "__main__":
    main()
