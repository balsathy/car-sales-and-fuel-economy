from __future__ import annotations

import unittest

from chatbot import answer
from downloaders.epa import parse_epa_csv
from downloaders.sales import parse_sales_html


class DownloaderTests(unittest.TestCase):
    def test_sales_parser_keeps_published_zero_and_omits_unknown_month(self):
        html = """
        <table>
          <tr><th>Model</th><th>Jan</th><th>Feb</th><th>Mar</th><th>Apr</th>
          <th>May</th><th>Jun</th><th>Jul</th><th>Aug</th><th>Sep</th>
          <th>Oct</th><th>Nov</th><th>Dec</th></tr>
          <tr><td>Honda CR-V</td><td>1,234</td><td>0</td><td>�</td><td>—</td>
          <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        </table>
        """
        result = parse_sales_html(html, 2026)
        self.assertEqual(result["available_months"], [1, 2])
        self.assertEqual([r["units"] for r in result["records"]], [1234, 0])
        self.assertEqual(result["records"][0]["make"], "Honda")
        self.assertEqual(result["records"][0]["model"], "CR-V")
        self.assertEqual(result["records"][0]["estimate_status"], "not_specified_by_source")

    def test_sales_parser_matches_table_without_extra_heading_row(self):
        html = "<table><tr>" + "".join(
            f"<th>{cell}</th>" for cell in ["Model", "Jan", "Feb", "Mar", "Apr", "May",
            "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ) + "</tr><tr><td>Alfa Romeo Giulia</td>" + "".join(
            f"<td>{value}</td>" for value in ["1"] * 12
        ) + "</tr></table>"
        result = parse_sales_html(html, 2025)
        self.assertEqual(result["records"][0]["make"], "Alfa Romeo")
        self.assertEqual(result["records"][0]["model"], "Giulia")

    def test_epa_parser_filters_years_and_marks_ev_records(self):
        csv_text = (
            "id,year,make,model,baseModel,fuelType,fuelType1,atvType,city08,highway08,comb08,combMpk\n"
            '1,2025,Toyota,Example Hybrid,Example,Regular,Regular,,50,48,49,0\n'
            '2,2026,Example,EV,EV,Electricity,Electricity,EV,130,110,120,0\n'
            '3,2024,Old,Car,Car,Regular,Regular,,30,40,34,0\n'
            '4,2026,Toyota,Hydrogen Car,Hydrogen Car,Hydrogen,Hydrogen,FCV,70,68,69,72\n'
        )
        result = parse_epa_csv(csv_text)
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(result["records"][1]["vehicle_type"], "EV")
        self.assertEqual(result["records"][1]["combined_mpg_or_mpge"], 120)
        self.assertEqual(result["records"][2]["combined_miles_per_kg"], 72)


class ChatbotTests(unittest.TestCase):
    def setUp(self):
        self.sales = {
            "source_url": "https://example.test/2026",
            "records": [
                {"year": 2025, "month": 1, "make": "Honda", "model": "CR-V", "units": 10,
                 "source_url": "https://example.test/2025"},
                {"year": 2025, "month": 2, "make": "Honda", "model": "CR-V", "units": 15,
                 "source_url": "https://example.test/2025"},
                {"year": 2025, "month": 1, "make": "Ford", "model": "F-Series", "units": 50,
                 "source_url": "https://example.test/2025"},
                {"year": 2025, "month": 1, "make": "Efficient", "model": "Hybrid", "units": 1,
                 "source_url": "https://example.test/2025"},
                {"year": 2025, "month": 1, "make": "Electric", "model": "EV", "units": 1,
                 "source_url": "https://example.test/2025"},
                {"year": 2025, "month": 1, "make": "Toyota", "model": "Mirai", "units": 1,
                 "source_url": "https://example.test/2025"},
            ],
        }
        self.mileage = {
            "records": [
                {"year": 2025, "make": "Efficient", "model": "Hybrid", "combined_mpg_or_mpge": 60,
                 "fuel_type": "Regular", "vehicle_type": "", "source": "EPA", "source_url": "https://epa.test"},
                {"year": 2025, "make": "Electric", "model": "EV", "combined_mpg_or_mpge": 130,
                 "fuel_type": "Electricity", "vehicle_type": "EV", "source": "EPA", "source_url": "https://epa.test"},
                {"year": 2025, "make": "Toyota", "model": "Mirai", "base_model": "Mirai",
                 "combined_mpg_or_mpge": 74, "combined_miles_per_kg": 74,
                 "fuel_type": "Hydrogen", "fuel_type_1": "Hydrogen", "vehicle_type": "FCV",
                 "source": "EPA", "source_url": "https://epa.test"},
            ],
        }

    def test_sales_question_sums_monthly_records_and_names_source(self):
        result = answer("How many Honda CR-Vs sold in 2025?", self.sales, self.mileage)
        self.assertIn("25 Honda CR-V sales", result)
        self.assertIn("https://example.test/2025", result)

    def test_best_mileage_separates_mpg_and_mpge(self):
        gas = answer("Which car has the best mileage?", self.sales, self.mileage)
        electric = answer("Which electric car has the best mileage?", self.sales, self.mileage)
        hydrogen = answer("Which hydrogen vehicle has the best mileage?", self.sales, self.mileage)
        self.assertIn("Efficient Hybrid", gas)
        self.assertIn("60 combined MPG", gas)
        self.assertIn("Electric EV", electric)
        self.assertIn("130 MPGe", electric)
        self.assertNotIn("Mirai", gas)
        self.assertIn("Toyota Mirai", hydrogen)
        self.assertIn("74 combined miles/kg", hydrogen)

    def test_model_specific_mileage_returns_odyssey_rating_not_global_best(self):
        sales = {"records": [
            {"year": 2025, "month": 1, "make": "Honda", "model": "Odyssey", "units": 10},
        ]}
        mileage = {"records": [
            {"year": 2025, "make": "Honda", "model": "Odyssey", "base_model": "Odyssey",
             "city_mpg": 19, "highway_mpg": 28, "combined_mpg_or_mpge": 22,
             "fuel_type": "Regular", "vehicle_type": "", "source": "EPA",
             "source_url": "https://epa.test"},
            {"year": 2025, "make": "Toyota", "model": "Prius", "base_model": "Prius",
             "city_mpg": 57, "highway_mpg": 56, "combined_mpg_or_mpge": 56,
             "fuel_type": "Regular", "vehicle_type": "", "source": "EPA",
             "source_url": "https://epa.test"},
        ]}
        result = answer("What is the mileage of a Honda Odyssey?", sales, mileage)
        self.assertIn("EPA 2025 fuel economy for Honda Odyssey", result)
        self.assertIn("19 city / 28 highway / 22 combined MPG", result)
        self.assertNotIn("Toyota Prius", result)

    def test_model_specific_mileage_tolerates_common_typos(self):
        sales = {"records": [
            {"year": 2025, "month": 1, "make": "Honda", "model": "Odyssey", "units": 10},
        ]}
        mileage = {"records": [
            {"year": 2025, "make": "Honda", "model": "Odyssey", "base_model": "Odyssey",
             "city_mpg": 19, "highway_mpg": 28, "combined_mpg_or_mpge": 22,
             "fuel_type": "Regular", "vehicle_type": "", "source": "EPA",
             "source_url": "https://epa.test"},
        ]}
        result = answer("What is the milage for a Honda Oddysey?", sales, mileage)
        self.assertIn("Honda Odyssey", result)
        self.assertIn("22 combined MPG", result)

    def test_combined_question_returns_model_sales_and_epa_mileage(self):
        sales = {"records": [
            {"year": 2025, "month": 1, "make": "Honda", "model": "Odyssey",
             "units": 100, "source_url": "https://sales.test/2025"},
            {"year": 2025, "month": 2, "make": "Honda", "model": "Odyssey",
             "units": 125, "source_url": "https://sales.test/2025"},
        ]}
        mileage = {"records": [
            {"year": 2025, "make": "Honda", "model": "Odyssey", "base_model": "Odyssey",
             "city_mpg": 19, "highway_mpg": 28, "combined_mpg_or_mpge": 22,
             "fuel_type": "Regular", "vehicle_type": "", "source": "EPA",
             "source_url": "https://epa.test"},
        ]}
        result = answer(
            "How many Honda Odyssey sold in 2025 and what is its mileage?",
            sales,
            mileage,
        )
        self.assertIn("22 combined MPG", result)
        self.assertIn("225 Honda Odyssey sales", result)
        self.assertIn("https://sales.test/2025", result)
        self.assertIn("https://epa.test", result)

    def test_sales_ranking(self):
        result = answer("Which model sold the most in 2025?", self.sales, self.mileage)
        self.assertIn("Ford F-Series", result)
        self.assertIn("50 units", result)

    def test_explicit_alias_matches_f_series_to_f150(self):
        sales = {"records": [
            {"year": 2025, "month": 1, "make": "Ford", "model": "F-Series", "units": 10},
        ]}
        mileage = {"records": [
            {"year": 2025, "make": "Ford", "model": "F-150 4WD", "base_model": "F150",
             "combined_mpg_or_mpge": 24, "fuel_type": "Regular", "vehicle_type": "",
             "source": "EPA", "source_url": "https://epa.test"},
        ]}
        result = answer("Which car has the best mileage in 2025?", sales, mileage)
        self.assertIn("Ford F-Series", result)

    def test_unmatched_mileage_nameplate_is_not_guessed(self):
        sales = {"records": [
            {"year": 2025, "month": 1, "make": "Honda", "model": "Civic", "units": 10},
        ]}
        mileage = {"records": [
            {"year": 2025, "make": "Unknown", "model": "Mystery", "base_model": "Mystery",
             "combined_mpg_or_mpge": 99, "fuel_type": "Regular", "vehicle_type": "",
             "source": "EPA", "source_url": "https://epa.test"},
        ]}
        result = answer("Which car has the best mileage in 2025?", sales, mileage)
        self.assertIn("Unmatched vehicles are not guessed", result)


if __name__ == "__main__":
    unittest.main()
