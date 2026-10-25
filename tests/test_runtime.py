"""Mocked launch boundaries: never bind DHCP or launch a real process."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import e3200_helper as helper

ROOT = Path(__file__).resolve().parents[1]


class RuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.example.json").read_text())
        self.config.update(interface="eth0", address_plan_confirmed=True)

    def test_unconfirmed_plan_cannot_reach_preflight_or_start(self):
        self.config["address_plan_confirmed"] = False
        with patch.object(helper.sys, "platform", "linux"), \
             patch.object(helper.os, "geteuid", return_value=0, create=True), \
             patch.object(helper, "_preflight") as preflight, \
             patch.object(helper.subprocess, "Popen") as start:
            with self.assertRaises(ValueError):
                helper.run_helper(self.config)
            preflight.assert_not_called()
            start.assert_not_called()

    def test_failed_preflight_cannot_start_daemon(self):
        with patch.object(helper.sys, "platform", "linux"), \
             patch.object(helper.os, "geteuid", return_value=0, create=True), \
             patch.object(helper, "_preflight", side_effect=RuntimeError("busy UDP port")), \
             patch.object(helper.subprocess, "Popen") as start:
            with self.assertRaisesRegex(RuntimeError, "busy UDP port"):
                helper.run_helper(self.config)
            start.assert_not_called()

    def test_preflight_only_tests_config_without_starting_daemon(self):
        args = ["/fake/dnsmasq", "--conf-file=/fake/config"]
        with patch.object(helper.sys, "platform", "linux"), \
             patch.object(helper.os, "geteuid", return_value=0, create=True), \
             patch.object(helper, "_preflight"), \
             patch.object(helper, "_runtime", return_value=contextlib.nullcontext(args)), \
             patch.object(helper, "_command") as command, \
             patch.object(helper.subprocess, "Popen") as start, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(helper.run_helper(self.config, preflight_only=True), 0)
            command.assert_called_once_with([*args, "--test"])
            start.assert_not_called()

    def test_configuration_parser_failure_prevents_start(self):
        with patch.object(helper.sys, "platform", "linux"), \
             patch.object(helper.os, "geteuid", return_value=0, create=True), \
             patch.object(helper, "_preflight"), \
             patch.object(helper, "_runtime", return_value=contextlib.nullcontext(["/fake/dnsmasq"])), \
             patch.object(helper, "_command", side_effect=RuntimeError("bad config")), \
             patch.object(helper.subprocess, "Popen") as start:
            with self.assertRaisesRegex(RuntimeError, "bad config"):
                helper.run_helper(self.config)
            start.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Unix privilege-drop runtime")
    def test_private_tmpdir_does_not_hide_runtime_from_privilege_dropped_daemon(self):
        import grp
        import pwd
        (ROOT / ".runtime").mkdir(exist_ok=True)
        factory = tempfile.TemporaryDirectory
        requested = []

        def mapped_tempdir(*args, **kwargs):
            requested.append(kwargs.get("dir"))
            kwargs["dir"] = ROOT / ".runtime"
            return factory(*args, **kwargs)

        with patch.object(helper.tempfile, "TemporaryDirectory", side_effect=mapped_tempdir), \
             patch.object(pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())), \
             patch.object(grp, "getgrgid", return_value=SimpleNamespace(gr_name="testgroup")), \
             patch.object(helper.os, "chown"), \
             patch.object(helper, "_dnsmasq_binary", return_value="/fake/dnsmasq"), \
             patch.dict(os.environ, {"TMPDIR": "/private/nontraversable/user-temp"}):
            with helper._runtime(self.config) as args:
                conf = Path(next(a.split("=", 1)[1] for a in args if a.startswith("--conf-file=")))
                directory = conf.parent
                self.assertTrue(conf.is_file())
                self.assertEqual(conf.stat().st_mode & 0o777, 0o600)
                self.assertEqual(directory.stat().st_mode & 0o777, 0o711)
                self.assertEqual((directory / "state").stat().st_mode & 0o777, 0o700)
            self.assertFalse(directory.exists())
        self.assertEqual(requested, ["/tmp"])


if __name__ == "__main__":
    unittest.main()
