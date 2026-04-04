"""Tkinter desktop GUI for selecting MySQL data and running GAMS."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from pathlib import Path
from tkinter import END, MULTIPLE, Listbox, StringVar, Tk, messagebox
from tkinter import ttk

import pandas as pd

from .db import DatabaseConfig, MySQLRepository
from .exporter import ExportError, save_long_csv, save_preview_csv
from .runner import GAMSRunError, run_gams_model
from .utils import DATA_DIR, GAMS_DIR, PROJECT_ROOT, configure_logging, load_db_config


class MySQLToGAMSApp:
    """Main tkinter application window."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("MySQL to GAMS Importer")
        self.root.geometry("1100x720")
        self.root.minsize(900, 620)

        self.logger = configure_logging(PROJECT_ROOT / "data" / "app.log")
        self.preview_df: pd.DataFrame = pd.DataFrame()
        self.repo: MySQLRepository | None = None

        self.status_var = StringVar(value="Load configuration to begin.")
        self.table_var = StringVar()
        self.max_rows_var = StringVar(value="10")

        self._build_layout()
        self._load_configuration()

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(main_frame, text="Data Selection", padding=12)
        controls.pack(fill="x")

        ttk.Button(
            controls, text="Connect to Database", command=self.connect_to_database
        ).grid(row=0, column=0, padx=(0, 10), pady=6, sticky="w")

        ttk.Label(controls, text="Table").grid(row=0, column=1, sticky="w")
        self.table_combo = ttk.Combobox(
            controls, textvariable=self.table_var, state="readonly", width=35
        )
        self.table_combo.grid(row=0, column=2, padx=(6, 10), pady=6, sticky="ew")
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_selected)

        ttk.Label(controls, text="Max rows").grid(row=0, column=3, sticky="w")
        self.max_rows_entry = ttk.Entry(controls, textvariable=self.max_rows_var, width=12)
        self.max_rows_entry.grid(row=0, column=4, padx=(6, 10), pady=6, sticky="w")

        ttk.Label(controls, text="Columns").grid(row=1, column=0, sticky="nw", pady=(10, 4))
        self.columns_listbox = Listbox(
            controls,
            selectmode=MULTIPLE,
            exportselection=False,
            width=40,
            height=10,
        )
        self.columns_listbox.grid(
            row=1, column=1, columnspan=2, padx=(6, 10), pady=(10, 6), sticky="nsew"
        )

        list_scrollbar = ttk.Scrollbar(
            controls, orient="vertical", command=self.columns_listbox.yview
        )
        list_scrollbar.grid(row=1, column=3, pady=(10, 6), sticky="nsw")
        self.columns_listbox.config(yscrollcommand=list_scrollbar.set)

        actions_frame = ttk.Frame(controls)
        actions_frame.grid(row=1, column=4, padx=(6, 0), pady=(10, 6), sticky="ne")
        ttk.Button(actions_frame, text="Preview Data", command=self.preview_data).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(
            actions_frame, text="Export and Run GAMS", command=self.export_and_run
        ).pack(fill="x")

        controls.columnconfigure(2, weight=1)
        controls.rowconfigure(1, weight=1)

        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=12)
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

        def task() -> list[str]:
            assert self.repo is not None
            return self.repo.list_columns(table_name)

        def on_success(columns: list[str]) -> None:
            self.columns_listbox.delete(0, END)
            for column_name in columns:
                self.columns_listbox.insert(END, column_name)
            self.status_var.set(
                f"Loaded {len(columns)} column(s) for table '{table_name}'."
            )

        self._run_in_background(task, on_success, f"Loading columns for {table_name}...")

    def _selected_columns(self) -> list[str]:
        indices = self.columns_listbox.curselection()
        return [self.columns_listbox.get(index) for index in indices]

    def preview_data(self) -> None:
        if self.repo is None:
            messagebox.showerror("Connection Required", "Connect to the database first.")
            return

        table_name = self.table_var.get().strip()
        selected_columns = self._selected_columns()
        try:
            max_rows = int(self.max_rows_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Max rows must be a positive integer.")
            return

        def task() -> pd.DataFrame:
            assert self.repo is not None
            dataframe = self.repo.fetch_preview(table_name, selected_columns, max_rows)
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
        if self.preview_df.empty:
            messagebox.showerror(
                "Preview Required",
                "Preview data before exporting and running the GAMS model.",
            )
            return

        def task() -> Path:
            save_preview_csv(self.preview_df, DATA_DIR)
            long_csv = save_long_csv(self.preview_df, DATA_DIR)
            model_path = GAMS_DIR / "model.gms"
            run_gams_model(PROJECT_ROOT, model_path)
            return long_csv

        def on_success(long_csv: Path) -> None:
            self.status_var.set(
                f"Exported long-format data to {long_csv} and ran GAMS successfully."
            )
            messagebox.showinfo(
                "Export and Run Complete",
                "Data exported successfully and GAMS completed without errors.",
            )

        self._run_in_background(
            task,
            on_success,
            "Exporting numeric data and running GAMS...",
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
                self.root.after(
                    0,
                    lambda: (
                        self.status_var.set("Export validation failed."),
                        messagebox.showerror("Export Error", str(exc)),
                    ),
                )
            except GAMSRunError as exc:
                self.logger.error("GAMS run failed: %s", exc)
                self.root.after(
                    0,
                    lambda: (
                        self.status_var.set("GAMS execution failed."),
                        messagebox.showerror("GAMS Error", str(exc)),
                    ),
                )
            except Exception as exc:
                self.logger.error("Unexpected error: %s\n%s", exc, traceback.format_exc())
                self.root.after(
                    0,
                    lambda: (
                        self.status_var.set("An unexpected error occurred."),
                        messagebox.showerror("Application Error", str(exc)),
                    ),
                )
            else:
                self.root.after(0, lambda: on_success(result))

        threading.Thread(target=worker, daemon=True).start()


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
