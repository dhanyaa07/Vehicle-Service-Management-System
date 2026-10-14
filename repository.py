"""Application queries and CRUD operations for the service-centre database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from database import Database


ENTITY_FIELDS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "customers": ("CUSTOMER", "Customer_ID", ("Name", "Phone", "Email", "Address")),
    "vehicles": (
        "VEHICLE",
        "Vehicle_ID",
        ("Customer_ID", "Registration_No", "Brand", "Model", "Manufacturing_Year", "Vehicle_Type"),
    ),
    "mechanics": ("MECHANIC", "Mechanic_ID", ("Name", "Phone", "Specialization", "Experience")),
    "services": ("SERVICE", "Service_ID", ("Service_Name", "Description", "Labour_Cost", "Estimated_Time")),
    "parts": ("SPARE_PART", "Part_ID", ("Part_Name", "Category", "Unit_Price", "Quantity_Available", "Reorder_Level")),
    "jobs": (
        "SERVICE_RECORD",
        "Service_Record_ID",
        ("Vehicle_ID", "Mechanic_ID", "Service_ID", "Service_Date", "Problem_Description", "Service_Status", "Remarks"),
    ),
}


class ServiceRepository:
    def __init__(self, database: Database):
        self.db = database

    def _save(self, entity: str, values: dict[str, Any], record_id: int | None = None) -> int:
        if entity not in ENTITY_FIELDS:
            raise ValueError(f"Unknown entity: {entity}")
        table, id_column, allowed = ENTITY_FIELDS[entity]
        unknown = set(values) - set(allowed)
        if unknown:
            raise ValueError(f"Unexpected fields for {entity}: {', '.join(sorted(unknown))}")
        columns = [field for field in allowed if field in values]
        if not columns:
            raise ValueError("There is nothing to save.")
        params = [values[field] for field in columns]
        with self.db.transaction() as session:
            if record_id is None:
                names = ", ".join(f"`{column}`" for column in columns)
                marks = ", ".join("?" for _ in columns)
                result = session.execute(
                    f"INSERT INTO `{table}` ({names}) VALUES ({marks})", params
                )
                return int(result.lastrowid or 0)
            assignments = ", ".join(f"`{column}` = ?" for column in columns)
            session.execute(
                f"UPDATE `{table}` SET {assignments} WHERE `{id_column}` = ?",
                [*params, record_id],
            )
            return int(record_id)

    def save_customer(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("customers", values, record_id)

    def save_vehicle(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("vehicles", values, record_id)

    def save_mechanic(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("mechanics", values, record_id)

    def save_service(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("services", values, record_id)

    def save_part(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("parts", values, record_id)

    def save_job(self, values: dict[str, Any], record_id: int | None = None) -> int:
        return self._save("jobs", values, record_id)

    def delete_entity(self, entity: str, record_id: int) -> None:
        if entity not in ENTITY_FIELDS:
            raise ValueError(f"Unknown entity: {entity}")
        table, id_column, _ = ENTITY_FIELDS[entity]
        self.db.execute(f"DELETE FROM `{table}` WHERE `{id_column}` = ?", (record_id,))

    @staticmethod
    def _like(value: str) -> str:
        return f"%{value.strip()}%"

    def list_customers(self, search: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM `CUSTOMER`"
        params: list[Any] = []
        if search.strip():
            sql += " WHERE `Name` LIKE ? OR `Phone` LIKE ? OR `Email` LIKE ? OR `Address` LIKE ?"
            params = [self._like(search)] * 4
        sql += " ORDER BY `Name`, `Customer_ID`"
        return self.db.query(sql, params)

    def list_vehicles(self, search: str = "") -> list[dict[str, Any]]:
        sql = """SELECT v.*, c.`Name` AS `Customer_Name`
                 FROM `VEHICLE` v JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`"""
        params: list[Any] = []
        if search.strip():
            sql += " WHERE v.`Registration_No` LIKE ? OR v.`Brand` LIKE ? OR v.`Model` LIKE ? OR c.`Name` LIKE ?"
            params = [self._like(search)] * 4
        sql += " ORDER BY v.`Registration_No`"
        return self.db.query(sql, params)

    def list_mechanics(self, search: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM `MECHANIC`"
        params: list[Any] = []
        if search.strip():
            sql += " WHERE `Name` LIKE ? OR `Phone` LIKE ? OR `Specialization` LIKE ?"
            params = [self._like(search)] * 3
        sql += " ORDER BY `Name`, `Mechanic_ID`"
        return self.db.query(sql, params)

    def list_services(self, search: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM `SERVICE`"
        params: list[Any] = []
        if search.strip():
            sql += " WHERE `Service_Name` LIKE ? OR `Description` LIKE ?"
            params = [self._like(search)] * 2
        sql += " ORDER BY `Service_Name`"
        return self.db.query(sql, params)

    def list_parts(self, search: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM `SPARE_PART`"
        params: list[Any] = []
        if search.strip():
            sql += " WHERE `Part_Name` LIKE ? OR `Category` LIKE ?"
            params = [self._like(search)] * 2
        sql += " ORDER BY CASE WHEN `Quantity_Available` <= `Reorder_Level` THEN 0 ELSE 1 END, `Part_Name`"
        return self.db.query(sql, params)

    def list_low_stock(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM `V_LOW_STOCK` ORDER BY `Quantity_Available`, `Part_Name`")

    def list_jobs(self, search: str = "", status: str = "All") -> list[dict[str, Any]]:
        sql = """SELECT sr.*, v.`Registration_No`, v.`Brand`, v.`Model`,
                         c.`Name` AS `Customer_Name`, m.`Name` AS `Mechanic_Name`,
                         s.`Service_Name`, s.`Labour_Cost`,
                         COALESCE(i.`Total_Amount`, 0) AS `Total_Amount`,
                         (SELECT COUNT(*) FROM `SERVICE_PART` sp
                          WHERE sp.`Service_Record_ID` = sr.`Service_Record_ID`) AS `Parts_Count`
                  FROM `SERVICE_RECORD` sr
                  JOIN `VEHICLE` v ON v.`Vehicle_ID` = sr.`Vehicle_ID`
                  JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`
                  JOIN `MECHANIC` m ON m.`Mechanic_ID` = sr.`Mechanic_ID`
                  JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`
                  LEFT JOIN `INVOICE` i ON i.`Service_Record_ID` = sr.`Service_Record_ID`
                  WHERE 1 = 1"""
        params: list[Any] = []
        if status and status != "All":
            sql += " AND sr.`Service_Status` = ?"
            params.append(status)
        if search.strip():
            sql += " AND (v.`Registration_No` LIKE ? OR c.`Name` LIKE ? OR m.`Name` LIKE ? OR s.`Service_Name` LIKE ? OR sr.`Problem_Description` LIKE ? OR CAST(sr.`Service_Record_ID` AS CHAR) LIKE ?)"
            params.extend([self._like(search)] * 6)
        sql += " ORDER BY sr.`Service_Date` DESC, sr.`Service_Record_ID` DESC"
        return self.db.query(sql, params)

    def get_job(self, service_record_id: int) -> dict[str, Any] | None:
        return self.db.one(
            "SELECT * FROM `SERVICE_RECORD` WHERE `Service_Record_ID` = ?", (service_record_id,)
        )

    def list_service_parts(self, service_record_id: int) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT sp.`Service_Part_ID`, sp.`Service_Record_ID`, sp.`Part_ID`,
                      p.`Part_Name`, sp.`Quantity_Used`, p.`Unit_Price`, sp.`Cost`
               FROM `SERVICE_PART` sp JOIN `SPARE_PART` p ON p.`Part_ID` = sp.`Part_ID`
               WHERE sp.`Service_Record_ID` = ? ORDER BY sp.`Service_Part_ID`""",
            (service_record_id,),
        )

    def add_service_part(self, service_record_id: int, part_id: int, quantity: int) -> int:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        with self.db.transaction() as session:
            part = session.one(
                "SELECT `Unit_Price`, `Quantity_Available`, `Part_Name` FROM `SPARE_PART` WHERE `Part_ID` = ?",
                (part_id,),
            )
            if not part:
                raise ValueError("That spare part no longer exists.")
            if int(part["Quantity_Available"]) < quantity:
                raise ValueError(
                    f"Not enough stock for {part['Part_Name']}. Available: {part['Quantity_Available']}."
                )
            unit_price = Decimal(str(part["Unit_Price"] or 0))
            cost = (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            result = session.execute(
                """INSERT INTO `SERVICE_PART`
                   (`Service_Record_ID`, `Part_ID`, `Quantity_Used`, `Cost`)
                   VALUES (?, ?, ?, ?)""",
                (service_record_id, part_id, quantity, float(cost)),
            )
            return int(result.lastrowid or 0)

    def remove_service_part(self, service_part_id: int) -> None:
        # The database delete trigger automatically returns quantity to inventory.
        self.db.execute("DELETE FROM `SERVICE_PART` WHERE `Service_Part_ID` = ?", (service_part_id,))

    def list_invoices(self, search: str = "") -> list[dict[str, Any]]:
        sql = """SELECT i.*, sr.`Service_Record_ID`, v.`Registration_No`,
                         c.`Name` AS `Customer_Name`, s.`Service_Name`
                  FROM `INVOICE` i
                  JOIN `SERVICE_RECORD` sr ON sr.`Service_Record_ID` = i.`Service_Record_ID`
                  JOIN `VEHICLE` v ON v.`Vehicle_ID` = sr.`Vehicle_ID`
                  JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`
                  JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`"""
        params: list[Any] = []
        if search.strip():
            sql += " WHERE v.`Registration_No` LIKE ? OR c.`Name` LIKE ? OR s.`Service_Name` LIKE ? OR CAST(i.`Invoice_ID` AS CHAR) LIKE ?"
            params = [self._like(search)] * 4
        sql += " ORDER BY i.`Invoice_Date` DESC, i.`Invoice_ID` DESC"
        return self.db.query(sql, params)

    def create_or_refresh_invoice(self, service_record_id: int, tax_percent: Decimal | float | str) -> int:
        try:
            rate = Decimal(str(tax_percent))
        except Exception as exc:
            raise ValueError("Enter a valid tax percentage.") from exc
        if rate < 0 or rate > 100:
            raise ValueError("Tax percentage must be between 0 and 100.")

        today = date.today().isoformat()
        with self.db.transaction() as session:
            job = session.one(
                """SELECT sr.`Service_Record_ID`, s.`Labour_Cost`
                   FROM `SERVICE_RECORD` sr JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`
                   WHERE sr.`Service_Record_ID` = ?""",
                (service_record_id,),
            )
            if not job:
                raise ValueError("The selected service record could not be found.")
            parts_row = session.one(
                "SELECT COALESCE(SUM(`Cost`), 0) AS `Parts_Amount` FROM `SERVICE_PART` WHERE `Service_Record_ID` = ?",
                (service_record_id,),
            ) or {"Parts_Amount": 0}
            labour = Decimal(str(job["Labour_Cost"] or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            parts = Decimal(str(parts_row["Parts_Amount"] or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax = ((labour + parts) * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total = (labour + parts + tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            existing = session.one(
                "SELECT `Invoice_ID` FROM `INVOICE` WHERE `Service_Record_ID` = ?",
                (service_record_id,),
            )
            if existing:
                invoice_id = int(existing["Invoice_ID"])
                session.execute(
                    """UPDATE `INVOICE` SET `Invoice_Date` = ?, `Labour_Amount` = ?,
                       `Parts_Amount` = ?, `Tax` = ?, `Total_Amount` = ? WHERE `Invoice_ID` = ?""",
                    (today, float(labour), float(parts), float(tax), float(total), invoice_id),
                )
                return invoice_id
            result = session.execute(
                """INSERT INTO `INVOICE`
                   (`Service_Record_ID`, `Invoice_Date`, `Labour_Amount`, `Parts_Amount`, `Tax`, `Total_Amount`, `Payment_Status`)
                   VALUES (?, ?, ?, ?, ?, ?, 'Unpaid')""",
                (service_record_id, today, float(labour), float(parts), float(tax), float(total)),
            )
            return int(result.lastrowid or 0)

    def set_invoice_payment_status(self, invoice_id: int, payment_status: str) -> None:
        if payment_status not in {"Unpaid", "Partial", "Paid"}:
            raise ValueError("Choose Unpaid, Partial or Paid.")
        self.db.execute(
            "UPDATE `INVOICE` SET `Payment_Status` = ? WHERE `Invoice_ID` = ?",
            (payment_status, invoice_id),
        )

    def get_invoice_details(self, invoice_id: int) -> dict[str, Any] | None:
        invoice = self.db.one(
            """SELECT i.*, sr.`Problem_Description`, sr.`Remarks`, sr.`Service_Date`,
                      sr.`Service_Record_ID`, sr.`Service_Status`,
                      v.`Registration_No`, v.`Brand`, v.`Model`,
                      c.`Name` AS `Customer_Name`, c.`Phone` AS `Customer_Phone`,
                      c.`Email` AS `Customer_Email`, c.`Address` AS `Customer_Address`,
                      m.`Name` AS `Mechanic_Name`, s.`Service_Name`
               FROM `INVOICE` i
               JOIN `SERVICE_RECORD` sr ON sr.`Service_Record_ID` = i.`Service_Record_ID`
               JOIN `VEHICLE` v ON v.`Vehicle_ID` = sr.`Vehicle_ID`
               JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`
               JOIN `MECHANIC` m ON m.`Mechanic_ID` = sr.`Mechanic_ID`
               JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`
               WHERE i.`Invoice_ID` = ?""",
            (invoice_id,),
        )
        if invoice:
            invoice["parts"] = self.list_service_parts(int(invoice["Service_Record_ID"]))
        return invoice

    def search_history(self, search: str = "") -> list[dict[str, Any]]:
        sql = """SELECT h.*,
                         (SELECT COUNT(*) FROM `SERVICE_PART` sp
                          WHERE sp.`Service_Record_ID` = h.`Service_Record_ID`) AS `Parts_Count`
                  FROM `V_SERVICE_HISTORY` h"""
        params: list[Any] = []
        if search.strip():
            wildcard = self._like(search)
            sql += " WHERE h.`Registration_No` LIKE ? OR h.`Customer_Name` LIKE ? OR h.`Service_Name` LIKE ? OR h.`Problem_Description` LIKE ? OR CAST(h.`Service_Record_ID` AS CHAR) LIKE ?"
            params = [wildcard] * 5
        sql += " ORDER BY h.`Service_Date` DESC, h.`Service_Record_ID` DESC"
        return self.db.query(sql, params)

    def get_history_details(self, service_record_id: int) -> dict[str, Any] | None:
        details = self.db.one(
            "SELECT * FROM `V_SERVICE_HISTORY` WHERE `Service_Record_ID` = ?",
            (service_record_id,),
        )
        if details:
            details["parts"] = self.list_service_parts(service_record_id)
        return details

    def dashboard_summary(self) -> dict[str, Any]:
        row = self.db.one(
            """SELECT
                 (SELECT COUNT(*) FROM `CUSTOMER`) AS `Customers`,
                 (SELECT COUNT(*) FROM `VEHICLE`) AS `Vehicles`,
                 (SELECT COUNT(*) FROM `SERVICE_RECORD` WHERE `Service_Status` IN ('Booked', 'In Progress')) AS `Active_Jobs`,
                 (SELECT COUNT(*) FROM `V_LOW_STOCK`) AS `Low_Stock`,
                 (SELECT COALESCE(SUM(`Total_Amount`), 0) FROM `INVOICE` WHERE `Payment_Status` = 'Paid') AS `Paid_Revenue`"""
        )
        return row or {"Customers": 0, "Vehicles": 0, "Active_Jobs": 0, "Low_Stock": 0, "Paid_Revenue": 0}

    def billing_analytics(self) -> dict[str, Any]:
        row = self.db.one(
            """SELECT COUNT(*) AS `Invoice_Count`,
                      COALESCE(SUM(`Total_Amount`), 0) AS `Total_Billed`,
                      COALESCE(AVG(`Total_Amount`), 0) AS `Average_Invoice`,
                      COALESCE(MAX(`Total_Amount`), 0) AS `Largest_Invoice`,
                      COALESCE(MIN(`Total_Amount`), 0) AS `Smallest_Invoice`,
                      COALESCE(SUM(CASE WHEN `Payment_Status` = 'Paid' THEN `Total_Amount` ELSE 0 END), 0) AS `Paid_Revenue`
               FROM `INVOICE`"""
        )
        return row or {}

    def service_analytics(self) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT s.`Service_ID`, s.`Service_Name`,
                      COUNT(sr.`Service_Record_ID`) AS `Jobs_Count`,
                      COALESCE(AVG(s.`Labour_Cost`), 0) AS `Average_Labour`,
                      COALESCE(SUM(i.`Total_Amount`), 0) AS `Invoiced_Amount`
               FROM `SERVICE` s
               LEFT JOIN `SERVICE_RECORD` sr ON sr.`Service_ID` = s.`Service_ID`
               LEFT JOIN `INVOICE` i ON i.`Service_Record_ID` = sr.`Service_Record_ID`
               GROUP BY s.`Service_ID`, s.`Service_Name`, s.`Labour_Cost`
               ORDER BY `Jobs_Count` DESC, s.`Service_Name`"""
        )

    def job_status_analytics(self) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT `Service_Status`, COUNT(*) AS `Jobs_Count` FROM `SERVICE_RECORD` GROUP BY `Service_Status` ORDER BY `Jobs_Count` DESC, `Service_Status`"
        )

    def part_usage_analytics(self) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT p.`Part_ID`, p.`Part_Name`,
                      COALESCE(SUM(sp.`Quantity_Used`), 0) AS `Quantity_Used`,
                      COALESCE(SUM(sp.`Cost`), 0) AS `Total_Cost`
               FROM `SPARE_PART` p
               LEFT JOIN `SERVICE_PART` sp ON sp.`Part_ID` = p.`Part_ID`
               GROUP BY p.`Part_ID`, p.`Part_Name`
               HAVING COALESCE(SUM(sp.`Quantity_Used`), 0) > 0
               ORDER BY `Quantity_Used` DESC, p.`Part_Name`"""
        )

    def recent_jobs(self, limit: int = 8) -> list[dict[str, Any]]:
        return self.db.query(
            """SELECT sr.`Service_Record_ID`, sr.`Service_Date`, sr.`Service_Status`,
                      v.`Registration_No`, c.`Name` AS `Customer_Name`, s.`Service_Name`
               FROM `SERVICE_RECORD` sr
               JOIN `VEHICLE` v ON v.`Vehicle_ID` = sr.`Vehicle_ID`
               JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`
               JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`
               ORDER BY sr.`Service_Date` DESC, sr.`Service_Record_ID` DESC LIMIT ?""",
            (int(limit),),
        )
