"""Offline input-boundary and single-client scope tests."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import e3200_helper as helper

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.example.json").read_text())
        self.config["interface"] = "eth0"

    def assert_invalid(self, **updates):
        candidate = deepcopy(self.config)
        candidate.update(updates)
        with self.assertRaises(ValueError):
            helper.validate_config(candidate)

    def test_normal_config_is_valid_before_startup_confirmation(self):
        normalized = helper.validate_config(self.config)
        self.assertEqual(normalized["extender_ip"], "192.168.1.250")
        self.assertEqual(normalized["lease_minutes"], 60)

    def test_serving_requires_explicit_address_confirmation(self):
        with self.assertRaises(ValueError):
            helper.validate_config(self.config, require_confirmed=True)
        self.config["address_plan_confirmed"] = True
        helper.validate_config(self.config, require_confirmed=True)

    def test_confirmation_is_boolean_not_a_truthy_string(self):
        self.assert_invalid(address_plan_confirmed="true")

    def test_rejects_injected_configuration_and_placeholders(self):
        for interface in ["eth0\ndhcp-range=192.168.1.2,192.168.1.239", "eth0;echo bad", "REPLACE_WITH_INTERFACE", ""]:
            with self.subTest(interface=interface):
                self.assert_invalid(interface=interface)

    def test_only_one_unicast_mac_is_allowed(self):
        for mac in ["*", "AA:BB:CC:*:*:*", "FF:FF:FF:FF:FF:FF", "01:00:5e:00:00:01", "00:00:00:00:00:00", "invalid"]:
            with self.subTest(mac=mac):
                self.assert_invalid(extender_mac=mac)

    def test_host_addresses_are_distinct(self):
        self.assert_invalid(extender_ip=self.config["server_ip"])
        self.assert_invalid(extender_ip=self.config["gateway"])
        self.assert_invalid(server_ip=self.config["gateway"])

    def test_usable_addresses_must_share_a_subnet(self):
        for field, value in [("extender_ip", "192.168.2.250"), ("server_ip", "192.168.1.255"),
                             ("gateway", "192.168.1.0"), ("extender_ip", "224.0.0.1"),
                             ("server_ip", "::1"), ("gateway", "not-an-ip")]:
            with self.subTest(field=field, value=value):
                self.assert_invalid(**{field: value})

    def test_mask_is_contiguous(self):
        self.assert_invalid(subnet_mask="255.0.255.0")

    def test_unknown_or_missing_fields_fail_closed(self):
        self.assert_invalid(unrestricted_pool=True)
        candidate = deepcopy(self.config)
        del candidate["extender_mac"]
        with self.assertRaises(ValueError):
            helper.validate_config(candidate)

    def test_lease_is_bounded_integer_minutes(self):
        for value in [True, 0, 1, 525601, "60", 3.5]:
            with self.subTest(value=value):
                self.assert_invalid(lease_minutes=value)
        for value in [2, 60, 1440, 525600]:
            candidate = dict(self.config, lease_minutes=value)
            self.assertEqual(helper.validate_config(candidate)["lease_minutes"], value)

    def test_option_125_has_valid_enterprise_and_nested_lengths(self):
        data = bytes.fromhex(helper.OPTION125_HEX.replace(":", ""))
        self.assertEqual(len(data), 38)
        self.assertEqual(int.from_bytes(data[:4], "big"), 3561)
        self.assertEqual(data[4], len(data[5:]))
        cursor, fields = 5, {}
        while cursor < len(data):
            code, size = data[cursor:cursor + 2]
            cursor += 2
            fields[code] = data[cursor:cursor + size]
            cursor += size
        self.assertEqual(cursor, len(data))
        self.assertEqual(fields[6], b"G3100")
        self.assertEqual(fields[5], b"G000000000000000")

    def test_dnsmasq_has_no_general_pool_or_dns_server(self):
        rendered = helper.render_dnsmasq(self.config)
        self.assertIn("port=0", rendered.splitlines())
        self.assertIn("dhcp-ignore=tag:!e3200", rendered.splitlines())
        hosts = [line for line in rendered.splitlines() if line.startswith("dhcp-host=")]
        ranges = [line for line in rendered.splitlines() if line.startswith("dhcp-range=")]
        self.assertEqual(len(hosts), 1)
        self.assertEqual(len(ranges), 1)
        self.assertIn("static", ranges[0])
        self.assertIn(self.config["extender_mac"].lower(), hosts[0].lower())
        self.assertNotIn("dhcp-authoritative", rendered.splitlines())
        self.assertFalse(any(line.startswith(("conf-file=", "conf-dir=", "enable-tftp")) for line in rendered.splitlines()))
        self.assertIn("dhcp-option-force=tag:e3200,60,ARCADYAN", rendered.splitlines())
        self.assertIn(helper.OPTION125_HEX, rendered)

    def test_tftpd_has_no_general_pool_or_other_services(self):
        rendered = helper.render_tftpd(self.config)
        lines = rendered.splitlines()
        self.assertIn("Services=4", lines)
        self.assertIn("PoolSize=0", lines)
        self.assertIn("Lease (minutes)=60", lines)
        self.assertIn("AddOptionNumber1=60", lines)
        self.assertIn("AddOptionNumber2=125", lines)
        self.assertIn(f"{self.config['extender_mac']}={self.config['extender_ip']}".lower(), rendered.lower())


if __name__ == "__main__":
    unittest.main()
