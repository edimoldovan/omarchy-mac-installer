# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import omarchy_centauri as centauri

SKU = bytes.fromhex("01000000000000005833000000000000")


def ioreg(sku=SKU):
    node = {"IORegistryEntryName": "centauri", centauri.SKU_PROPERTY: sku}
    return plistlib.dumps([{"IORegistryEntryName": "arm-io", "IORegistryEntryChildren": [node]}])


class CentauriTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.preboot = os.path.join(self.root.name, "Preboot")
        self.factory = os.path.join(self.root.name, "factorydata")
        os.makedirs(self.factory)

    def tearDown(self):
        self.root.cleanup()

    def boot_dir(self, vgid, nonce, mtime, ftab=b"ftab"):
        path = os.path.join(self.preboot, vgid, "boot", nonce, "usr/standalone/firmware/Centauri")
        os.makedirs(path)
        Path(path, "ftab.bin").write_bytes(ftab)
        manifest = Path(path, "centauri.j714cap.im4m")
        manifest.write_bytes(b"manifest " + nonce.encode())
        Path(path, "centauri.j716cap.im4m").write_bytes(b"another board")
        os.utime(manifest, (mtime, mtime))
        return path

    def test_collects_the_newest_manifest_with_its_own_ftab(self):
        self.boot_dir("6CB7E866", "41AC12F8", 2000, ftab=b"new ftab")
        self.boot_dir("3A31C7DB", "E53C26FF", 1000, ftab=b"old ftab")
        Path(self.factory, "BWC3-00002026-3519709EA602E93A").write_bytes(b"IMG4 BWC3")
        Path(self.factory, "mansta-BWC3-00002026-3519709EA602E93A").write_bytes(b"status")
        files = centauri.collect("j714cap", self.preboot, self.factory, ioreg=ioreg)
        self.assertEqual(files, {
            "apple/centauri/ftab.bin": b"new ftab",
            "apple/centauri/manifest.im4m": b"manifest 41AC12F8",
            "apple/centauri/BWC3.img4": b"IMG4 BWC3",
            "apple/centauri/wifi-antenna-sku-info": SKU,
        })

    def test_a_mac_without_an_n1_manifest_collects_nothing(self):
        self.boot_dir("6CB7E866", "41AC12F8", 2000)
        self.assertEqual(centauri.collect("j700ap", self.preboot, self.factory, ioreg=lambda: self.fail("read")), {})

    def test_an_n1_without_its_calibration_fails(self):
        self.boot_dir("6CB7E866", "41AC12F8", 2000)
        with self.assertRaisesRegex(centauri.CentauriError, "one BWC3 factory file, found 0"):
            centauri.collect("j714cap", self.preboot, self.factory, ioreg=ioreg)

    def test_the_sku_comes_from_the_centauri_node_only(self):
        self.assertEqual(centauri.sku_info(ioreg()), SKU)
        other = plistlib.dumps([{"IORegistryEntryName": "bluetooth", centauri.SKU_PROPERTY: SKU}])
        with self.assertRaisesRegex(centauri.CentauriError, "no wifi-antenna-sku-info"):
            centauri.sku_info(other)
        with self.assertRaisesRegex(centauri.CentauriError, "invalid"):
            centauri.sku_info(b"not a plist")


if __name__ == "__main__":
    unittest.main()
