"""Synthetic log records only; no household data or network probes."""
from datetime import date
import unittest

from tools.analyze_bhm import analyze_lines


class BhmEvidenceTests(unittest.TestCase):
    def test_function_name_and_warning_are_not_disconnects(self):
        rows = [
            "2026 Jan 02 10:00:00 warning BHM: bh_disconnected, uci_pre_uplink: eth2",
            "2026 Jan 02 10:00:01 notice BHM: bh packet loss rate = 0",
            "2026 Jan 02 10:00:01 warning BHM: bh_ping_disconnect: 0",
        ]
        result = analyze_lines(rows)
        self.assertEqual(result["gateway_loss_samples"], 1)
        self.assertEqual(result["nonzero_loss_samples"], 0)
        self.assertEqual(result["explicit_backhaul_disconnect_led_events"], 0)
        self.assertEqual(result["nonzero_disconnect_indicators"], 0)

    def test_old_failure_is_excluded_from_selected_day(self):
        rows = [
            "2026 Jan 01 23:00:00 notice BHM: bh packet loss rate = 100",
            "2026 Jan 01 23:00:01 notice BHM: BHM_LED_DISCONNECTED",
            "2026 Jan 02 01:00:00 notice BHM: bh packet loss rate = 0",
            "2026 Jan 02 01:00:56 notice BHM: bh packet loss rate = 0",
        ]
        result = analyze_lines(rows, date(2026, 1, 2))
        self.assertEqual(result["gateway_loss_samples"], 2)
        self.assertEqual(result["sample_distribution_percent"], {"0": 2})
        self.assertEqual(result["explicit_backhaul_disconnect_led_events"], 0)
        self.assertEqual(result["maximum_nonnegative_gap_between_samples_seconds"], 56)

    def test_explicit_failure_and_recovery(self):
        result = analyze_lines([
            "2026 Jan 02 01:00:00 notice BHM: bh packet loss rate = 66",
            "2026 Jan 02 01:00:00 warning BHM: bh_ping_disconnect: 1",
            "2026 Jan 02 01:00:01 notice BHM: BHM_LED_DISCONNECTED",
            "2026 Jan 02 01:00:11 notice BHM: BHM_LED_ESTABLISH_WIRE_BACKHAUL",
        ])
        self.assertEqual(result["nonzero_loss_samples"], 1)
        self.assertEqual(result["nonzero_disconnect_indicators"], 1)
        self.assertEqual(result["explicit_backhaul_disconnect_led_events"], 1)
        self.assertEqual(result["explicit_wired_establishment_led_events"], 1)

    def test_clock_rollback_reported_even_outside_date_filter(self):
        result = analyze_lines([
            "2026 Jan 03 10:00:00 warning BHM: debug",
            "2026 Jan 02 09:00:00 notice BHM: bh packet loss rate = 0",
        ], date(2026, 1, 2))
        self.assertEqual(len(result["backward_clock_steps_in_whole_file"]), 1)
        self.assertEqual(result["backward_clock_steps_in_whole_file"][0]["seconds"], 90000)

    def test_empty_file_does_not_claim_no_loss(self):
        result = analyze_lines([])
        self.assertEqual(result["gateway_loss_samples"], 0)
        self.assertIsNone(result["first_record"])
        self.assertIsNone(result["maximum_nonnegative_gap_between_samples_seconds"])
        self.assertTrue(any("Zero samples" in item for item in result["limits"]))

    def test_malformed_record_is_not_executed_or_counted(self):
        result = analyze_lines(["$(do not execute)", "2026 Feb 31 00:00:00 invalid"])
        self.assertEqual(result["matching_records"], 0)
        self.assertEqual(result["unparsed_or_invalid_records_in_whole_file"], 2)


if __name__ == "__main__":
    unittest.main()
