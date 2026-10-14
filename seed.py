"""Optional sample data for a first-run walkthrough of the desktop application."""

from __future__ import annotations

from datetime import date, timedelta

from database import Database
from repository import ServiceRepository


def seed_demo(database: Database) -> bool:
    """Seed a compact fictional Mumbai workshop dataset if the database is empty."""
    count = database.one("SELECT COUNT(*) AS `total` FROM `CUSTOMER`") or {"total": 0}
    if int(count["total"]) > 0:
        return False

    today = date.today()
    with database.transaction() as session:
        customers = [
            ("Asha Kulkarni", "9000000001", "asha@example.test", "Dadar, Mumbai"),
            ("Rahul Mehta", "9000000002", "rahul@example.test", "Andheri, Mumbai"),
            ("Neha Shah", "9000000003", "neha@example.test", "Thane, Maharashtra"),
        ]
        customer_ids: list[int] = []
        for name, phone, email, address in customers:
            result = session.execute(
                "INSERT INTO `CUSTOMER` (`Name`, `Phone`, `Email`, `Address`) VALUES (?, ?, ?, ?)",
                (name, phone, email, address),
            )
            customer_ids.append(int(result.lastrowid or 0))

        vehicles = [
            (customer_ids[0], "MH02AB1234", "Honda", "City", 2020, "Car"),
            (customer_ids[1], "MH01CD5678", "Hyundai", "i20", 2022, "Car"),
            (customer_ids[2], "MH03EF4567", "TVS", "Jupiter", 2021, "Scooter"),
        ]
        vehicle_ids: list[int] = []
        for vehicle in vehicles:
            result = session.execute(
                """INSERT INTO `VEHICLE`
                   (`Customer_ID`, `Registration_No`, `Brand`, `Model`, `Manufacturing_Year`, `Vehicle_Type`)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                vehicle,
            )
            vehicle_ids.append(int(result.lastrowid or 0))

        mechanics = [
            ("S. Patil", "9000000011", "Engine & general service", 8),
            ("M. Shaikh", "9000000012", "Brakes & suspension", 5),
            ("R. Nair", "9000000013", "Electrical systems", 6),
        ]
        mechanic_ids: list[int] = []
        for mechanic in mechanics:
            result = session.execute(
                "INSERT INTO `MECHANIC` (`Name`, `Phone`, `Specialization`, `Experience`) VALUES (?, ?, ?, ?)",
                mechanic,
            )
            mechanic_ids.append(int(result.lastrowid or 0))

        services = [
            ("General Service", "Periodic inspection, fluids and routine maintenance", 1450.00, "2-3 hours"),
            ("Oil Change", "Engine oil and filter replacement", 650.00, "1 hour"),
            ("Brake Inspection", "Brake inspection and adjustment", 850.00, "1-2 hours"),
            ("Battery Check", "Battery and charging-system test", 350.00, "45 minutes"),
        ]
        service_ids: list[int] = []
        for service in services:
            result = session.execute(
                "INSERT INTO `SERVICE` (`Service_Name`, `Description`, `Labour_Cost`, `Estimated_Time`) VALUES (?, ?, ?, ?)",
                service,
            )
            service_ids.append(int(result.lastrowid or 0))

        parts = [
            ("Engine Oil 4L", "Fluids", 1850.00, 18, 5),
            ("Oil Filter", "Filters", 420.00, 14, 5),
            ("Brake Pad Set", "Brakes", 1650.00, 3, 4),
            ("Air Filter", "Filters", 520.00, 6, 4),
            ("Spark Plug", "Ignition", 280.00, 20, 6),
        ]
        part_ids: list[int] = []
        for part in parts:
            result = session.execute(
                """INSERT INTO `SPARE_PART`
                   (`Part_Name`, `Category`, `Unit_Price`, `Quantity_Available`, `Reorder_Level`)
                   VALUES (?, ?, ?, ?, ?)""",
                part,
            )
            part_ids.append(int(result.lastrowid or 0))

        jobs = [
            (vehicle_ids[0], mechanic_ids[0], service_ids[0], (today - timedelta(days=4)).isoformat(), "Routine 40,000 km service", "Completed", "Road test completed; next check in 6 months."),
            (vehicle_ids[1], mechanic_ids[2], service_ids[1], today.isoformat(), "Oil change and filter replacement", "In Progress", "Awaiting final inspection."),
            (vehicle_ids[2], mechanic_ids[1], service_ids[2], (today + timedelta(days=1)).isoformat(), "Front brake noise", "Booked", "Customer prefers a morning appointment."),
        ]
        job_ids: list[int] = []
        for job in jobs:
            result = session.execute(
                """INSERT INTO `SERVICE_RECORD`
                   (`Vehicle_ID`, `Mechanic_ID`, `Service_ID`, `Service_Date`, `Problem_Description`, `Service_Status`, `Remarks`)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                job,
            )
            job_ids.append(int(result.lastrowid or 0))

    repository = ServiceRepository(database)
    # The same database trigger used by the UI subtracts the sample parts from stock.
    repository.add_service_part(job_ids[0], part_ids[0], 1)
    repository.add_service_part(job_ids[0], part_ids[1], 1)
    repository.add_service_part(job_ids[1], part_ids[0], 1)
    repository.create_or_refresh_invoice(job_ids[0], 18)
    invoice = database.one(
        "SELECT `Invoice_ID` FROM `INVOICE` WHERE `Service_Record_ID` = ?", (job_ids[0],)
    )
    if invoice:
        repository.set_invoice_payment_status(int(invoice["Invoice_ID"]), "Paid")
    return True
