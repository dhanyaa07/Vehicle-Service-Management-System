"""Launch the GearDesk Vehicle Service & Maintenance desktop application."""

from __future__ import annotations

import argparse
import os
import sys
import tkinter as tk
from tkinter import messagebox

from app import ServiceApp
from database import Database
from repository import ServiceRepository
from seed import seed_demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vehicle Service & Maintenance Management System")
    parser.add_argument("--check-db", action="store_true", help="initialize/check the database and exit")
    parser.add_argument("--no-seed", action="store_true", help="do not add first-run sample data")
    parser.add_argument("--seed-demo", action="store_true", help="add the sample dataset if the database is empty")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = Database.from_env()
    try:
        database.initialize()
        seed_enabled = args.seed_demo or (
            not args.no_seed and os.getenv("SEED_DEMO", "1" if database.backend == "sqlite" else "0").lower() in {"1", "true", "yes", "on"}
        )
        seeded = seed_demo(database) if seed_enabled else False
        if args.check_db:
            note = " Sample data added." if seeded else ""
            print(f"Database ready: {database.health()}.{note}")
            return 0
    except Exception as exc:
        if args.check_db:
            print(f"Database check failed: {exc}", file=sys.stderr)
            return 1
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("GearDesk could not start", str(exc), parent=root)
            root.destroy()
        except tk.TclError:
            print(f"GearDesk could not start: {exc}", file=sys.stderr)
        return 1

    root = tk.Tk()
    ServiceApp(root, database, ServiceRepository(database))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
