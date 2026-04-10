"""Tkinter desktop GUI for selecting MySQL data and running GAMS."""

from __future__ import annotations

import re
import threading
import traceback
from collections.abc import Callable
from pathlib import Path
from tkinter import END, MULTIPLE, Listbox, StringVar, Tk, messagebox
from tkinter import ttk

import pandas as pd
from sqlalchemy.exc import OperationalError

from .db import DatabaseConfig, MySQLRepository, validate_where_clause
from .exporter import ExportArtifacts, ExportError, export_import_jobs, save_preview_csv, validate_gams_symbol_name
from .models import ImportJob, MaterializedImportJob, SEMANTIC_ROLES
from .runner import GAMSRunError, GAMSRunResult, run_gams_model
from .utils import DATA_DIR, GAMS_DIR, PROJECT_ROOT, configure_logging, load_db_config


class MySQLToGAMSApp:
    """Main tkinter application window."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("MySQL to GAMS Importer")
        self.root.geometry("1280x860")
        self.root.minsize(1040, 700)

        self.logger = configure_logging(PROJECT_ROOT / "data" / "app.log")
        self.preview_df: pd.DataFrame = pd.DataFrame()
        self.repo: MySQLRepository | None = None
        self.import_jobs: list[ImportJob] = []
        self.current_role_assignments: dict[str, str] = {}
        self.current_numeric_columns: set[str] = set()
        self.editing_job_index: int | None = None

        self.status_var = StringVar(value="Load configuration to begin.")
        self.table_var = StringVar()
        self.max_rows_var = StringVar(value="10")
        self.symbol_name_var = StringVar()
        self.where_var = StringVar()
        self.semantic_role_var = StringVar(value="index")

        self._build_layout()
        self._bind_form_state()
        self._load_configuration()

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(main_frame, text="Current Import Job", padding=12)
        controls.pack(fill="x")

        ttk.Button(
            controls, text="Connect to Database", command=self.connect_to_database
        ).grid(row=0, column=0, padx=(0, 10), pady=6, sticky="w")

        ttk.Label(controls, text="Table").grid(row=0, column=1, sticky="w")
        self.table_combo = ttk.Combobox(
            controls, textvariable=self.table_var, state="readonly", width=28
        )
        self.table_combo.grid(row=0, column=2, padx=(6, 10), pady=6, sticky="ew")
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_selected)

        ttk.Label(controls, text="Output symbol").grid(row=0, column=3, sticky="w")
        self.symbol_name_entry = ttk.Entry(
            controls, textvariable=self.symbol_name_var, width=24
        )
        self.symbol_name_entry.grid(row=0, column=4, padx=(6, 10), pady=6, sticky="ew")

        ttk.Label(controls, text="Max rows").grid(row=0, column=5, sticky="w")
        self.max_rows_entry = ttk.Entry(controls, textvariable=self.max_rows_var, width=12)
        self.max_rows_entry.grid(row=0, column=6, padx=(6, 0), pady=6, sticky="w")

        ttk.Label(controls, text="Filter expression").grid(row=1, column=0, sticky="w", pady=(8, 4))
        self.where_entry = ttk.Entry(controls, textvariable=self.where_var)
        self.where_entry.grid(
            row=1, column=1, columnspan=6, padx=(6, 0), pady=(8, 4), sticky="ew"
        )

        ttk.Label(controls, text="Columns").grid(row=2, column=0, sticky="nw", pady=(10, 4))
        self.columns_listbox = Listbox(
            controls,
            selectmode=MULTIPLE,
            exportselection=False,
            width=42,
            height=11,
        )
        self.columns_listbox.grid(
            row=2, column=1, columnspan=3, padx=(6, 10), pady=(10, 6), sticky="nsew"
        )

        list_scrollbar = ttk.Scrollbar(
            controls, orient="vertical", command=self.columns_listbox.yview
        )
        list_scrollbar.grid(row=2, column=4, pady=(10, 6), sticky="nsw")
        self.columns_listbox.config(yscrollcommand=list_scrollbar.set)
        self.columns_listbox.bind("<<ListboxSelect>>", self._refresh_role_assignments)

        role_frame = ttk.LabelFrame(controls, text="Semantic Roles", padding=10)
        role_frame.grid(row=3, column=0, columnspan=5, padx=(0, 10), pady=(8, 0), sticky="nsew")

        ttk.Label(role_frame, text="Role").grid(row=0, column=0, sticky="w")
        self.semantic_role_combo = ttk.Combobox(
            role_frame,
            textvariable=self.semantic_role_var,
            state="readonly",
            values=list(SEMANTIC_ROLES),
            width=16,
        )
        self.semantic_role_combo.grid(row=0, column=1, padx=(6, 10), sticky="w")

        ttk.Button(
            role_frame,
            text="Assign Role To Selected Columns",
            command=self.assign_role_to_selected_columns,
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")
        ttk.Button(
            role_frame,
            text="Clear Role From Selected Columns",
            command=self.clear_role_from_selected_columns,
        ).grid(row=0, column=3, sticky="w")

        self.roles_tree = ttk.Treeview(
            role_frame,
            columns=("column", "role"),
            show="headings",
            height=5,
        )
        self.roles_tree.heading("column", text="Selected Column")
        self.roles_tree.heading("role", text="Assigned Role")
        self.roles_tree.column("column", width=260, anchor="w")
        self.roles_tree.column("role", width=140, anchor="w")
        self.roles_tree.grid(row=1, column=0, columnspan=4, pady=(10, 0), sticky="nsew")
        role_frame.columnconfigure(3, weight=1)

        actions_frame = ttk.Frame(controls)
        actions_frame.grid(row=2, column=5, columnspan=2, rowspan=2, padx=(12, 0), pady=(10, 6), sticky="ne")
        ttk.Button(actions_frame, text="Preview Current Selection", command=self.preview_data).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Add Import Job", command=self.add_import_job).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Update Selected Basket Item", command=self.update_selected_job).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Load Selected Item Into Form", command=self.edit_selected_job).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Duplicate Selected Basket Item", command=self.duplicate_selected_job).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Remove Selected Job", command=self.remove_selected_job).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(actions_frame, text="Export Basket and Run GAMS", command=self.export_and_run).pack(
            fill="x"
        )

        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(4, weight=1)
        controls.rowconfigure(2, weight=1)

        basket_frame = ttk.LabelFrame(main_frame, text="Import Basket", padding=12)
        basket_frame.pack(fill="x", pady=(12, 0))

        self.basket_tree = ttk.Treeview(
            basket_frame,
            columns=("symbol", "table", "rows", "filter", "columns", "roles"),
            show="headings",
            height=7,
        )
        self.basket_tree.heading("symbol", text="Output Symbol")
        self.basket_tree.heading("table", text="Source Table")
        self.basket_tree.heading("rows", text="Max Rows")
        self.basket_tree.heading("filter", text="Filter expression")
        self.basket_tree.heading("columns", text="Selected Columns")
        self.basket_tree.heading("roles", text="Semantic Roles")
        self.basket_tree.column("symbol", width=180, anchor="w")
        self.basket_tree.column("table", width=170, anchor="w")
        self.basket_tree.column("rows", width=80, anchor="center")
        self.basket_tree.column("filter", width=220, anchor="w")
        self.basket_tree.column("columns", width=320, anchor="w")
        self.basket_tree.column("roles", width=260, anchor="w")
        self.basket_tree.pack(side="left", fill="x", expand=True)

        basket_scrollbar = ttk.Scrollbar(
            basket_frame, orient="vertical", command=self.basket_tree.yview
        )
        basket_scrollbar.pack(side="right", fill="y")
        self.basket_tree.configure(yscrollcommand=basket_scrollbar.set)
        self.basket_tree.bind("<<TreeviewSelect>>", self._on_basket_selection_changed)

        diagnostics_frame = ttk.Frame(main_frame)
        diagnostics_frame.pack(fill="x", pady=(12, 0))

        readiness_frame = ttk.LabelFrame(diagnostics_frame, text="Pre-Run Readiness", padding=12)
        readiness_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.readiness_tree = ttk.Treeview(
            readiness_frame,
            columns=("field", "value"),
            show="headings",
            height=7,
        )
        self.readiness_tree.heading("field", text="Field")
        self.readiness_tree.heading("value", text="Current Value")
        self.readiness_tree.column("field", width=170, anchor="w")
        self.readiness_tree.column("value", width=480, anchor="w")
        self.readiness_tree.pack(fill="both", expand=True)

        results_frame = ttk.LabelFrame(diagnostics_frame, text="Post-Run Results", padding=12)
        results_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.results_tree = ttk.Treeview(
            results_frame,
            columns=("artifact", "path"),
            show="headings",
            height=7,
        )
        self.results_tree.heading("artifact", text="Artifact")
        self.results_tree.heading("path", text="Location")
        self.results_tree.column("artifact", width=180, anchor="w")
        self.results_tree.column("path", width=470, anchor="w")
        self.results_tree.pack(fill="both", expand=True)

        preview_frame = ttk.LabelFrame(main_frame, text="Preview Of Current Selection", padding=12)
        preview_frame.pack(fill="both", expand=True, pady=(12, 0))

        self.preview_tree = ttk.Treeview(preview_frame, show="headings")
        self.preview_tree.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(
            preview_frame, orient="vertical", command=self.preview_tree.yview
        )
        y_scroll.pack(side="right", fill="y")
        x_scroll = ttk.Scrollbar(
            main_frame, orient="horizontal", command=self.preview_tree.xview
        )
        x_scroll.pack(fill="x")
        self.preview_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, anchor="w", padding=(12, 8)
        )
        status_bar.pack(fill="x")
        self._refresh_readiness_panel()
        self._populate_results_panel([])

    def _load_configuration(self) -> None:
        try:
            config_data, warnings = load_db_config()
            self.config = DatabaseConfig(**config_data)
            if warnings:
                self.status_var.set(warnings[0])
                self.logger.warning(warnings[0])
            else:
                self.status_var.set("Configuration loaded successfully.")
        except Exception as exc:
            self.logger.exception("Failed to load configuration")
            messagebox.showerror("Configuration Error", str(exc))
            self.status_var.set("Configuration could not be loaded.")

    def _bind_form_state(self) -> None:
        """Refresh readiness information whenever the form changes."""
        for variable in (
            self.table_var,
            self.max_rows_var,
            self.symbol_name_var,
            self.where_var,
            self.semantic_role_var,
        ):
            variable.trace_add("write", self._on_form_field_changed)

    def _on_form_field_changed(self, *_args: object) -> None:
        """Handle entry and combobox edits from traced tkinter variables."""
        self._refresh_readiness_panel()

    def _refresh_readiness_panel(self) -> None:
        """Show a concise readiness summary for the current form state."""
        self.readiness_tree.delete(*self.readiness_tree.get_children())

        selected_columns = self._selected_columns()
        filter_text = self.where_var.get().strip()
        filter_status = "Valid simple filter"
        if filter_text:
            try:
                validate_where_clause(filter_text)
            except ValueError as exc:
                filter_status = f"Needs attention: {exc}"

        readiness_rows = [
            ("Selected table", self.table_var.get().strip() or "(not selected)"),
            ("Selected columns", ", ".join(selected_columns) or "(none)"),
            ("Output symbol", self.symbol_name_var.get().strip() or "(not set)"),
            ("Row limit", self.max_rows_var.get().strip() or "(not set)"),
            ("Filter", filter_text or "(none)"),
            ("Filter status", filter_status),
            (
                "Numeric columns present",
                self._format_numeric_presence(selected_columns),
            ),
            (
                "Edit mode",
                f"Editing basket item #{self.editing_job_index + 1}"
                if self.editing_job_index is not None
                else "Adding a new basket item",
            ),
        ]

        for index, row in enumerate(readiness_rows):
            self.readiness_tree.insert("", END, iid=str(index), values=row)

    def _populate_results_panel(self, rows: list[tuple[str, str]]) -> None:
        """Display the most recent exported artifact locations."""
        self.results_tree.delete(*self.results_tree.get_children())
        if not rows:
            rows = [("No run yet", "Export basket data and run GAMS to populate artifacts.")]
        for index, row in enumerate(rows):
            self.results_tree.insert("", END, iid=str(index), values=row)

    def _format_numeric_presence(self, selected_columns: list[str]) -> str:
        """Summarize whether the current selection includes numeric columns."""
        if not selected_columns:
            return "No columns selected yet"
        numeric_selected = [column for column in selected_columns if column in self.current_numeric_columns]
        if numeric_selected:
            return f"Yes: {', '.join(numeric_selected)}"
        if self.table_var.get().strip() and self.current_numeric_columns:
            return "No: selected columns are currently nonnumeric"
        if self.table_var.get().strip():
            return "Unknown until table metadata is loaded"
        return "Unknown until a table is selected"

    def connect_to_database(self) -> None:
        if not hasattr(self, "config"):
            messagebox.showerror(
                "Configuration Error",
                "Database configuration is not available. Check the config files first.",
            )
            return

        def task() -> list[str]:
            self.repo = MySQLRepository(self.config)
            self.repo.test_connection()
            return self.repo.list_tables()

        def on_success(tables: list[str]) -> None:
            self.table_combo["values"] = tables
            self.status_var.set(f"Connected successfully. {len(tables)} table(s) available.")
            messagebox.showinfo(
                "Connection Successful",
                f"Connected to database '{self.config.database}'.",
            )

        self._run_in_background(task, on_success, "Connecting to MySQL database...")

    def _on_table_selected(self, _event: object) -> None:
        table_name = self.table_var.get()
        if not table_name or self.repo is None:
            return

        if not self.symbol_name_var.get().strip():
            self.symbol_name_var.set(self._suggest_symbol_name(table_name))
        self.current_role_assignments.clear()
        self.current_numeric_columns.clear()
        self._refresh_readiness_panel()

        def task() -> tuple[list[str], list[str]]:
            assert self.repo is not None
            return (
                self.repo.list_columns(table_name),
                self.repo.list_numeric_columns(table_name),
            )

        def on_success(result: tuple[list[str], list[str]]) -> None:
            columns, numeric_columns = result
            self.columns_listbox.delete(0, END)
            for column_name in columns:
                self.columns_listbox.insert(END, column_name)
            self.current_numeric_columns = set(numeric_columns)
            self._refresh_role_assignments()
            self._refresh_readiness_panel()
            self.status_var.set(
                f"Loaded {len(columns)} column(s) for table '{table_name}'. "
                f"{len(numeric_columns)} numeric column(s) detected."
            )

        self._run_in_background(task, on_success, f"Loading columns for {table_name}...")

    def _selected_columns(self) -> list[str]:
        indices = self.columns_listbox.curselection()
        return [self.columns_listbox.get(index) for index in indices]

    def _suggest_symbol_name(self, table_name: str) -> str:
        """Derive a safe default output symbol name from the selected table."""
        parts = [part.lower() for part in re.split(r"[^A-Za-z0-9]+", table_name) if part]
        if not parts:
            return "importedData"
        symbol_name = parts[0] + "".join(part.title() for part in parts[1:]) + "Data"
        if symbol_name[0].isdigit():
            symbol_name = f"_{symbol_name}"
        return symbol_name

    def _build_import_job(self, require_symbol: bool = True) -> ImportJob:
        """Build and validate the current GUI form as an import job."""
        if self.repo is None:
            raise ExportError("Connect to the database before building import jobs.")

        table_name = self.table_var.get().strip()
        if not table_name:
            raise ExportError("Select a source table before adding an import job.")
        available_tables = set(self.table_combo.cget("values") or [])
        if available_tables and table_name not in available_tables:
            raise ExportError(
                f"Table '{table_name}' is not available in the connected database. "
                "Reload the table list and choose a valid source table."
            )

        selected_columns = self._selected_columns()
        if not selected_columns:
            raise ExportError("Select at least one column before adding an import job.")
        available_columns = {
            self.columns_listbox.get(index) for index in range(self.columns_listbox.size())
        }
        unknown_columns = [column for column in selected_columns if column not in available_columns]
        if unknown_columns:
            raise ExportError(
                "One or more selected columns are no longer available in the current table: "
                + ", ".join(unknown_columns)
            )

        try:
            max_rows = int(self.max_rows_var.get().strip())
        except ValueError as exc:
            raise ExportError("Max rows must be a positive integer.") from exc
        if max_rows <= 0:
            raise ExportError("Max rows must be a positive integer.")

        symbol_name = self.symbol_name_var.get().strip()
        if not symbol_name and not require_symbol:
            symbol_name = self._suggest_symbol_name(table_name)
            self.symbol_name_var.set(symbol_name)
        try:
            symbol_name = validate_gams_symbol_name(symbol_name)
        except ExportError as exc:
            raise ExportError(
                f"{exc} Example safe symbol names: productsData, laborCostData, importedProfit."
            ) from exc

        where_clause = self.where_var.get().strip()
        try:
            validated_where = validate_where_clause(where_clause)
        except ValueError as exc:
            raise ExportError(
                f"{exc} Keep the filter to a simple expression such as Anno = 2023 or profit > 0."
            ) from exc

        return ImportJob(
            table_name=table_name,
            selected_columns=selected_columns,
            max_rows=max_rows,
            symbol_name=symbol_name,
            where_clause=validated_where,
            semantic_roles={
                column_name: role
                for column_name, role in self.current_role_assignments.items()
                if column_name in selected_columns
            },
        )

    def assign_role_to_selected_columns(self) -> None:
        """Assign the chosen semantic role to the selected columns."""
        selected_columns = self._selected_columns()
        if not selected_columns:
            messagebox.showerror(
                "Semantic Role Assignment",
                "Select one or more columns before assigning a semantic role.",
            )
            return

        role = self.semantic_role_var.get().strip().lower()
        for column_name in selected_columns:
            self.current_role_assignments[column_name] = role
        self._refresh_role_assignments()
        self._refresh_readiness_panel()
        self.status_var.set(
            f"Assigned role '{role}' to {len(selected_columns)} selected column(s)."
        )

    def clear_role_from_selected_columns(self) -> None:
        """Remove semantic role assignments from the selected columns."""
        selected_columns = self._selected_columns()
        if not selected_columns:
            messagebox.showerror(
                "Semantic Role Assignment",
                "Select one or more columns before clearing semantic roles.",
            )
            return

        for column_name in selected_columns:
            self.current_role_assignments.pop(column_name, None)
        self._refresh_role_assignments()
        self._refresh_readiness_panel()
        self.status_var.set("Cleared semantic roles from selected column(s).")

    def _refresh_role_assignments(self, _event: object | None = None) -> None:
        """Refresh the semantic role table for the current GUI selection."""
        self.roles_tree.delete(*self.roles_tree.get_children())
        selected_columns = self._selected_columns()
        for column_name in selected_columns:
            self.roles_tree.insert(
                "",
                END,
                values=(
                    column_name,
                    self.current_role_assignments.get(column_name, "(none)"),
                ),
            )
        self._refresh_readiness_panel()

    def add_import_job(self) -> None:
        """Add the current selection to the import basket."""
        try:
            job = self._build_import_job()
        except ExportError as exc:
            messagebox.showerror("Import Job Error", str(exc))
            return

        if any(existing.symbol_name == job.symbol_name for existing in self.import_jobs):
            messagebox.showerror(
                "Import Job Error",
                f"An import job with symbol name '{job.symbol_name}' is already in the basket.",
            )
            return

        self.import_jobs.append(job)
        self.editing_job_index = None
        self._refresh_basket()
        self._refresh_readiness_panel()
        self.logger.info("Added import job '%s' from table '%s'.", job.symbol_name, job.table_name)
        self.status_var.set(
            f"Added import job '{job.symbol_name}' from table '{job.table_name}'."
        )

    def update_selected_job(self) -> None:
        """Persist current form values into the selected basket item."""
        target_index = self.editing_job_index
        if target_index is None:
            selection = self.basket_tree.selection()
            if len(selection) != 1:
                messagebox.showerror(
                    "Update Import Job",
                    "Select exactly one basket item, then edit it before saving changes.",
                )
                return
            target_index = int(selection[0])

        try:
            job = self._build_import_job()
        except ExportError as exc:
            messagebox.showerror("Update Import Job", str(exc))
            return

        duplicate_symbols = [
            existing.symbol_name
            for index, existing in enumerate(self.import_jobs)
            if index != target_index and existing.symbol_name == job.symbol_name
        ]
        if duplicate_symbols:
            messagebox.showerror(
                "Update Import Job",
                f"Another basket item already uses symbol name '{job.symbol_name}'.",
            )
            return

        self.import_jobs[target_index] = job
        self.editing_job_index = target_index
        self._refresh_basket()
        self.basket_tree.selection_set(str(target_index))
        self._refresh_readiness_panel()
        self.logger.info("Updated import job '%s' at basket index %d.", job.symbol_name, target_index)
        self.status_var.set(
            f"Updated basket item '{job.symbol_name}' from table '{job.table_name}'."
        )

    def edit_selected_job(self) -> None:
        """Load a basket item back into the form for editing."""
        selection = self.basket_tree.selection()
        if len(selection) != 1:
            messagebox.showerror(
                "Edit Import Job",
                "Select exactly one basket item before editing it.",
            )
            return

        index = int(selection[0])
        self._load_job_into_form(index)
        self.status_var.set(
            f"Loaded basket item '{self.import_jobs[index].symbol_name}' into the form for editing."
        )

    def duplicate_selected_job(self) -> None:
        """Duplicate the selected basket item with a unique symbol name."""
        selection = self.basket_tree.selection()
        if len(selection) != 1:
            messagebox.showerror(
                "Duplicate Import Job",
                "Select exactly one basket item before duplicating it.",
            )
            return

        index = int(selection[0])
        source_job = self.import_jobs[index]
        duplicated_symbol = self._generate_unique_symbol_name(source_job.symbol_name)
        duplicated_job = ImportJob(
            table_name=source_job.table_name,
            selected_columns=list(source_job.selected_columns),
            max_rows=source_job.max_rows,
            symbol_name=duplicated_symbol,
            where_clause=source_job.where_clause,
            semantic_roles=dict(source_job.semantic_roles),
        )
        self.import_jobs.append(duplicated_job)
        new_index = len(self.import_jobs) - 1
        self._refresh_basket()
        self.basket_tree.selection_set(str(new_index))
        self._load_job_into_form(new_index)
        self.logger.info(
            "Duplicated import job '%s' as '%s'.",
            source_job.symbol_name,
            duplicated_symbol,
        )
        self.status_var.set(
            f"Duplicated basket item '{source_job.symbol_name}' as '{duplicated_symbol}'."
        )

    def remove_selected_job(self) -> None:
        """Remove the currently selected import job from the basket."""
        selection = self.basket_tree.selection()
        if not selection:
            messagebox.showerror(
                "Remove Import Job",
                "Select an import job in the basket before removing it.",
            )
            return

        indices = sorted((int(item_id) for item_id in selection), reverse=True)
        for index in indices:
            del self.import_jobs[index]
        if self.editing_job_index in indices:
            self.editing_job_index = None
        elif self.editing_job_index is not None:
            removed_before = sum(1 for index in indices if index < self.editing_job_index)
            self.editing_job_index -= removed_before
        self._refresh_basket()
        self._refresh_readiness_panel()
        self.logger.info("Removed %d import job(s) from the basket.", len(indices))
        self.status_var.set("Removed selected import job(s) from the basket.")

    def _load_job_into_form(self, index: int) -> None:
        """Load a queued basket item back into the editable form."""
        job = self.import_jobs[index]
        self.editing_job_index = index
        self.table_var.set(job.table_name)
        self.symbol_name_var.set(job.symbol_name)
        self.max_rows_var.set(str(job.max_rows))
        self.where_var.set(job.where_clause)
        self.current_role_assignments = dict(job.semantic_roles)

        if self.repo is None:
            self._refresh_readiness_panel()
            return

        def task() -> tuple[list[str], list[str]]:
            assert self.repo is not None
            return (
                self.repo.list_columns(job.table_name),
                self.repo.list_numeric_columns(job.table_name),
            )

        def on_success(result: tuple[list[str], list[str]]) -> None:
            columns, numeric_columns = result
            self.columns_listbox.delete(0, END)
            for column_name in columns:
                self.columns_listbox.insert(END, column_name)
            self.current_numeric_columns = set(numeric_columns)
            index_lookup = {column_name: pos for pos, column_name in enumerate(columns)}
            for column_name in job.selected_columns:
                if column_name in index_lookup:
                    self.columns_listbox.selection_set(index_lookup[column_name])
            self._refresh_role_assignments()
            self._refresh_readiness_panel()

        self._run_in_background(
            task,
            on_success,
            f"Loading basket item '{job.symbol_name}' into the current form...",
        )

    def _generate_unique_symbol_name(self, base_symbol: str) -> str:
        """Create a basket-safe symbol name for duplicated jobs."""
        candidate_base = f"{base_symbol}Copy"
        existing = {job.symbol_name for job in self.import_jobs}
        candidate = candidate_base
        suffix = 2
        while candidate in existing:
            candidate = f"{candidate_base}{suffix}"
            suffix += 1
        return candidate

    def _on_basket_selection_changed(self, _event: object) -> None:
        """Reflect current basket selection in the status bar."""
        selection = self.basket_tree.selection()
        if len(selection) == 1:
            job = self.import_jobs[int(selection[0])]
            self.status_var.set(
                f"Selected basket item '{job.symbol_name}' from table '{job.table_name}'."
            )

    def _refresh_basket(self) -> None:
        """Refresh the import basket treeview."""
        self.basket_tree.delete(*self.basket_tree.get_children())
        for index, job in enumerate(self.import_jobs):
            self.basket_tree.insert(
                "",
                END,
                iid=str(index),
                values=(
                    job.symbol_name,
                    job.table_name,
                    job.max_rows,
                    job.where_clause or "(none)",
                    ", ".join(job.selected_columns),
                    ", ".join(
                        f"{column}:{role}" for column, role in sorted(job.semantic_roles.items())
                    )
                    or "(none)",
                ),
            )

    def preview_data(self) -> None:
        """Preview the current GUI selection without adding it to the basket."""
        try:
            job = self._build_import_job(require_symbol=False)
        except ExportError as exc:
            messagebox.showerror("Preview Error", str(exc))
            return

        def task() -> pd.DataFrame:
            assert self.repo is not None
            dataframe = self.repo.fetch_preview(
                job.table_name,
                job.selected_columns,
                job.max_rows,
                job.where_clause,
            )
            save_preview_csv(dataframe, DATA_DIR)
            return dataframe

        def on_success(dataframe: pd.DataFrame) -> None:
            self.preview_df = dataframe
            self._populate_preview(dataframe)
            self._populate_results_panel(
                [("Preview CSV", str(DATA_DIR / "exported_preview.csv"))]
            )
            self.status_var.set(
                f"Preview loaded with {len(dataframe)} row(s). "
                "Preview CSV saved to data/exported_preview.csv."
            )

        self._run_in_background(task, on_success, "Fetching preview data...")

    def export_and_run(self) -> None:
        """Export queued jobs, generate reusable GAMS symbols, and run the model."""
        if self.repo is None:
            messagebox.showerror("Connection Required", "Connect to the database first.")
            return

        try:
            queued_jobs = list(self.import_jobs)
            if not queued_jobs:
                queued_jobs = [self._build_import_job(require_symbol=False)]
            self._validate_jobs_ready_for_run(queued_jobs)
        except ExportError as exc:
            messagebox.showerror("Export Error", str(exc))
            return

        def task() -> tuple[ExportArtifacts, GAMSRunResult]:
            assert self.repo is not None
            materialized_jobs: list[MaterializedImportJob] = []
            for job in queued_jobs:
                self.logger.info(
                    "Fetching import job '%s' from table '%s' with %d selected column(s), max_rows=%d, filter=%r",
                    job.symbol_name,
                    job.table_name,
                    len(job.selected_columns),
                    job.max_rows,
                    job.where_clause,
                )
                dataframe = self.repo.fetch_preview(
                    job.table_name,
                    job.selected_columns,
                    job.max_rows,
                    job.where_clause,
                )
                materialized_jobs.append(MaterializedImportJob(job=job, dataframe=dataframe))

            artifacts = export_import_jobs(materialized_jobs, DATA_DIR, GAMS_DIR)
            self.preview_df = materialized_jobs[0].dataframe
            run_result = run_gams_model(PROJECT_ROOT, GAMS_DIR / "model.gms")
            return artifacts, run_result

        def on_success(result: tuple[ExportArtifacts, GAMSRunResult]) -> None:
            artifacts, run_result = result
            self._populate_preview(self.preview_df)
            self._populate_results_panel(
                [
                    ("Preview CSV", str(artifacts.preview_csv)),
                    ("Legacy long CSV", str(artifacts.legacy_long_csv)),
                    ("Import job CSV folder", str(artifacts.job_directory)),
                    ("Import manifest", str(artifacts.manifest_csv)),
                    ("Generated runtime include", str(artifacts.generated_runtime_include)),
                    ("Generated symbol include", str(artifacts.generated_symbol_include)),
                    (
                        "Generated semantic declarations",
                        str(artifacts.generated_semantic_declarations_include),
                    ),
                    (
                        "Generated semantic mapping",
                        str(artifacts.generated_semantic_mapping_include),
                    ),
                    ("Generated example consumer", str(artifacts.generated_example_model)),
                    ("Listing file", str(run_result.listing_file)),
                    ("Log file", str(run_result.log_file)),
                    ("GDX handoff", str(run_result.gdx_file)),
                ]
            )
            self.status_var.set(
                f"Exported {len(artifacts.symbol_names)} import job(s) and ran GAMS successfully."
            )
            studio_note = (
                "GAMS Studio was opened automatically on the model, listing, and GDX data files."
                if run_result.studio_opened
                else "GAMS Studio could not be opened automatically, but the GAMS artifacts were created successfully."
            )
            optimization_note = (
                run_result.optimization_message + "\n\n"
                if run_result.optimization_message
                else ""
            )
            symbol_lines = "\n".join(f"- {symbol_name}(obs,col)" for symbol_name in artifacts.symbol_names)
            messagebox.showinfo(
                "Export and Run Complete",
                "Queued SQL imports were exported successfully and GAMS completed without errors.\n\n"
                f"{optimization_note}"
                f"{studio_note}\n\n"
                f"Primary backward-compatible symbol: data(obs,col) from '{artifacts.primary_symbol_name}'\n"
                "Reusable imported symbols created in this run:\n"
                f"{symbol_lines}\n\n"
                "Assigned semantic roles are available in the generated semantic mapping include.\n\n"
                f"GDX data: {run_result.gdx_file}\n"
                f"Import job folder: {artifacts.job_directory}\n"
                f"Manifest: {artifacts.manifest_csv}\n"
                f"Runtime include: {artifacts.generated_runtime_include}\n"
                f"Symbol include: {artifacts.generated_symbol_include}\n"
                f"Semantic declarations: {artifacts.generated_semantic_declarations_include}\n"
                f"Semantic mapping include: {artifacts.generated_semantic_mapping_include}\n"
                f"Example consumer: {artifacts.generated_example_model}\n"
                f"Listing file: {run_result.listing_file}\n"
                f"Log file: {run_result.log_file}",
            )

        self._run_in_background(
            task,
            on_success,
            "Exporting queued import jobs and running GAMS...",
        )

    def _validate_jobs_ready_for_run(self, jobs: list[ImportJob]) -> None:
        """Perform fast metadata checks before starting a full export run."""
        if self.repo is None:
            raise ExportError("Connect to the database before running GAMS.")

        symbol_names: set[str] = set()
        readiness_warnings: list[str] = []
        for job in jobs:
            if job.symbol_name in symbol_names:
                raise ExportError(
                    f"The import basket contains duplicate symbol name '{job.symbol_name}'. "
                    "Each job must have a unique GAMS output symbol."
                )
            symbol_names.add(job.symbol_name)

            numeric_columns = set(self.repo.list_numeric_columns(job.table_name))
            numeric_selected = [column for column in job.selected_columns if column in numeric_columns]
            if not numeric_selected:
                readiness_warnings.append(
                    f"- {job.symbol_name}: no numeric columns are currently selected in table '{job.table_name}'"
                )

        if readiness_warnings:
            raise ExportError(
                "The current basket is not ready for GAMS export because at least one job has no numeric columns.\n\n"
                + "\n".join(readiness_warnings)
                + "\n\nAdjust the selected columns before running GAMS."
            )

    def _populate_preview(self, dataframe: pd.DataFrame) -> None:
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_tree["columns"] = list(dataframe.columns)

        for column_name in dataframe.columns:
            self.preview_tree.heading(column_name, text=column_name)
            self.preview_tree.column(column_name, width=150, minwidth=100, anchor="w")

        for row in dataframe.itertuples(index=False, name=None):
            self.preview_tree.insert("", END, values=[str(value) for value in row])

    def _run_in_background(
        self,
        task: Callable[[], object],
        on_success: Callable[[object], None],
        status_message: str,
    ) -> None:
        self.status_var.set(status_message)

        def worker() -> None:
            try:
                result = task()
            except ExportError as exc:
                self.logger.warning("Export validation failed: %s", exc)
                self._show_async_error("Export validation failed.", "Export Error", str(exc))
            except GAMSRunError as exc:
                self.logger.error("GAMS run failed: %s", exc)
                self._show_async_error("GAMS execution failed.", "GAMS Error", str(exc))
            except OperationalError as exc:
                self.logger.error("Database operation failed: %s\n%s", exc, traceback.format_exc())
                friendly_message = self._format_database_error(exc)
                self._show_async_error(
                    "Database connection failed.",
                    "Database Error",
                    friendly_message,
                )
            except Exception as exc:
                self.logger.error("Unexpected error: %s\n%s", exc, traceback.format_exc())
                self._show_async_error(
                    "An unexpected error occurred.",
                    "Application Error",
                    str(exc),
                )
            else:
                self.root.after(0, lambda: on_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _show_async_error(self, status: str, title: str, message: str) -> None:
        """Schedule a GUI error message from a worker thread."""
        self.root.after(
            0,
            lambda status_text=status, dialog_title=title, dialog_message=message: (
                self.status_var.set(status_text),
                messagebox.showerror(dialog_title, dialog_message),
            ),
        )

    def _format_database_error(self, error: OperationalError) -> str:
        """Return a clearer GUI message for common MySQL connection failures."""
        error_text = str(error)

        if "getaddrinfo failed" in error_text:
            return (
                "The MySQL host name could not be resolved. "
                "Check the 'host' value in config/db_config.json. "
                "It may still contain a placeholder or an invalid server name."
            )
        if "Access denied" in error_text:
            return (
                "MySQL rejected the username or password. "
                "Check the credentials in config/db_config.json."
            )
        if "Can't connect to MySQL server" in error_text:
            return (
                "Could not reach the MySQL server. Verify the host, port, network access, "
                "and whether the database server is online."
            )

        return error_text


def main() -> None:
    """Start the tkinter desktop application."""
    root = Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = MySQLToGAMSApp(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
