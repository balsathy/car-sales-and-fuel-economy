from __future__ import annotations

import unittest
from unittest.mock import patch

import download_data


class DownloadCommandTests(unittest.TestCase):
    def test_sales_command_merges_year_without_dropping_other_year(self):
        existing = {
            "records": [
                {"year": 2025, "make": "Honda", "model": "Civic", "units": 10},
                {"year": 2026, "make": "Toyota", "model": "Camry", "units": 20},
            ]
        }
        incoming = {
            "year": 2025,
            "source_url": "https://example.test/2025",
            "records": [{"year": 2025, "make": "Honda", "model": "Civic", "units": 15}],
        }
        with (
            patch("sys.argv", ["download_data.py", "sales", "2025"]),
            patch.object(download_data, "DATA_DIR"),
            patch.object(download_data, "_load", return_value=existing),
            patch.object(download_data, "download_sales", return_value=incoming),
            patch.object(download_data, "_save") as save,
        ):
            self.assertEqual(download_data.main(), 0)
        saved = save.call_args.args[1]
        self.assertEqual([r["units"] for r in saved["records"]], [20, 15])

    def test_epa_command_reports_source_failure_with_nonzero_status(self):
        with (
            patch("sys.argv", ["download_data.py", "epa"]),
            patch.object(download_data, "DATA_DIR"),
            patch.object(download_data, "download_epa", side_effect=OSError("offline")),
        ):
            self.assertEqual(download_data.main(), 1)

    def test_invalid_sales_year_is_rejected(self):
        with patch("sys.argv", ["download_data.py", "sales", "2024"]):
            with self.assertRaises(SystemExit) as error:
                download_data.main()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
