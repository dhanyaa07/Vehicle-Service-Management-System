# GearDesk — Vehicle Service & Maintenance Management System

A Python desktop project built from the supplied DBMS report. It uses **Tkinter** for the front end and a relational database for customers, vehicles, mechanics, service bookings, spare parts, usage history and invoices.

## Implemented features

- Customer, vehicle, mechanic, service-catalogue and spare-part CRUD screens.
- Service booking with vehicle, mechanic, service, date, reported problem, status and remarks.
- Job statuses: `Booked`, `In Progress`, `Completed` and `Cancelled`.
- Add/remove spare parts against a service job. A database trigger deducts stock on insert, validates available quantity, and restores stock if a usage line is removed.
- Low-stock view and inventory highlighting when available stock is at/below the reorder level.
- Invoice calculation from catalogue labour cost plus recorded part costs, with an editable tax percentage (defaults to 18%). Payment status can be tracked as `Unpaid`, `Partial` or `Paid`.
- Searchable service history, dashboard summaries, CSV exports and print-ready HTML invoice export.
- Reports for invoice count/sum/average/min/max, job-status counts, service popularity and parts usage.
- Primary/foreign keys, uniqueness and check constraints, indexes, a service-history view and a low-stock view.
- SQLite for zero-setup demos, plus a MySQL schema and connector for the report's MySQL deployment target.

## Requirements

- Python 3.10 or newer.
- Tkinter (normally included with Python; on some Linux distributions install the OS package `python3-tk`).
- **Optional:** `mysql-connector-python` if using MySQL. No pip package is needed for the default SQLite run.

## Run the SQLite demo

1. Extract the project folder.
2. Open a terminal in that folder.
3. Start the app:

   ```bash
   python main.py
   ```

On first launch, GearDesk creates `data/vehicle_service.db` and loads a small fictional sample workshop if the database is empty. The dashboard, history, low-stock list and invoice screen will therefore have sample records to explore.

To create an empty SQLite database instead:

```bash
python main.py --no-seed
```

To initialize/check the database without opening the desktop window:

```bash
python main.py --check-db
```

The sample database is persistent. Delete `data/vehicle_service.db` to recreate it from scratch on the next default launch. Sample contacts and vehicle details are fictional demonstration data.

## Use MySQL (report configuration)

The provided app defaults to SQLite so it runs immediately. To use MySQL 8.0.16 or newer:

1. Create a database. For the default name, run `scripts/create_database.sql` as a MySQL administrator, or execute:

   ```sql
   CREATE DATABASE vehicle_service_db
     CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. Install the connector:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Set the environment variables before launching. Example for macOS/Linux:

   ```bash
   export DB_BACKEND=mysql
   export DB_HOST=127.0.0.1
   export DB_PORT=3306
   export DB_NAME=vehicle_service_db
   export DB_USER=root
   export DB_PASSWORD='your-password'
   # Optional: leave unset for an empty MySQL database; set to 1 for sample data.
   export SEED_DEMO=0
   python main.py
   ```

   PowerShell example:

   ```powershell
   $env:DB_BACKEND = 'mysql'
   $env:DB_HOST = '127.0.0.1'
   $env:DB_PORT = '3306'
   $env:DB_NAME = 'vehicle_service_db'
   $env:DB_USER = 'root'
   $env:DB_PASSWORD = 'your-password'
   $env:SEED_DEMO = '0'
   python main.py
   ```

At start-up the application creates the tables, indexes, views and inventory triggers in the selected MySQL database. Keep credentials in environment variables; do not commit real passwords. You can also copy `.env.example` as a reminder of the supported settings—this project intentionally does not load `.env` files automatically.

## Database design

| Table | Purpose |
| --- | --- |
| `CUSTOMER` | Customer name and contact details |
| `VEHICLE` | Registration, manufacturer/model, type and owning customer |
| `MECHANIC` | Mechanic contact, specialization and experience |
| `SERVICE` | Service catalogue and labour pricing |
| `SERVICE_RECORD` | Vehicle service job, assigned mechanic, date, problem and status |
| `SPARE_PART` | Part price, on-hand quantity and reorder level |
| `SERVICE_PART` | Parts used on a service record and historical line cost |
| `INVOICE` | One invoice per service record, amounts, tax and payment status |

The report's automatic stock-update behavior is implemented with database triggers, not only application code. `SERVICE_PART` insert/update/delete triggers validate stock and adjust `SPARE_PART.Quantity_Available`. A failed stock check aborts the transaction, so stock cannot become negative through the app or direct SQL.

## Tests

From the project folder run:

```bash
python -m unittest discover -s tests -v
```

The SQLite tests cover the trigger lifecycle, insufficient-stock protection, foreign-key-backed workflow, service-history view and invoice arithmetic. They create temporary databases and do not alter your demo data.

## Project files

```text
main.py                 Desktop launcher
app.py                  Tkinter screens and dialogs
database.py             SQLite/MySQL connection, schema bootstrap and transactions
repository.py           CRUD queries, billing and service-history queries
seed.py                 Optional first-run fictional sample data
schema_sqlite.sql       SQLite tables, views and inventory triggers
schema_mysql.sql        MySQL 8 schema, views and inventory triggers
ER_DIAGRAM.svg          Visual entity–relationship diagram
ER_DIAGRAM.md           Relationship and ER-to-relational mapping
scripts/create_database.sql  One-time MySQL database creation
tests/test_database.py  SQLite workflow and trigger tests
```

## Project Overview

Vehicle Service Management System for managing vehicle service operations.

## Environment Setup

Configure local environment variables using .env.example.

## Install Dependencies

Install dependencies using pip install -r requirements.txt.

## Running the Application

Use the documented project entry point to start the application.

## Database Support

The project includes SQLite and MySQL schema files.

## Database Design

Refer to ER_DIAGRAM.md and ER_DIAGRAM.svg for the database design.
