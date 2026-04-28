from unittest import TestCase

from apps.browser.presentation import format_protein_position, format_repeat_pattern


class BrowserPresentationTests(TestCase):
    def test_format_repeat_pattern_compacts_pure_repeat(self):
        self.assertEqual(format_repeat_pattern("Q" * 42), "42Q")

    def test_format_repeat_pattern_compacts_interrupted_repeats(self):
        self.assertEqual(format_repeat_pattern("Q" * 18 + "A" + "Q" * 12), "18Q1A12Q")
        self.assertEqual(format_repeat_pattern("A" * 10 + "G" + "A" * 9), "10A1G9A")
        self.assertEqual(
            format_repeat_pattern("P" * 7 + "A" + "P" * 8 + "S" + "P" * 5),
            "7P1A8P1S5P",
        )

    def test_format_repeat_pattern_handles_empty_sequence(self):
        self.assertEqual(format_repeat_pattern(""), "")
        self.assertEqual(format_repeat_pattern(None), "")

    def test_format_protein_position_includes_midpoint_percent(self):
        self.assertEqual(format_protein_position(10, 20, 300), "10-20 (5%)")

    def test_format_protein_position_falls_back_to_coordinates_without_length(self):
        self.assertEqual(format_protein_position(10, 20, 0), "10-20")
        self.assertEqual(format_protein_position(10, 20, None), "10-20")

    def test_format_protein_position_handles_missing_coordinates(self):
        self.assertEqual(format_protein_position(None, 20, 300), "")
        self.assertEqual(format_protein_position(10, None, 300), "")
