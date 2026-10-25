import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import desktop


class ReleaseLauncherTests(unittest.TestCase):
    def setUp(self):
        self.adapter = dict(interface="Ethernet", ip="192.168.1.240", prefix=24, gateway="192.168.1.1")

    def test_answers_produce_the_existing_one_mac_profile(self):
        c = desktop.configuration_from_answers(self.adapter, "aa-bb-cc-dd-ee-ff", "192.168.1.250", 60)
        self.assertEqual(c["extender_mac"], "AA:BB:CC:DD:EE:FF")
        self.assertTrue(c["address_plan_confirmed"])
        self.assertEqual(c["server_ip"], self.adapter["ip"])

    def test_bad_address_and_bad_mac_cannot_be_saved(self):
        for mac, address in [("01:00:00:00:00:01", "192.168.1.250"),
                             ("AA:BB:CC:DD:EE:FF", "192.168.1.1"),
                             ("AA:BB:CC:DD:EE:FF", "192.168.2.250")]:
            with self.assertRaises(ValueError):
                desktop.configuration_from_answers(self.adapter, mac, address, 60)

    def test_suggestion_is_a_host_not_the_helper(self):
        self.assertEqual(desktop.default_extender_ip(self.adapter), "192.168.1.250")

    def test_pinned_archive_is_rejected_before_installation(self):
        with self.assertRaises(ValueError):
            desktop.verified_tftpd_payload(b"unexpected download")

    def test_only_the_expected_verified_executable_is_returned(self):
        contents = io.BytesIO()
        with zipfile.ZipFile(contents, "w") as archive:
            archive.writestr("../../tftpd64.exe", b"test executable")
            archive.writestr("../../unrelated-file", b"never extracted")
        payload = contents.getvalue()
        with patch.object(desktop, "TFTPD_ZIP_SHA", hashlib.sha256(payload).hexdigest()), \
             patch.object(desktop, "TFTPD_EXE_SHA", hashlib.sha256(b"test executable").hexdigest()):
            self.assertEqual(desktop.verified_tftpd_payload(payload), b"test executable")

    def test_self_test_never_downloads_or_starts_a_process(self):
        with patch("desktop.subprocess.run", side_effect=AssertionError("unexpected process")), \
             patch("desktop.urllib.request.urlopen", side_effect=AssertionError("unexpected download")):
            self.assertEqual(desktop.self_test(), 0)

    def test_windows_discovery_accepts_single_object_json(self):
        with patch("desktop.sys.platform", "win32"), patch("desktop.capture", return_value=json.dumps(self.adapter)):
            self.assertEqual(desktop.discover_adapters(), [self.adapter])
