# SPDX-License-Identifier: MIT
"""This Mac's N1 (centauri) Wi-Fi and Bluetooth firmware inputs.

The N1 ROM boots only an image stitched for this Mac: the Preboot ftab.bin
with its personalized manifest, the factory BWC3 calibration and the Wi-Fi
SKU. omarchy-mac-boot's omarchy-centauri initcpio hook stitches them the way
macOS's centaurid does; this collects them, unchanged, into vendorfw.
Never substitute another Mac's inputs when collection fails.
"""

import glob
import os
import plistlib
import subprocess
from xml.parsers.expat import ExpatError

PREBOOT = "/System/Volumes/Preboot"
FACTORY_DIR = "/System/Volumes/Hardware/FactoryData/System/Library/Caches/com.apple.factorydata"
FIRMWARE_DIR = "apple/centauri/"
SKU_PROPERTY = "wifi-antenna-sku-info"


class CentauriError(ValueError):
    pass


def firmware_dir(device_class, preboot=PREBOOT):
    """The newest Preboot Centauri directory holding this Mac's manifest, or None on a Mac without an N1."""
    manifests = glob.glob(os.path.join(
        preboot, "*", "boot", "*", "usr/standalone/firmware/Centauri", f"centauri.{device_class}.im4m"))
    if not manifests:
        return None
    return os.path.dirname(max(manifests, key=os.path.getmtime))


def sku_info(data):
    """The wifi-antenna-sku-info property of the centauri node in an IORegistry property list."""
    try:
        pending = list(plistlib.loads(data))
    except (ValueError, TypeError, ExpatError, plistlib.InvalidFileException) as error:
        raise CentauriError("invalid centauri IORegistry property list") from error
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        if node.get("IORegistryEntryName") == "centauri" and isinstance(node.get(SKU_PROPERTY), bytes):
            return node[SKU_PROPERTY]
        pending.extend(node.get("IORegistryEntryChildren", []))
    raise CentauriError(f"no {SKU_PROPERTY} on the centauri IORegistry node")


def read_ioreg():
    return subprocess.run(["ioreg", "-a", "-r", "-n", "centauri", "-l"], check=True, capture_output=True).stdout


def collect(device_class, preboot=PREBOOT, factory_dir=FACTORY_DIR, ioreg=read_ioreg):
    """The four inputs by firmware name, or {} on a Mac without an N1."""
    source = firmware_dir(device_class, preboot)
    if source is None:
        return {}
    calibration = sorted(glob.glob(os.path.join(factory_dir, "BWC3-*")))
    if len(calibration) != 1:
        raise CentauriError(f"expected one BWC3 factory file, found {len(calibration)}")
    read = lambda path: open(path, "rb").read()
    return {
        FIRMWARE_DIR + "ftab.bin": read(os.path.join(source, "ftab.bin")),
        FIRMWARE_DIR + "manifest.im4m": read(os.path.join(source, f"centauri.{device_class}.im4m")),
        FIRMWARE_DIR + "BWC3.img4": read(calibration[0]),
        FIRMWARE_DIR + SKU_PROPERTY: sku_info(ioreg()),
    }
