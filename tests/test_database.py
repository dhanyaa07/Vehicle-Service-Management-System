from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import Database
from repository import ServiceRepository
from seed import seed_demo


class VehicleServiceDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(backend="sqlite", sqlite_path=self.db_path)
        self.db.initialize()
        self.repo = ServiceRepository(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_minimal_job(self, stock: int = 10, part_price: float = 12.50):
        customer_id = self.repo.save_customer({"Name": "Test Customer", "Phone": "9000000000", "Email": "test@example.test", "Address": "Mumbai"})
        vehicle_id = self.repo.save_vehicle({"Customer_ID": customer_id, "Registration_No": "MH00ZZ0001", "Brand": "Test", "Model": "One", "Manufacturing_Year": 2024, "Vehicle_Type": "Car"})
        mechanic_id = self.repo.save_mechanic({"Name": "Test Mechanic", "Phone": "9000000009", "Specialization": "General", "Experience": 4})
        service_id = self.repo.save_service({"Service_Name": "Test Service", "Description": "Test work", "Labour_Cost": 100.00, "Estimated_Time": "1 hour"})
        part_id = self.repo.save_part({"Part_Name": "Test Filter", "Category": "Filters", "Unit_Price": part_price, "Quantity_Available": stock, "Reorder_Level": 2})
        job_id = self.repo.save_job({"Vehicle_ID": vehicle_id, "Mechanic_ID": mechanic_id, "Service_ID": service_id, "Service_Date": "2026-10-14", "Problem_Description": "Testing", "Service_Status": "Booked", "Remarks": ""})
        return job_id, part_id

    def test_inventory_trigger_deducts_restores_and_rejects_oversell(self) -> None:
        job_id, part_id = self.create_minimal_job(stock=10)
        line_id = self.repo.add_service_part(job_id, part_id, 4)
        stock = self.db.one("SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = ?", (part_id,))
        self.assertEqual(stock["Quantity_Available"], 6)

        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO `SERVICE_PART` (`Service_Record_ID`, `Part_ID`, `Quantity_Used`, `Cost`) VALUES (?, ?, ?, ?)",
                (job_id, part_id, 7, 87.50),
            )
        stock = self.db.one("SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = ?", (part_id,))
        self.assertEqual(stock["Quantity_Available"], 6, "a rejected insert must not change stock")

        self.db.execute("UPDATE `SERVICE_PART` SET `Quantity_Used` = ?, `Cost` = ? WHERE `Service_Part_ID` = ?", (5, 62.50, line_id))
        stock = self.db.one("SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = ?", (part_id,))
        self.assertEqual(stock["Quantity_Available"], 5)
        self.repo.remove_service_part(line_id)
        stock = self.db.one("SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = ?", (part_id,))
        self.assertEqual(stock["Quantity_Available"], 10)

    def test_invoice_calculation_and_history_view(self) -> None:
        job_id, part_id = self.create_minimal_job(stock=10, part_price=12.50)
        self.repo.add_service_part(job_id, part_id, 2)
        invoice_id = self.repo.create_or_refresh_invoice(job_id, 18)
        invoice = self.db.one("SELECT * FROM `INVOICE` WHERE `Invoice_ID` = ?", (invoice_id,))
        self.assertEqual(float(invoice["Labour_Amount"]), 100.00)
        self.assertEqual(float(invoice["Parts_Amount"]), 25.00)
        self.assertEqual(float(invoice["Tax"]), 22.50)
        self.assertEqual(float(invoice["Total_Amount"]), 147.50)
        self.assertEqual(invoice["Payment_Status"], "Unpaid")

        history = self.repo.get_history_details(job_id)
        self.assertEqual(history["Registration_No"], "MH00ZZ0001")
        self.assertEqual(history["Service_Name"], "Test Service")
        self.assertEqual(history["Invoice_ID"], invoice_id)
        self.assertEqual(len(history["parts"]), 1)

    def test_foreign_keys_and_searchable_crud(self) -> None:
        job_id, part_id = self.create_minimal_job()
        self.assertEqual(len(self.repo.list_customers("Test Customer")), 1)
        self.assertEqual(len(self.repo.list_vehicles("MH00ZZ0001")), 1)
        self.assertEqual(len(self.repo.list_jobs("Testing")), 1)
        # A referenced vehicle cannot be removed while its job exists.
        vehicle = self.db.one("SELECT `Vehicle_ID` FROM `VEHICLE` WHERE `Registration_No` = ?", ("MH00ZZ0001",))
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.delete_entity("vehicles", int(vehicle["Vehicle_ID"]))
        self.assertIsNotNone(self.repo.get_job(job_id))

    def test_demo_seed_is_idempotent_and_has_low_stock_example(self) -> None:
        self.assertTrue(seed_demo(self.db))
        self.assertFalse(seed_demo(self.db))
        self.assertEqual(len(self.repo.list_customers()), 3)
        self.assertGreaterEqual(len(self.repo.list_jobs()), 3)
        self.assertTrue(any(row["Part_Name"] == "Brake Pad Set" for row in self.repo.list_low_stock()))
        summary = self.repo.dashboard_summary()
        self.assertEqual(summary["Customers"], 3)
        self.assertGreaterEqual(summary["Low_Stock"], 1)
        billing = self.repo.billing_analytics()
        self.assertEqual(billing["Invoice_Count"], 1)
        self.assertGreater(float(billing["Total_Billed"]), 0)
        self.assertGreater(float(billing["Largest_Invoice"]), 0)
        self.assertEqual(len(self.repo.service_analytics()), 4)
        self.assertTrue(self.repo.part_usage_analytics())


if __name__ == "__main__":
    unittest.main()
