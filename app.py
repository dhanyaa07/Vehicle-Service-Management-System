"""Tkinter desktop user interface for the Vehicle Service & Maintenance System."""

from __future__ import annotations

import csv
import html
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from database import Database
from repository import ServiceRepository


BG = "#f3f5f9"
SURFACE = "#ffffff"
INK = "#172b4d"
MUTED = "#667085"
NAV = "#14243a"
NAV_HOVER = "#223954"
ACCENT = "#246bfd"
BORDER = "#e4e9f0"
GREEN = "#137a55"
AMBER = "#a15c00"
RED = "#b42318"


def money(value: Any) -> str:
    try:
        return f"₹{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


def field(
    key: str,
    label: str,
    kind: str = "text",
    *,
    required: bool = False,
    default: Any = "",
    options: list[tuple[str, Any]] | None = None,
    help_text: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "required": required,
        "default": default,
        "options": options or [],
        "help_text": help_text,
    }


class FormDialog(tk.Toplevel):
    """Small reusable, validated modal form for CRUD and workflow actions."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        fields: list[dict[str, Any]],
        initial: dict[str, Any] | None = None,
        submit_label: str = "Save",
        width: int = 520,
    ):
        super().__init__(parent)
        self.parent = parent
        self.fields = fields
        self.initial = initial or {}
        self.result: dict[str, Any] | None = None
        self.variables: dict[str, Any] = {}
        self.widgets: dict[str, Any] = {}
        self.option_maps: dict[str, dict[str, Any]] = {}
        self.title(title)
        self.configure(bg=BG)
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        outer = ttk.Frame(self, style="Page.TFrame", padding=(22, 18, 22, 18))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=title, style="DialogTitle.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(
            outer,
            text="Fields marked with * are required.",
            style="DialogHint.TLabel",
        ).pack(anchor="w", pady=(0, 13))

        form = ttk.Frame(outer, style="Page.TFrame")
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)
        row = 0
        for spec in self.fields:
            key = spec["key"]
            label_text = spec["label"] + (" *" if spec.get("required") else "")
            ttk.Label(form, text=label_text, style="FormLabel.TLabel").grid(
                row=row, column=0, sticky="nw", padx=(0, 16), pady=(5, 8)
            )
            kind = spec.get("kind", "text")
            value = self.initial.get(key, spec.get("default", ""))
            if value is None:
                value = ""
            if kind == "combo":
                display_values = [display for display, _ in spec.get("options", [])]
                option_map = {display: option_value for display, option_value in spec.get("options", [])}
                self.option_maps[key] = option_map
                selected = ""
                for display, option_value in spec.get("options", []):
                    if str(option_value) == str(value):
                        selected = display
                        break
                if not selected and value in ("", None) and display_values:
                    selected = ""
                var = tk.StringVar(value=selected)
                widget = ttk.Combobox(
                    form,
                    textvariable=var,
                    values=display_values,
                    state="readonly",
                    width=35,
                )
                if selected:
                    widget.set(selected)
                self.variables[key] = var
                self.widgets[key] = widget
                widget.grid(row=row, column=1, sticky="ew", pady=(2, 6))
            elif kind == "textarea":
                widget = tk.Text(
                    form,
                    height=3,
                    width=38,
                    wrap="word",
                    relief="solid",
                    borderwidth=1,
                    highlightthickness=1,
                    highlightbackground=BORDER,
                    highlightcolor=ACCENT,
                    font=("Segoe UI", 10),
                    padx=7,
                    pady=6,
                )
                widget.insert("1.0", str(value))
                widget.grid(row=row, column=1, sticky="ew", pady=(2, 6))
                self.widgets[key] = widget
            else:
                var = tk.StringVar(value=str(value))
                widget = ttk.Entry(form, textvariable=var, width=38)
                widget.grid(row=row, column=1, sticky="ew", pady=(2, 6))
                self.variables[key] = var
                self.widgets[key] = widget
            help_text = spec.get("help_text")
            if help_text:
                ttk.Label(form, text=help_text, style="FieldHelp.TLabel").grid(
                    row=row + 1, column=1, sticky="w", pady=(0, 7)
                )
                row += 1
            row += 1

        buttons = ttk.Frame(outer, style="Page.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", style="Secondary.TButton", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(buttons, text=submit_label, style="Primary.TButton", command=self._submit).pack(side="right")

        self.geometry(f"{width}x{min(690, max(300, 190 + len(fields) * 58))}")
        self.minsize(width - 40, 280)
        self.update_idletasks()
        self._center()
        self.grab_set()
        if fields:
            self.widgets[fields[0]["key"]].focus_set()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", self._on_return)

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.parent.winfo_toplevel()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _on_return(self, event: tk.Event) -> str | None:
        if isinstance(event.widget, tk.Text):
            return None
        self._submit()
        return "break"

    def _read_value(self, spec: dict[str, Any]) -> Any:
        key = spec["key"]
        kind = spec.get("kind", "text")
        widget = self.widgets[key]
        if kind == "textarea":
            return widget.get("1.0", "end-1c").strip()
        raw = self.variables[key].get().strip()
        if kind == "combo":
            if not raw:
                return None
            return self.option_maps[key][raw]
        if not raw:
            if kind in {"integer", "decimal"}:
                default = spec.get("default", "")
                if default not in (None, ""):
                    return int(default) if kind == "integer" else float(default)
            return None if kind in {"integer", "decimal"} else ""
        if kind == "integer":
            return int(raw)
        if kind == "decimal":
            return float(raw.replace(",", ""))
        if kind == "date":
            return raw
        return raw

    def _submit(self) -> None:
        values: dict[str, Any] = {}
        try:
            for spec in self.fields:
                key = spec["key"]
                raw = self._read_value(spec)
                if spec.get("required") and raw in (None, ""):
                    raise ValueError(f"{spec['label']} is required.")
                kind = spec.get("kind", "text")
                if kind == "date" and raw:
                    try:
                        date.fromisoformat(str(raw))
                    except ValueError as exc:
                        raise ValueError(f"{spec['label']} must use YYYY-MM-DD format.") from exc
                if key == "Email" and raw and ("@" not in str(raw) or "." not in str(raw).split("@")[-1]):
                    raise ValueError("Enter a valid email address, or leave it blank.")
                if isinstance(raw, (int, float)) and raw < 0:
                    raise ValueError(f"{spec['label']} cannot be negative.")
                values[key] = raw
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Check the form", str(exc), parent=self)
            return
        self.result = values
        self.destroy()


class EntityTablePage:
    """Searchable CRUD table used for customer, vehicle, mechanic, service and part data."""

    def __init__(self, app: "ServiceApp", parent: ttk.Frame, entity: str):
        self.app = app
        self.parent = parent
        self.entity = entity
        self.config = app.entity_config(entity)
        self.rows: list[dict[str, Any]] = []
        self.rows_by_id: dict[int, dict[str, Any]] = {}
        self.search_var = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self) -> None:
        page = ttk.Frame(self.parent, style="Page.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        toolbar = ttk.Frame(page, style="Page.TFrame")
        toolbar.pack(fill="x", pady=(0, 14))
        ttk.Label(toolbar, text=self.config["description"], style="Body.TLabel").pack(side="left")
        actions = ttk.Frame(toolbar, style="Page.TFrame")
        actions.pack(side="right")
        search = ttk.Entry(actions, textvariable=self.search_var, width=28)
        search.pack(side="left", padx=(0, 7))
        search.insert(0, "")
        search.bind("<Return>", lambda _event: self.refresh())
        ttk.Button(actions, text="Search", style="Secondary.TButton", command=self.refresh).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Export CSV", style="Secondary.TButton", command=self.export_csv).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="＋  Add new", style="Primary.TButton", command=self.add).pack(side="left")

        table_box = ttk.Frame(page, style="Card.TFrame", padding=8)
        table_box.pack(fill="both", expand=True)
        columns = self.config["columns"]
        self.tree = ttk.Treeview(table_box, columns=[item[0] for item in columns], show="headings", selectmode="browse")
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55, anchor=anchor, stretch=True)
        yscroll = ttk.Scrollbar(table_box, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)
        self.tree.tag_configure("low_stock", background="#fff5e8", foreground=AMBER)
        self.tree.bind("<Double-1>", lambda _event: self.edit())
        self.tree.bind("<Return>", lambda _event: self.edit())

        footer = ttk.Frame(page, style="Page.TFrame")
        footer.pack(fill="x", pady=(11, 0))
        self.count_label = ttk.Label(footer, text="", style="Muted.TLabel")
        self.count_label.pack(side="left")
        ttk.Button(footer, text="Edit selected", style="Secondary.TButton", command=self.edit).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Delete selected", style="Danger.TButton", command=self.delete).pack(side="right")

    def selected(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return self.rows_by_id.get(int(selection[0]))
        except (ValueError, KeyError):
            return None

    def refresh(self) -> None:
        try:
            self.rows = self.config["list"](self.search_var.get())
            self.rows_by_id = {int(row[self.config["id"]]): row for row in self.rows}
            for item in self.tree.get_children():
                self.tree.delete(item)
            for row in self.rows:
                values = [self.app.display_cell(key, row.get(key)) for key, *_ in self.config["columns"]]
                tags = ()
                if self.entity == "parts" and int(row.get("Quantity_Available") or 0) <= int(row.get("Reorder_Level") or 0):
                    tags = ("low_stock",)
                self.tree.insert("", "end", iid=str(row[self.config["id"]]), values=values, tags=tags)
            self.count_label.configure(text=f"{len(self.rows)} record{'s' if len(self.rows) != 1 else ''}")
        except Exception as exc:
            self.app.show_error("Could not load records", exc)

    def add(self) -> None:
        self._edit_record(None)

    def edit(self) -> None:
        row = self.selected()
        if not row:
            messagebox.showinfo("Select a record", "Select a row to edit first.", parent=self.app.root)
            return
        self._edit_record(row)

    def _edit_record(self, row: dict[str, Any] | None) -> None:
        cfg = self.config
        initial = dict(row or {})
        dlg = FormDialog(self.app.root, cfg["form_title"], cfg["fields"](), initial=initial)
        self.app.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            cfg["save"](dlg.result, int(row[cfg["id"]]) if row else None)
            self.refresh()
            self.app.set_status(f"{cfg['singular']} saved.")
        except Exception as exc:
            self.app.show_error("Could not save record", exc)

    def delete(self) -> None:
        row = self.selected()
        if not row:
            messagebox.showinfo("Select a record", "Select a row to delete first.", parent=self.app.root)
            return
        label = row.get(self.config.get("name_key", "Name"), f"record #{row[self.config['id']]}")
        if not messagebox.askyesno(
            "Delete record?",
            f"Delete {label}? This is allowed only when no other record depends on it.",
            parent=self.app.root,
        ):
            return
        try:
            self.config["delete"](int(row[self.config["id"]]))
            self.refresh()
            self.app.set_status(f"{self.config['singular']} deleted.")
        except Exception as exc:
            self.app.show_error("Record could not be deleted", exc)

    def export_csv(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to export", "There are no rows in this view.", parent=self.app.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.app.root,
            title="Export table",
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
            initialfile=f"{self.entity}.csv",
        )
        if not path:
            return
        try:
            keys = [item[0] for item in self.config["columns"]]
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.rows)
            self.app.set_status(f"Exported {len(self.rows)} rows to {Path(path).name}.")
            messagebox.showinfo("Export complete", f"Saved {len(self.rows)} rows to:\n{path}", parent=self.app.root)
        except Exception as exc:
            self.app.show_error("CSV export failed", exc)


class ServiceApp:
    NAV_ITEMS = [
        ("dashboard", "Overview", "⌂"),
        ("customers", "Customers", "C"),
        ("vehicles", "Vehicles", "V"),
        ("mechanics", "Mechanics", "M"),
        ("services", "Services", "S"),
        ("jobs", "Service jobs", "J"),
        ("parts", "Inventory", "I"),
        ("invoices", "Invoices", "₹"),
        ("history", "Service history", "H"),
        ("reports", "Reports & analytics", "R"),
    ]

    TITLES = {
        "dashboard": ("Workshop overview", "A clear view of today's workshop activity."),
        "customers": ("Customers", "Manage customer contact details."),
        "vehicles": ("Vehicles", "Connect each vehicle to its owner and service history."),
        "mechanics": ("Mechanics", "Maintain mechanic profiles and specializations."),
        "services": ("Service catalogue", "Set the labour price and estimated duration for each service."),
        "jobs": ("Service jobs", "Book work, assign a mechanic, track progress and parts used."),
        "parts": ("Spare-part inventory", "Track stock, prices and reorder levels."),
        "invoices": ("Invoices & payments", "Calculate service charges and record payment status."),
        "history": ("Vehicle service history", "Find past services by registration, customer, job or issue."),
        "reports": ("Reports & analytics", "Use grouped summaries and aggregate functions across workshop records."),
    }

    def __init__(self, root: tk.Tk, database: Database, repository: ServiceRepository):
        self.root = root
        self.database = database
        self.repo = repository
        self.current_page = "dashboard"
        self.page_object: Any = None
        self.nav_buttons: dict[str, ttk.Button] = {}
        self.status_var = tk.StringVar(value="Ready")
        self._configure_styles()
        self._build_shell()
        self.show_page("dashboard")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10), foreground=INK)
        style.configure("App.TFrame", background=BG)
        style.configure("Page.TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE, relief="solid", borderwidth=1)
        style.configure("Sidebar.TFrame", background=NAV)
        style.configure("Body.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("HeaderTitle.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 21))
        style.configure("HeaderSub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardLabel.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("CardValue.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 21))
        style.configure("CardSub.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("SectionTitle.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 12))
        style.configure("SectionHint.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("DialogTitle.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 15))
        style.configure("DialogHint.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("FormLabel.TLabel", background=BG, foreground=INK, font=("Segoe UI", 9))
        style.configure("FieldHelp.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 8))
        style.configure("BrandTitle.TLabel", background=NAV, foreground="#ffffff", font=("Segoe UI Semibold", 15))
        style.configure("BrandSub.TLabel", background=NAV, foreground="#a8b6c8", font=("Segoe UI", 9))
        style.configure("Nav.TButton", background=NAV, foreground="#d5dfeb", anchor="w", padding=(13, 10), borderwidth=0, font=("Segoe UI", 10))
        style.map("Nav.TButton", background=[("active", NAV_HOVER)], foreground=[("active", "#ffffff")])
        style.configure("NavSelected.TButton", background="#28415e", foreground="#ffffff", anchor="w", padding=(13, 10), borderwidth=0, font=("Segoe UI Semibold", 10))
        style.map("NavSelected.TButton", background=[("active", "#2f4d70")], foreground=[("active", "#ffffff")])
        style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff", padding=(12, 8), borderwidth=0, font=("Segoe UI Semibold", 9))
        style.map("Primary.TButton", background=[("active", "#1555d6"), ("disabled", "#9ab8ff")], foreground=[("disabled", "#f7faff")])
        style.configure("Secondary.TButton", background="#ffffff", foreground=INK, padding=(10, 7), borderwidth=1, relief="solid", bordercolor=BORDER, font=("Segoe UI", 9))
        style.map("Secondary.TButton", background=[("active", "#f0f4f9")])
        style.configure("Danger.TButton", background="#fff3f1", foreground=RED, padding=(10, 7), borderwidth=1, relief="solid", bordercolor="#f4c7c2", font=("Segoe UI", 9))
        style.map("Danger.TButton", background=[("active", "#fde2df")])
        style.configure("TEntry", padding=(8, 7), fieldbackground="#ffffff")
        style.configure("TCombobox", padding=(6, 5), fieldbackground="#ffffff")
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground=INK, rowheight=29, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#f2f5f9", foreground="#475467", padding=(8, 8), font=("Segoe UI Semibold", 9), relief="flat")
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", INK)])
        style.configure("Vertical.TScrollbar", background="#edf1f6", troughcolor="#f8fafc", bordercolor="#f8fafc", arrowcolor="#667085")
        style.configure("Horizontal.TScrollbar", background="#edf1f6", troughcolor="#f8fafc", bordercolor="#f8fafc", arrowcolor="#667085")

    def _build_shell(self) -> None:
        self.root.title("GearDesk | Vehicle Service Management")
        self.root.configure(bg=BG)
        self.root.geometry("1320x820")
        self.root.minsize(1050, 680)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=222)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(18, 22, 18, 16))
        brand.pack(fill="x")
        mark = tk.Label(brand, text="GD", bg="#2864d7", fg="#ffffff", font=("Segoe UI Semibold", 12), width=4, height=2)
        mark.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 11))
        ttk.Label(brand, text="GEARDESK", style="BrandTitle.TLabel").grid(row=0, column=1, sticky="sw")
        ttk.Label(brand, text="SERVICE CENTRE", style="BrandSub.TLabel").grid(row=1, column=1, sticky="nw")
        tk.Frame(sidebar, bg="#30435a", height=1).pack(fill="x", padx=17, pady=(4, 16))
        ttk.Label(sidebar, text="WORKSPACE", style="BrandSub.TLabel").pack(anchor="w", padx=20, pady=(0, 7))
        nav = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(10, 0, 10, 0))
        nav.pack(fill="x")
        for page_key, label, icon in self.NAV_ITEMS:
            button = ttk.Button(
                nav,
                text=f"{icon}    {label}",
                style="Nav.TButton",
                command=lambda key=page_key: self.show_page(key),
            )
            button.pack(fill="x", pady=2)
            self.nav_buttons[page_key] = button
        sidebar_bottom = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=16)
        sidebar_bottom.pack(side="bottom", fill="x")
        ttk.Label(sidebar_bottom, text="Vehicle Service &\nMaintenance System", style="BrandSub.TLabel", justify="left").pack(anchor="w")
        ttk.Label(sidebar_bottom, text="DBMS project • Desktop", style="BrandSub.TLabel").pack(anchor="w", pady=(7, 0))

        self.main = ttk.Frame(self.root, style="App.TFrame")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        header = ttk.Frame(self.main, style="App.TFrame", padding=(24, 21, 24, 13))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.header_title = ttk.Label(header, text="", style="HeaderTitle.TLabel")
        self.header_title.grid(row=0, column=0, sticky="w")
        self.header_subtitle = ttk.Label(header, text="", style="HeaderSub.TLabel")
        self.header_subtitle.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.db_badge = tk.Label(
            header,
            text=self.database.health(),
            bg="#eaf2ff",
            fg="#2857a4",
            padx=10,
            pady=7,
            font=("Segoe UI", 9),
        )
        self.db_badge.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        self.page_host = ttk.Frame(self.main, style="App.TFrame")
        self.page_host.grid(row=1, column=0, sticky="nsew")
        statusbar = tk.Frame(self.main, bg="#e9edf3", height=27)
        statusbar.grid(row=2, column=0, sticky="ew")
        statusbar.grid_propagate(False)
        tk.Label(statusbar, textvariable=self.status_var, bg="#e9edf3", fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(side="left", padx=14, fill="y")
        tk.Label(statusbar, text="Inventory deductions are protected by database triggers", bg="#e9edf3", fg=MUTED, font=("Segoe UI", 8)).pack(side="right", padx=14)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def show_error(self, title: str, error: Exception | str) -> None:
        message = str(error)
        if "Insufficient spare-part stock" in message:
            message = "There is not enough stock for that part. Inventory was not changed."
        elif "FOREIGN KEY constraint failed" in message or "foreign key constraint" in message.lower():
            message = "This record is linked to other data and cannot be deleted. Remove its dependent records first."
        elif "UNIQUE constraint failed" in message or "Duplicate entry" in message:
            message = "That value already exists. Check for a duplicate registration number or service name."
        messagebox.showerror(title, message, parent=self.root)

    def display_cell(self, key: str, value: Any) -> str:
        if value is None:
            return "—"
        if key in {"Unit_Price", "Labour_Cost", "Labour_Amount", "Parts_Amount", "Tax", "Total_Amount", "Cost"}:
            return money(value)
        return str(value)

    def show_page(self, page: str) -> None:
        self.current_page = page
        self.page_object = None
        for key, button in self.nav_buttons.items():
            button.configure(style="NavSelected.TButton" if key == page else "Nav.TButton")
        title, subtitle = self.TITLES[page]
        self.header_title.configure(text=title)
        self.header_subtitle.configure(text=subtitle)
        for child in self.page_host.winfo_children():
            child.destroy()
        try:
            if page == "dashboard":
                self._dashboard_page()
            elif page in {"customers", "vehicles", "mechanics", "services", "parts"}:
                self.page_object = EntityTablePage(self, self.page_host, page)
            elif page == "jobs":
                self._jobs_page()
            elif page == "invoices":
                self._invoices_page()
            elif page == "history":
                self._history_page()
            elif page == "reports":
                self._reports_page()
        except Exception as exc:
            self.show_error("Page could not be opened", exc)

    def entity_config(self, entity: str) -> dict[str, Any]:
        if entity == "customers":
            return {
                "id": "Customer_ID", "singular": "Customer", "name_key": "Name",
                "description": "Customer directory · add and update contact information",
                "columns": [("Customer_ID", "ID", 65, "center"), ("Name", "Customer name", 180, "w"), ("Phone", "Phone", 120, "w"), ("Email", "Email", 190, "w"), ("Address", "Address", 270, "w")],
                "list": self.repo.list_customers, "save": self.repo.save_customer,
                "delete": lambda rid: self.repo.delete_entity("customers", rid),
                "form_title": "Customer details",
                "fields": lambda: [field("Name", "Full name", required=True), field("Phone", "Phone"), field("Email", "Email"), field("Address", "Address", "textarea")],
            }
        if entity == "vehicles":
            customers = self.repo.list_customers()
            options = [(f"{row['Customer_ID']} · {row['Name']}", int(row["Customer_ID"])) for row in customers]
            return {
                "id": "Vehicle_ID", "singular": "Vehicle", "name_key": "Registration_No",
                "description": "Vehicle register · every vehicle is linked to a customer",
                "columns": [("Vehicle_ID", "ID", 60, "center"), ("Registration_No", "Registration", 135, "w"), ("Brand", "Brand", 120, "w"), ("Model", "Model", 125, "w"), ("Manufacturing_Year", "Year", 72, "center"), ("Vehicle_Type", "Type", 100, "w"), ("Customer_Name", "Owner", 175, "w")],
                "list": self.repo.list_vehicles, "save": self.repo.save_vehicle,
                "delete": lambda rid: self.repo.delete_entity("vehicles", rid),
                "form_title": "Vehicle details",
                "fields": lambda: [field("Customer_ID", "Customer / owner", "combo", required=True, options=options), field("Registration_No", "Registration number", required=True), field("Brand", "Manufacturer"), field("Model", "Model"), field("Manufacturing_Year", "Manufacturing year", "integer"), field("Vehicle_Type", "Vehicle type", "combo", required=True, default="Car", options=[("Car", "Car"), ("Motorcycle", "Motorcycle"), ("Scooter", "Scooter"), ("Commercial", "Commercial"), ("Other", "Other")])],
            }
        if entity == "mechanics":
            return {
                "id": "Mechanic_ID", "singular": "Mechanic", "name_key": "Name",
                "description": "Workshop team · specializations are shown when assigning jobs",
                "columns": [("Mechanic_ID", "ID", 60, "center"), ("Name", "Mechanic", 175, "w"), ("Phone", "Phone", 125, "w"), ("Specialization", "Specialization", 235, "w"), ("Experience", "Experience (years)", 135, "center")],
                "list": self.repo.list_mechanics, "save": self.repo.save_mechanic,
                "delete": lambda rid: self.repo.delete_entity("mechanics", rid),
                "form_title": "Mechanic details",
                "fields": lambda: [field("Name", "Full name", required=True), field("Phone", "Phone"), field("Specialization", "Specialization"), field("Experience", "Experience (years)", "integer", required=True, default=0)],
            }
        if entity == "services":
            return {
                "id": "Service_ID", "singular": "Service", "name_key": "Service_Name",
                "description": "Standard jobs and labour pricing used by bookings and invoices",
                "columns": [("Service_ID", "ID", 60, "center"), ("Service_Name", "Service", 190, "w"), ("Labour_Cost", "Labour cost", 120, "e"), ("Estimated_Time", "Estimated time", 130, "w"), ("Description", "Description", 360, "w")],
                "list": self.repo.list_services, "save": self.repo.save_service,
                "delete": lambda rid: self.repo.delete_entity("services", rid),
                "form_title": "Service catalogue item",
                "fields": lambda: [field("Service_Name", "Service name", required=True), field("Description", "Description", "textarea"), field("Labour_Cost", "Labour cost (₹)", "decimal", required=True, default=0), field("Estimated_Time", "Estimated time", default="1 hour")],
            }
        if entity == "parts":
            return {
                "id": "Part_ID", "singular": "Spare part", "name_key": "Part_Name",
                "description": "Rows highlighted in amber are at or below their reorder level",
                "columns": [("Part_ID", "ID", 60, "center"), ("Part_Name", "Part", 205, "w"), ("Category", "Category", 120, "w"), ("Unit_Price", "Unit price", 120, "e"), ("Quantity_Available", "Available", 100, "center"), ("Reorder_Level", "Reorder at", 100, "center")],
                "list": self.repo.list_parts, "save": self.repo.save_part,
                "delete": lambda rid: self.repo.delete_entity("parts", rid),
                "form_title": "Spare part details",
                "fields": lambda: [field("Part_Name", "Part name", required=True), field("Category", "Category"), field("Unit_Price", "Unit price (₹)", "decimal", required=True, default=0), field("Quantity_Available", "Opening / available stock", "integer", required=True, default=0), field("Reorder_Level", "Reorder level", "integer", required=True, default=5)],
            }
        raise ValueError(f"No configuration for {entity}.")

    def _section_header(self, parent: ttk.Frame, title: str, hint: str = "") -> ttk.Frame:
        header = ttk.Frame(parent, style="Card.TFrame", padding=(15, 13, 15, 10))
        ttk.Label(header, text=title, style="SectionTitle.TLabel").pack(anchor="w")
        if hint:
            ttk.Label(header, text=hint, style="SectionHint.TLabel").pack(anchor="w", pady=(3, 0))
        return header

    def _dashboard_page(self) -> None:
        page = ttk.Frame(self.page_host, style="App.TFrame", padding=(20, 2, 20, 18))
        page.pack(fill="both", expand=True)
        summary = self.repo.dashboard_summary()
        cards = [
            ("CUSTOMERS", str(summary["Customers"]), "registered owners", "#246bfd"),
            ("VEHICLES", str(summary["Vehicles"]), "in the workshop database", "#7a5af8"),
            ("ACTIVE JOBS", str(summary["Active_Jobs"]), "booked or in progress", "#c47b16"),
            ("LOW-STOCK PARTS", str(summary["Low_Stock"]), "at / below reorder level", "#d04437"),
            ("PAID REVENUE", money(summary["Paid_Revenue"]), "invoices marked paid", "#16835d"),
        ]
        cards_row = ttk.Frame(page, style="App.TFrame")
        cards_row.pack(fill="x", pady=(0, 14))
        for index, (label, value, sub, accent) in enumerate(cards):
            cards_row.columnconfigure(index, weight=1, uniform="cards")
            card = tk.Frame(cards_row, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 0 if index == len(cards) - 1 else 7))
            tk.Frame(card, bg=accent, height=3).pack(fill="x")
            inner = tk.Frame(card, bg=SURFACE, padx=13, pady=12)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x")
            tk.Label(inner, text=value, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 19), anchor="w").pack(fill="x", pady=(7, 3))
            tk.Label(inner, text=sub, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        quick = ttk.Frame(page, style="App.TFrame")
        quick.pack(fill="x", pady=(0, 14))
        ttk.Label(quick, text="Quick actions", style="SectionTitle.TLabel").pack(side="left", padx=(2, 10))
        ttk.Button(quick, text="＋ New service booking", style="Primary.TButton", command=self._quick_new_job).pack(side="left", padx=(0, 7))
        ttk.Button(quick, text="＋ Add customer", style="Secondary.TButton", command=lambda: self._quick_add_entity("customers")).pack(side="left", padx=(0, 7))
        ttk.Button(quick, text="＋ Receive stock", style="Secondary.TButton", command=lambda: self._quick_add_entity("parts")).pack(side="left")
        ttk.Button(quick, text="View reports  →", style="Secondary.TButton", command=lambda: self.show_page("reports")).pack(side="right")

        content = ttk.Frame(page, style="App.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3, uniform="dashboard")
        content.columnconfigure(1, weight=2, uniform="dashboard")
        content.rowconfigure(0, weight=1)
        recent_panel = ttk.Frame(content, style="Card.TFrame", padding=12)
        recent_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        heading = ttk.Frame(recent_panel, style="Card.TFrame")
        heading.pack(fill="x", pady=(0, 9))
        ttk.Label(heading, text="Recent service jobs", style="SectionTitle.TLabel").pack(side="left")
        ttk.Button(heading, text="View all  →", style="Secondary.TButton", command=lambda: self.show_page("jobs")).pack(side="right")
        recent_columns = [("Service_Record_ID", "Job", 60, "center"), ("Service_Date", "Date", 100, "center"), ("Registration_No", "Registration", 125, "w"), ("Customer_Name", "Customer", 150, "w"), ("Service_Name", "Service", 160, "w"), ("Service_Status", "Status", 105, "center")]
        self.dashboard_jobs_tree, _ = self._make_tree(recent_panel, recent_columns, height=11)
        for row in self.repo.recent_jobs():
            values = [self.display_cell(key, row.get(key)) for key, *_ in recent_columns]
            tag = self._status_tag(row.get("Service_Status"))
            self.dashboard_jobs_tree.insert("", "end", iid=f"recent-{row['Service_Record_ID']}", values=values, tags=(tag,))

        stock_panel = ttk.Frame(content, style="Card.TFrame", padding=12)
        stock_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        heading2 = ttk.Frame(stock_panel, style="Card.TFrame")
        heading2.pack(fill="x", pady=(0, 9))
        ttk.Label(heading2, text="Reorder watch", style="SectionTitle.TLabel").pack(side="left")
        ttk.Button(heading2, text="Inventory  →", style="Secondary.TButton", command=lambda: self.show_page("parts")).pack(side="right")
        low_stock = self.repo.list_low_stock()
        stock_cols = [("Part_Name", "Part name", 180, "w"), ("Quantity_Available", "Available", 82, "center"), ("Reorder_Level", "Reorder at", 82, "center")]
        stock_tree, _ = self._make_tree(stock_panel, stock_cols, height=9)
        stock_tree.tag_configure("low_stock", background="#fff5e8", foreground=AMBER)
        if low_stock:
            for row in low_stock:
                stock_tree.insert("", "end", iid=f"stock-{row['Part_ID']}", values=[row.get(key, "") for key, *_ in stock_cols], tags=("low_stock",))
        else:
            ttk.Label(stock_panel, text="All parts are above their reorder level.", style="SectionHint.TLabel").pack(anchor="w", pady=(10, 0))
        ttk.Label(stock_panel, text="Stock levels are updated automatically when a part is assigned to a job.", style="SectionHint.TLabel", wraplength=330).pack(anchor="w", pady=(9, 0))

    def _quick_add_entity(self, entity: str) -> None:
        config = self.entity_config(entity)
        dlg = FormDialog(self.root, config["form_title"], config["fields"]())
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            config["save"](dlg.result)
            self.set_status(f"{config['singular']} saved.")
            self.show_page("dashboard")
        except Exception as exc:
            self.show_error("Could not save record", exc)

    def _quick_new_job(self) -> None:
        self.show_page("jobs")
        self._open_job_form(None)

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: list[tuple[str, str, int, str]],
        height: int = 13,
    ) -> tuple[ttk.Treeview, ttk.Frame]:
        box = ttk.Frame(parent, style="Card.TFrame")
        box.pack(fill="both", expand=True)
        tree = ttk.Treeview(box, columns=[item[0] for item in columns], show="headings", selectmode="browse", height=height)
        for key, title, width, anchor in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=55, anchor=anchor, stretch=True)
        tree.tag_configure("status_booked", foreground="#8a5b00", background="#fff8e8")
        tree.tag_configure("status_progress", foreground="#175cd3", background="#eff8ff")
        tree.tag_configure("status_completed", foreground=GREEN, background="#ecfdf3")
        tree.tag_configure("status_cancelled", foreground=MUTED, background="#f3f4f6")
        yscroll = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        return tree, box

    @staticmethod
    def _status_tag(status: Any) -> str:
        return {
            "Booked": "status_booked",
            "In Progress": "status_progress",
            "Completed": "status_completed",
            "Cancelled": "status_cancelled",
        }.get(str(status), "")

    def _jobs_page(self) -> None:
        page = ttk.Frame(self.page_host, style="Page.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        toolbar = ttk.Frame(page, style="Page.TFrame")
        toolbar.pack(fill="x", pady=(0, 10))
        self.job_search_var = tk.StringVar()
        self.job_status_var = tk.StringVar(value="All")
        search = ttk.Entry(toolbar, textvariable=self.job_search_var, width=30)
        search.pack(side="left", padx=(0, 7))
        search.bind("<Return>", lambda _event: self._refresh_jobs())
        ttk.Combobox(toolbar, textvariable=self.job_status_var, state="readonly", width=15, values=["All", "Booked", "In Progress", "Completed", "Cancelled"]).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="Filter", style="Secondary.TButton", command=self._refresh_jobs).pack(side="left")
        ttk.Button(toolbar, text="Export CSV", style="Secondary.TButton", command=self._export_jobs).pack(side="left", padx=(7, 0))
        ttk.Button(toolbar, text="＋ New booking", style="Primary.TButton", command=lambda: self._open_job_form(None)).pack(side="right")

        actions = ttk.Frame(page, style="Page.TFrame")
        actions.pack(fill="x", pady=(0, 10))
        ttk.Label(actions, text="Select a job to manage its progress and parts.", style="Muted.TLabel").pack(side="left")
        ttk.Button(actions, text="Generate invoice", style="Secondary.TButton", command=self._generate_invoice).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="Parts used", style="Secondary.TButton", command=self._open_parts_used).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="Update status", style="Secondary.TButton", command=self._update_job_status).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="Edit booking", style="Secondary.TButton", command=self._edit_job).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="Delete", style="Danger.TButton", command=self._delete_job).pack(side="right")
        columns = [("Service_Record_ID", "Job", 58, "center"), ("Service_Date", "Service date", 105, "center"), ("Registration_No", "Vehicle", 122, "w"), ("Customer_Name", "Customer", 150, "w"), ("Service_Name", "Service", 150, "w"), ("Mechanic_Name", "Mechanic", 128, "w"), ("Parts_Count", "Parts", 60, "center"), ("Total_Amount", "Invoice total", 112, "e"), ("Service_Status", "Status", 110, "center")]
        self.jobs_tree, _ = self._make_tree(page, columns, height=15)
        self.jobs_columns = columns
        self.job_rows: dict[int, dict[str, Any]] = {}
        self.jobs_tree.bind("<Double-1>", lambda _event: self._edit_job())
        self._refresh_jobs()

    def _refresh_jobs(self) -> None:
        try:
            rows = self.repo.list_jobs(self.job_search_var.get(), self.job_status_var.get())
            self.job_rows = {int(row["Service_Record_ID"]): row for row in rows}
            for item in self.jobs_tree.get_children():
                self.jobs_tree.delete(item)
            for row in rows:
                values = [self.display_cell(key, row.get(key)) for key, *_ in self.jobs_columns]
                self.jobs_tree.insert("", "end", iid=str(row["Service_Record_ID"]), values=values, tags=(self._status_tag(row.get("Service_Status")),))
            self.set_status(f"Showing {len(rows)} service job{'s' if len(rows) != 1 else ''}.")
        except Exception as exc:
            self.show_error("Could not load service jobs", exc)

    def _selected_job(self) -> dict[str, Any] | None:
        selection = self.jobs_tree.selection()
        if not selection:
            messagebox.showinfo("Select a service job", "Select a service job row first.", parent=self.root)
            return None
        try:
            return self.job_rows.get(int(selection[0]))
        except ValueError:
            return None

    def _job_form_fields(self) -> list[dict[str, Any]]:
        vehicles = self.repo.list_vehicles()
        mechanics = self.repo.list_mechanics()
        services = self.repo.list_services()
        if not vehicles:
            raise ValueError("Add a customer and vehicle before creating a service booking.")
        if not mechanics:
            raise ValueError("Add at least one mechanic before creating a service booking.")
        if not services:
            raise ValueError("Add at least one service catalogue item before creating a booking.")
        return [
            field("Vehicle_ID", "Vehicle", "combo", required=True, options=[(f"{r['Registration_No']} · {r.get('Brand') or ''} {r.get('Model') or ''} — {r['Customer_Name']}", int(r["Vehicle_ID"])) for r in vehicles]),
            field("Mechanic_ID", "Assigned mechanic", "combo", required=True, options=[(f"{r['Name']} · {r.get('Specialization') or 'General'}", int(r["Mechanic_ID"])) for r in mechanics]),
            field("Service_ID", "Service type", "combo", required=True, options=[(f"{r['Service_Name']} · {money(r['Labour_Cost'])}", int(r["Service_ID"])) for r in services]),
            field("Service_Date", "Service date (YYYY-MM-DD)", "date", required=True, default=date.today().isoformat()),
            field("Problem_Description", "Reported problem", "textarea"),
            field("Service_Status", "Status", "combo", required=True, default="Booked", options=[(value, value) for value in ["Booked", "In Progress", "Completed", "Cancelled"]]),
            field("Remarks", "Technician / service remarks", "textarea"),
        ]

    def _open_job_form(self, record: dict[str, Any] | None) -> None:
        try:
            fields = self._job_form_fields()
        except Exception as exc:
            self.show_error("Booking prerequisites missing", exc)
            return
        title = "Edit service booking" if record else "New service booking"
        dlg = FormDialog(self.root, title, fields, initial=record)
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.repo.save_job(dlg.result, int(record["Service_Record_ID"]) if record else None)
            self._refresh_jobs()
            self.set_status("Service booking saved.")
        except Exception as exc:
            self.show_error("Could not save service booking", exc)

    def _edit_job(self) -> None:
        row = self._selected_job()
        if row:
            raw = self.repo.get_job(int(row["Service_Record_ID"]))
            if raw:
                self._open_job_form(raw)

    def _update_job_status(self) -> None:
        row = self._selected_job()
        if not row:
            return
        dlg = FormDialog(
            self.root,
            f"Update status · Job #{row['Service_Record_ID']}",
            [field("Service_Status", "Service status", "combo", required=True, default=row["Service_Status"], options=[(value, value) for value in ["Booked", "In Progress", "Completed", "Cancelled"]])],
        )
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.repo.save_job({"Service_Status": dlg.result["Service_Status"]}, int(row["Service_Record_ID"]))
            self._refresh_jobs()
            self.set_status(f"Job #{row['Service_Record_ID']} status updated.")
        except Exception as exc:
            self.show_error("Could not update job status", exc)

    def _delete_job(self) -> None:
        row = self._selected_job()
        if not row:
            return
        if not messagebox.askyesno("Delete service booking?", f"Delete job #{row['Service_Record_ID']}? Jobs with used parts or an invoice are protected by foreign keys.", parent=self.root):
            return
        try:
            self.repo.delete_entity("jobs", int(row["Service_Record_ID"]))
            self._refresh_jobs()
        except Exception as exc:
            self.show_error("Could not delete service booking", exc)

    def _open_parts_used(self) -> None:
        row = self._selected_job()
        if row:
            PartsUsedDialog(self, int(row["Service_Record_ID"]), row)
            self._refresh_jobs()

    def _generate_invoice(self) -> None:
        selection = self.jobs_tree.selection()
        row = self.job_rows.get(int(selection[0])) if selection else None
        self._show_invoice_generator(int(row["Service_Record_ID"]) if row else None)

    def _export_jobs(self) -> None:
        if not self.job_rows:
            messagebox.showinfo("Nothing to export", "There are no jobs in this view.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Export service jobs", defaultextension=".csv", filetypes=[("CSV file", "*.csv")], initialfile="service_jobs.csv")
        if not path:
            return
        try:
            keys = [column[0] for column in self.jobs_columns]
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.job_rows.values())
            messagebox.showinfo("Export complete", f"Saved {len(self.job_rows)} jobs to:\n{path}", parent=self.root)
        except Exception as exc:
            self.show_error("CSV export failed", exc)

    def _invoices_page(self) -> None:
        page = ttk.Frame(self.page_host, style="Page.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        toolbar = ttk.Frame(page, style="Page.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        self.invoice_search_var = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.invoice_search_var, width=32)
        search.pack(side="left", padx=(0, 7))
        search.bind("<Return>", lambda _event: self._refresh_invoices())
        ttk.Button(toolbar, text="Search", style="Secondary.TButton", command=self._refresh_invoices).pack(side="left")
        ttk.Button(toolbar, text="＋ Generate invoice", style="Primary.TButton", command=lambda: self._show_invoice_generator(None)).pack(side="right")
        actions = ttk.Frame(page, style="Page.TFrame")
        actions.pack(fill="x", pady=(0, 10))
        ttk.Label(actions, text="Tax is entered as a percentage when the invoice is calculated; payment status can be tracked separately.", style="Muted.TLabel").pack(side="left")
        ttk.Button(actions, text="View / export", style="Secondary.TButton", command=self._view_invoice).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="Update payment", style="Secondary.TButton", command=self._update_invoice_payment).pack(side="right")
        columns = [("Invoice_ID", "Invoice", 72, "center"), ("Invoice_Date", "Date", 100, "center"), ("Registration_No", "Vehicle", 120, "w"), ("Customer_Name", "Customer", 145, "w"), ("Service_Name", "Service", 140, "w"), ("Labour_Amount", "Labour", 105, "e"), ("Parts_Amount", "Parts", 105, "e"), ("Tax", "Tax", 95, "e"), ("Total_Amount", "Total", 115, "e"), ("Payment_Status", "Payment", 100, "center")]
        self.invoice_columns = columns
        self.invoice_tree, _ = self._make_tree(page, columns, height=16)
        self.invoice_rows: dict[int, dict[str, Any]] = {}
        self.invoice_tree.bind("<Double-1>", lambda _event: self._view_invoice())
        self._refresh_invoices()

    def _refresh_invoices(self) -> None:
        try:
            rows = self.repo.list_invoices(self.invoice_search_var.get())
            self.invoice_rows = {int(row["Invoice_ID"]): row for row in rows}
            for item in self.invoice_tree.get_children():
                self.invoice_tree.delete(item)
            for row in rows:
                values = [self.display_cell(key, row.get(key)) for key, *_ in self.invoice_columns]
                self.invoice_tree.insert("", "end", iid=str(row["Invoice_ID"]), values=values)
        except Exception as exc:
            self.show_error("Could not load invoices", exc)

    def _selected_invoice(self) -> dict[str, Any] | None:
        selection = self.invoice_tree.selection()
        if not selection:
            messagebox.showinfo("Select an invoice", "Select an invoice row first.", parent=self.root)
            return None
        return self.invoice_rows.get(int(selection[0]))

    def _show_invoice_generator(self, default_record_id: int | None) -> None:
        jobs = self.repo.list_jobs()
        if not jobs:
            messagebox.showinfo("No service jobs", "Create a service booking before generating an invoice.", parent=self.root)
            return
        options = [
            (f"Job #{row['Service_Record_ID']} · {row['Registration_No']} · {row['Customer_Name']} · {row['Service_Name']} · {row['Service_Status']}", int(row["Service_Record_ID"]))
            for row in jobs
        ]
        fields = [
            field("Service_Record_ID", "Service job", "combo", required=True, options=options),
            field("Tax_Percent", "Tax percentage", "decimal", required=True, default=18, help_text="Example: 18 adds 18% tax to labour plus parts."),
        ]
        dlg = FormDialog(self.root, "Generate / recalculate invoice", fields, initial={"Service_Record_ID": default_record_id} if default_record_id else None)
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        record_id = int(dlg.result["Service_Record_ID"])
        existing = self.database.one("SELECT `Invoice_ID` FROM `INVOICE` WHERE `Service_Record_ID` = ?", (record_id,))
        if existing and not messagebox.askyesno("Recalculate invoice?", "An invoice already exists for this service. Recalculation will refresh its amounts and date but will keep its payment status.", parent=self.root):
            return
        try:
            invoice_id = self.repo.create_or_refresh_invoice(record_id, dlg.result["Tax_Percent"])
            if self.current_page == "invoices":
                self._refresh_invoices()
            if self.current_page == "jobs":
                self._refresh_jobs()
            self.set_status(f"Invoice #{invoice_id} generated.")
            messagebox.showinfo("Invoice ready", f"Invoice #{invoice_id} has been calculated.", parent=self.root)
        except Exception as exc:
            self.show_error("Could not generate invoice", exc)

    def _update_invoice_payment(self) -> None:
        row = self._selected_invoice()
        if not row:
            return
        statuses = [(status, status) for status in ["Unpaid", "Partial", "Paid"]]
        dlg = FormDialog(self.root, f"Payment status · Invoice #{row['Invoice_ID']}", [field("Payment_Status", "Payment status", "combo", required=True, default=row["Payment_Status"], options=statuses)])
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.repo.set_invoice_payment_status(int(row["Invoice_ID"]), dlg.result["Payment_Status"])
            self._refresh_invoices()
            self.set_status(f"Invoice #{row['Invoice_ID']} payment status updated.")
        except Exception as exc:
            self.show_error("Could not update payment status", exc)

    def _view_invoice(self) -> None:
        row = self._selected_invoice()
        if row:
            details = self.repo.get_invoice_details(int(row["Invoice_ID"]))
            if details:
                InvoicePreviewDialog(self, details)

    def _reports_page(self) -> None:
        page = ttk.Frame(self.page_host, style="App.TFrame", padding=(20, 2, 20, 18))
        page.pack(fill="both", expand=True)
        summary = self.repo.billing_analytics()
        cards = [
            ("INVOICES", str(summary.get("Invoice_Count", 0)), "generated to date", "#246bfd"),
            ("TOTAL BILLED", money(summary.get("Total_Billed", 0)), "all invoices", "#7a5af8"),
            ("AVERAGE INVOICE", money(summary.get("Average_Invoice", 0)), "AVG(Total_Amount)", "#16835d"),
            ("LARGEST INVOICE", money(summary.get("Largest_Invoice", 0)), "MAX(Total_Amount)", "#c47b16"),
            ("SMALLEST INVOICE", money(summary.get("Smallest_Invoice", 0)), "MIN(Total_Amount)", "#d04437"),
        ]
        cards_row = ttk.Frame(page, style="App.TFrame")
        cards_row.pack(fill="x", pady=(0, 14))
        for index, (label, value, sub, accent) in enumerate(cards):
            cards_row.columnconfigure(index, weight=1, uniform="report_cards")
            card = tk.Frame(cards_row, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 0 if index == len(cards) - 1 else 7))
            tk.Frame(card, bg=accent, height=3).pack(fill="x")
            inner = tk.Frame(card, bg=SURFACE, padx=13, pady=11)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x")
            tk.Label(inner, text=value, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 17), anchor="w").pack(fill="x", pady=(6, 2))
            tk.Label(inner, text=sub, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        content = ttk.Frame(page, style="App.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3, uniform="report_panels")
        content.columnconfigure(1, weight=2, uniform="report_panels")
        content.rowconfigure(0, weight=1)
        service_panel = ttk.Frame(content, style="Card.TFrame", padding=12)
        service_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        ttk.Label(service_panel, text="Service performance", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(service_panel, text="Job counts, catalogue labour averages and invoiced totals by service.", style="SectionHint.TLabel").pack(anchor="w", pady=(3, 9))
        service_cols = [("Service_Name", "Service", 165, "w"), ("Jobs_Count", "Jobs", 60, "center"), ("Average_Labour", "Avg labour", 105, "e"), ("Invoiced_Amount", "Invoiced", 110, "e")]
        service_tree, _ = self._make_tree(service_panel, service_cols, height=13)
        for row in self.repo.service_analytics():
            values = [self.display_cell(key, row.get(key)) for key, *_ in service_cols]
            service_tree.insert("", "end", iid=f"report-service-{row['Service_ID']}", values=values)

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1, uniform="report_right")
        right.rowconfigure(1, weight=1, uniform="report_right")
        status_panel = ttk.Frame(right, style="Card.TFrame", padding=12)
        status_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 7))
        ttk.Label(status_panel, text="Job status mix", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(status_panel, text="COUNT(*) grouped by current service status.", style="SectionHint.TLabel").pack(anchor="w", pady=(3, 7))
        status_cols = [("Service_Status", "Status", 150, "w"), ("Jobs_Count", "Jobs", 70, "center")]
        status_tree, _ = self._make_tree(status_panel, status_cols, height=5)
        for index, row in enumerate(self.repo.job_status_analytics()):
            status_tree.insert("", "end", iid=f"report-status-{index}", values=(row["Service_Status"], row["Jobs_Count"]), tags=(self._status_tag(row["Service_Status"]),))

        parts_panel = ttk.Frame(right, style="Card.TFrame", padding=12)
        parts_panel.grid(row=1, column=0, sticky="nsew", pady=(7, 0))
        ttk.Label(parts_panel, text="Most-used spare parts", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(parts_panel, text="SUM(Quantity_Used) and SUM(Cost) from recorded usage.", style="SectionHint.TLabel").pack(anchor="w", pady=(3, 7))
        part_cols = [("Part_Name", "Part", 170, "w"), ("Quantity_Used", "Used", 65, "center"), ("Total_Cost", "Cost", 100, "e")]
        part_tree, _ = self._make_tree(parts_panel, part_cols, height=5)
        for index, row in enumerate(self.repo.part_usage_analytics()):
            values = [self.display_cell(key, row.get(key)) for key, *_ in part_cols]
            part_tree.insert("", "end", iid=f"report-part-{index}", values=values)
        ttk.Label(page, text=f"Paid revenue: {money(summary.get('Paid_Revenue', 0))}  ·  All values are calculated from the active database.", style="Muted.TLabel").pack(anchor="w", pady=(9, 0))

    def _history_page(self) -> None:
        page = ttk.Frame(self.page_host, style="Page.TFrame", padding=18)
        page.pack(fill="both", expand=True)
        toolbar = ttk.Frame(page, style="Page.TFrame")
        toolbar.pack(fill="x", pady=(0, 11))
        self.history_search_var = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.history_search_var, width=42)
        search.pack(side="left", padx=(0, 7))
        search.bind("<Return>", lambda _event: self._refresh_history())
        ttk.Button(toolbar, text="Search history", style="Primary.TButton", command=self._refresh_history).pack(side="left")
        ttk.Label(toolbar, text="Search by registration, customer, service, problem or job number.", style="Muted.TLabel").pack(side="left", padx=12)
        split = ttk.Panedwindow(page, orient="vertical")
        split.pack(fill="both", expand=True)
        history_top = ttk.Frame(split, style="Card.TFrame", padding=7)
        history_bottom = ttk.Frame(split, style="Card.TFrame", padding=11)
        split.add(history_top, weight=3)
        split.add(history_bottom, weight=1)
        columns = [("Service_Record_ID", "Job", 62, "center"), ("Service_Date", "Date", 95, "center"), ("Registration_No", "Vehicle", 120, "w"), ("Customer_Name", "Customer", 145, "w"), ("Service_Name", "Service", 145, "w"), ("Mechanic_Name", "Mechanic", 125, "w"), ("Service_Status", "Status", 100, "center"), ("Parts_Count", "Parts", 60, "center"), ("Total_Amount", "Invoice total", 115, "e")]
        self.history_columns = columns
        self.history_tree, _ = self._make_tree(history_top, columns, height=10)
        self.history_tree.bind("<<TreeviewSelect>>", self._show_history_details)
        self.history_rows: dict[int, dict[str, Any]] = {}
        ttk.Label(history_bottom, text="Selected service detail", style="SectionTitle.TLabel").pack(anchor="w", pady=(0, 5))
        self.history_detail = tk.Text(history_bottom, height=6, wrap="word", relief="flat", bg="#ffffff", fg=INK, font=("Segoe UI", 9), padx=9, pady=7)
        self.history_detail.pack(fill="both", expand=True)
        self.history_detail.insert("1.0", "Select a service record to see the problem, mechanic, parts used and invoice status.")
        self.history_detail.configure(state="disabled")
        self._refresh_history()

    def _refresh_history(self) -> None:
        try:
            rows = self.repo.search_history(self.history_search_var.get())
            self.history_rows = {int(row["Service_Record_ID"]): row for row in rows}
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            for row in rows:
                values = [self.display_cell(key, row.get(key)) for key, *_ in self.history_columns]
                self.history_tree.insert("", "end", iid=str(row["Service_Record_ID"]), values=values, tags=(self._status_tag(row.get("Service_Status")),))
            self.set_status(f"{len(rows)} matching service history record{'s' if len(rows) != 1 else ''}.")
        except Exception as exc:
            self.show_error("Could not search service history", exc)

    def _show_history_details(self, _event: tk.Event | None = None) -> None:
        selection = self.history_tree.selection()
        if not selection:
            return
        try:
            details = self.repo.get_history_details(int(selection[0]))
        except Exception as exc:
            self.show_error("Could not load history detail", exc)
            return
        if not details:
            return
        lines = [
            f"Job #{details['Service_Record_ID']}  ·  {details['Registration_No']}  ·  {details.get('Brand') or ''} {details.get('Model') or ''}",
            f"Customer: {details['Customer_Name']}  |  Mechanic: {details['Mechanic_Name']}  |  Service: {details['Service_Name']}",
            f"Status: {details['Service_Status']}  |  Reported issue: {details.get('Problem_Description') or '—'}",
            f"Remarks: {details.get('Remarks') or '—'}",
        ]
        parts = details.get("parts", [])
        if parts:
            lines.append("Parts used: " + "; ".join(f"{part['Part_Name']} × {part['Quantity_Used']} ({money(part['Cost'])})" for part in parts))
        else:
            lines.append("Parts used: none")
        invoice_id = details.get("Invoice_ID")
        if invoice_id and int(invoice_id) != 0:
            lines.append(f"Invoice: {money(details.get('Total_Amount'))}  |  Payment: {details.get('Payment_Status') or 'Unpaid'}")
        else:
            lines.append("Invoice: not generated")
        self.history_detail.configure(state="normal")
        self.history_detail.delete("1.0", "end")
        self.history_detail.insert("1.0", "\n".join(lines))
        self.history_detail.configure(state="disabled")


class PartsUsedDialog(tk.Toplevel):
    def __init__(self, app: ServiceApp, service_record_id: int, job: dict[str, Any]):
        super().__init__(app.root)
        self.app = app
        self.service_record_id = service_record_id
        self.job = job
        self.title(f"Parts used · Job #{service_record_id}")
        self.configure(bg=BG)
        self.geometry("690x510")
        self.minsize(600, 420)
        self.transient(app.root)
        self.grab_set()
        outer = ttk.Frame(self, style="Page.TFrame", padding=17)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Parts used on job #{service_record_id}", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"{job.get('Registration_No', '')} · {job.get('Customer_Name', '')} · {job.get('Service_Name', '')}", style="DialogHint.TLabel").pack(anchor="w", pady=(3, 10))
        columns = [("Service_Part_ID", "Line", 55, "center"), ("Part_Name", "Spare part", 230, "w"), ("Quantity_Used", "Qty", 70, "center"), ("Unit_Price", "Unit price", 110, "e"), ("Cost", "Line total", 115, "e")]
        self.tree, _ = app._make_tree(outer, columns, height=9)
        ttk.Label(outer, text="Add part to this service", style="SectionTitle.TLabel").pack(anchor="w", pady=(12, 7))
        controls = ttk.Frame(outer, style="Page.TFrame")
        controls.pack(fill="x")
        self.parts = [row for row in app.repo.list_parts() if int(row.get("Quantity_Available") or 0) > 0]
        self.options = {f"{r['Part_Name']} · {int(r['Quantity_Available'])} available · {money(r['Unit_Price'])}": int(r["Part_ID"]) for r in self.parts}
        self.part_var = tk.StringVar(value=next(iter(self.options), ""))
        self.part_combo = ttk.Combobox(controls, textvariable=self.part_var, state="readonly", values=list(self.options), width=47)
        self.part_combo.pack(side="left", padx=(0, 7))
        ttk.Label(controls, text="Qty").pack(side="left", padx=(0, 4))
        self.quantity_var = tk.StringVar(value="1")
        ttk.Spinbox(controls, from_=1, to=9999, textvariable=self.quantity_var, width=6).pack(side="left", padx=(0, 7))
        ttk.Button(controls, text="Add part", style="Primary.TButton", command=self._add).pack(side="left")
        ttk.Button(controls, text="Remove selected", style="Danger.TButton", command=self._remove).pack(side="right")
        ttk.Label(outer, text="The inventory trigger deducts stock on add and returns it if a line is removed.", style="DialogHint.TLabel").pack(anchor="w", pady=(9, 0))
        self._refresh()

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.app.repo.list_service_parts(self.service_record_id):
            self.tree.insert(
                "", "end", iid=str(row["Service_Part_ID"]),
                values=(row["Service_Part_ID"], row["Part_Name"], row["Quantity_Used"], money(row["Unit_Price"]), money(row["Cost"])),
            )
        self.parts = [row for row in self.app.repo.list_parts() if int(row.get("Quantity_Available") or 0) > 0]
        self.options = {f"{r['Part_Name']} · {int(r['Quantity_Available'])} available · {money(r['Unit_Price'])}": int(r["Part_ID"]) for r in self.parts}
        current = self.part_var.get()
        self.part_combo.configure(values=list(self.options))
        if current not in self.options:
            self.part_var.set(next(iter(self.options), ""))

    def _add(self) -> None:
        try:
            label = self.part_var.get()
            if not label or label not in self.options:
                raise ValueError("Select an in-stock spare part first.")
            quantity = int(self.quantity_var.get())
            self.app.repo.add_service_part(self.service_record_id, self.options[label], quantity)
            self.quantity_var.set("1")
            self._refresh()
            self.app.set_status("Spare-part usage recorded; stock updated by trigger.")
        except Exception as exc:
            self.app.show_error("Could not add spare part", exc)

    def _remove(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a part line", "Select the part line to remove.", parent=self)
            return
        if not messagebox.askyesno("Remove part line?", "Remove this usage line and return its quantity to stock?", parent=self):
            return
        try:
            self.app.repo.remove_service_part(int(selection[0]))
            self._refresh()
            self.app.set_status("Part line removed; inventory restored by trigger.")
        except Exception as exc:
            self.app.show_error("Could not remove spare part", exc)


class InvoicePreviewDialog(tk.Toplevel):
    def __init__(self, app: ServiceApp, invoice: dict[str, Any]):
        super().__init__(app.root)
        self.app = app
        self.invoice = invoice
        self.title(f"Invoice #{invoice['Invoice_ID']}")
        self.configure(bg=BG)
        self.geometry("600x650")
        self.minsize(500, 500)
        self.transient(app.root)
        outer = ttk.Frame(self, style="Page.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Invoice #{invoice['Invoice_ID']}", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Created {invoice['Invoice_Date']} · {invoice['Payment_Status']}", style="DialogHint.TLabel").pack(anchor="w", pady=(3, 10))
        self.text = tk.Text(outer, wrap="word", bg="#ffffff", fg=INK, relief="solid", borderwidth=1, padx=18, pady=16, font=("Segoe UI", 10))
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", self._invoice_text())
        self.text.configure(state="disabled")
        buttons = ttk.Frame(outer, style="Page.TFrame")
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save print-ready HTML", style="Primary.TButton", command=self._save_html).pack(side="right")
        ttk.Button(buttons, text="Close", style="Secondary.TButton", command=self.destroy).pack(side="right", padx=(0, 7))

    def _invoice_text(self) -> str:
        inv = self.invoice
        lines = [
            "GEARDESK  |  VEHICLE SERVICE CENTRE",
            "SERVICE & MAINTENANCE INVOICE",
            "=" * 44,
            f"Invoice no.:  {inv['Invoice_ID']}",
            f"Invoice date: {inv['Invoice_Date']}",
            f"Payment:      {inv['Payment_Status']}",
            "",
            f"Customer:     {inv['Customer_Name']}",
            f"Phone:        {inv.get('Customer_Phone') or '—'}",
            f"Email:        {inv.get('Customer_Email') or '—'}",
            f"Vehicle:      {inv['Registration_No']} · {inv.get('Brand') or ''} {inv.get('Model') or ''}",
            f"Service:      {inv['Service_Name']} (job #{inv['Service_Record_ID']})",
            f"Service date: {inv['Service_Date']}",
            f"Mechanic:     {inv['Mechanic_Name']}",
            "",
            "CHARGES",
            "-" * 44,
            f"Labour                                      {money(inv['Labour_Amount']):>14}",
        ]
        parts = inv.get("parts", [])
        if parts:
            for row in parts:
                lines.append(f"{row['Part_Name']} × {row['Quantity_Used']}  ({money(row['Cost'])})")
        else:
            lines.append("Spare parts                                  —")
        lines.extend([
            f"Parts total                                 {money(inv['Parts_Amount']):>14}",
            f"Tax                                          {money(inv['Tax']):>14}",
            "-" * 44,
            f"TOTAL                                        {money(inv['Total_Amount']):>14}",
            "",
            f"Reported issue: {inv.get('Problem_Description') or '—'}",
            f"Service remarks: {inv.get('Remarks') or '—'}",
            "",
            "Thank you for choosing GearDesk Service Centre.",
        ])
        return "\n".join(lines)

    def _save_html(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, title="Save invoice HTML", defaultextension=".html", filetypes=[("HTML file", "*.html")], initialfile=f"invoice_{self.invoice['Invoice_ID']}.html")
        if not path:
            return
        try:
            Path(path).write_text(self._invoice_html(), encoding="utf-8")
            messagebox.showinfo("Invoice exported", f"Print-ready invoice saved to:\n{path}\n\nOpen the file in a browser and choose Print to create a PDF.", parent=self)
        except Exception as exc:
            self.app.show_error("Could not export invoice", exc)

    def _invoice_html(self) -> str:
        inv = self.invoice
        parts_html = "".join(
            f"<tr><td>{html.escape(str(row['Part_Name']))}</td><td>{row['Quantity_Used']}</td><td>{money(row['Unit_Price'])}</td><td>{money(row['Cost'])}</td></tr>"
            for row in inv.get("parts", [])
        ) or '<tr><td colspan="4" class="muted">No spare parts</td></tr>'
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Invoice {inv['Invoice_ID']}</title>
<style>body{{font:15px Arial,sans-serif;color:#172b4d;background:#f3f5f9;margin:0;padding:32px}}.sheet{{max-width:780px;margin:auto;background:white;padding:42px;box-shadow:0 8px 30px #16253d18}}h1{{margin:0;color:#246bfd}}.sub{{color:#667085}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px 28px;margin:24px 0}}table{{width:100%;border-collapse:collapse;margin-top:18px}}th,td{{padding:10px;border-bottom:1px solid #e4e9f0;text-align:left}}th{{background:#f2f5f9}}.num{{text-align:right}}.totals{{width:320px;margin:18px 0 0 auto}}.totals td{{border:0;padding:5px}}.grand{{font-size:20px;font-weight:bold;border-top:2px solid #172b4d!important}}.muted{{color:#667085}}.pill{{background:#eaf2ff;color:#2857a4;padding:5px 10px;border-radius:30px}}@media print{{body{{background:white;padding:0}}.sheet{{box-shadow:none;max-width:none}}}}</style></head>
<body><main class="sheet"><h1>GearDesk</h1><div class="sub">Vehicle Service &amp; Maintenance Centre</div><hr>
<h2>Invoice #{inv['Invoice_ID']} <span class="pill">{html.escape(str(inv['Payment_Status']))}</span></h2><div class="sub">Invoice date: {html.escape(str(inv['Invoice_Date']))}</div>
<div class="grid"><div><b>Customer</b><br>{html.escape(str(inv['Customer_Name']))}<br>{html.escape(str(inv.get('Customer_Phone') or ''))}<br>{html.escape(str(inv.get('Customer_Email') or ''))}</div><div><b>Vehicle &amp; service</b><br>{html.escape(str(inv['Registration_No']))} · {html.escape(str(inv.get('Brand') or ''))} {html.escape(str(inv.get('Model') or ''))}<br>{html.escape(str(inv['Service_Name']))}<br>Job #{inv['Service_Record_ID']} · {html.escape(str(inv['Service_Date']))}<br>Mechanic: {html.escape(str(inv['Mechanic_Name']))}</div></div>
<table><thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th class="num">Amount</th></tr></thead><tbody>{parts_html}</tbody></table>
<table class="totals"><tr><td>Labour</td><td class="num">{money(inv['Labour_Amount'])}</td></tr><tr><td>Parts</td><td class="num">{money(inv['Parts_Amount'])}</td></tr><tr><td>Tax</td><td class="num">{money(inv['Tax'])}</td></tr><tr class="grand"><td>Total</td><td class="num">{money(inv['Total_Amount'])}</td></tr></table>
<p class="sub">Reported issue: {html.escape(str(inv.get('Problem_Description') or '—'))}</p><p class="sub">Thank you for choosing GearDesk.</p></main></body></html>"""
