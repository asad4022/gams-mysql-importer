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

from .db import DatabaseConfig, MySQLRepository
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

        self.status_var = StringVar(value="Load configuration to begin.")
        self.table_var = StringVar()
        self.max_rows_var = StringVar(value="10")
        self.symbol_name_var = StringVar()
        self.where_var = StringVar()
        self.semantic_role_var = StringVar(value="index")

        self._build_layout()
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

        ttk.Label(controls, text="Filter / WHERE").grid(row=1, column=0, sticky="w", pady=(8, 4))
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
        self.basket_tree.heading("filter", text="Filter / WHERE")
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

        def task() -> list[str]:
            assert self.repo is not None
            return self.repo.list_columns(table_name)

        def on_success(columns: list[str]) -> None:
            self.columns_listbox.delete(0, END)
            for column_name in columns:
                self.columns_listbox.insert(END, column_name)
            self._refresh_role_assignments()
            self.status_var.set(
                f"Loaded {len(columns)} column(s) for table '{table_name}'."
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

        selected_columns = self._selected_columns()
        if not selected_columns:
            raise ExportError("Select at least one column before adding an import job.")

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
        symbol_name = validate_gams_symbol_name(symbol_name)

        return ImportJob(
            table_name=table_name,
            selected_columns=selected_columns,
            max_rows=max_rows,
            symbol_name=symbol_name,
            where_clause=self.where_var.get().strip(),
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
        self._refresh_basket()
        self.status_var.set(
            f"Added import job '{job.symbol_name}' from table '{job.table_name}'."
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
        self._refresh_basket()
        self.status_var.set("Removed selected import job(s) from the basket.")

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
        except ExportError as exc:
            messagebox.showerror("Export Error", str(exc))
            return

        def task() -> tuple[ExportArtifacts, GAMSRunResult]:
            assert self.repo is not None
            materialized_jobs: list[MaterializedImportJob] = []
            for job in queued_jobs:
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
                f"Runtime include: {artifacts.generated_runtime_include}\n"
                f"Symbol include: {artifacts.generated_symbol_include}\n"
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
