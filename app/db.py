"""Database access layer for MySQL metadata and data preview queries."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_$]+$")


def quote_mysql_identifier(identifier: str) -> str:
    """Safely quote a MySQL identifier after a conservative validation check."""
    if not IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(f"Unsafe MySQL identifier: {identifier!r}")
    return f"`{identifier.replace('`', '``')}`"


def validate_where_clause(where_clause: str) -> str:
    """Perform a conservative validation for a simple user-supplied SQL filter."""
    normalized = where_clause.strip()
    if not normalized:
        return ""

    forbidden_tokens = (";", "--", "/*", "*/", "\\")
    if any(token in normalized for token in forbidden_tokens):
        raise ValueError(
            "The WHERE/filter text contains unsupported SQL control characters. "
            "Use a simple filter expression only, without semicolons or comments."
        )

    return normalized


@dataclass(slots=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


class MySQLRepository:
    """Encapsulates metadata and table preview queries."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            connection_url = (
                f"mysql+pymysql://{self.config.user}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/{self.config.database}"
            )
            self._engine = create_engine(connection_url, future=True, pool_pre_ping=True)
        return self._engine

    def test_connection(self) -> None:
        """Raise an exception if the database cannot be reached."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def list_tables(self) -> list[str]:
        """Return base table names for the configured schema."""
        query = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :database_name
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                query, {"database_name": self.config.database}
            ).scalars()
            return list(rows)

    def list_columns(self, table_name: str) -> list[str]:
        """Return column names for the selected table."""
        query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :database_name
              AND table_name = :table_name
            ORDER BY ordinal_position
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                query,
                {"database_name": self.config.database, "table_name": table_name},
            ).scalars()
            return list(rows)

    def fetch_preview(
        self,
        table_name: str,
        selected_columns: list[str],
        max_rows: int,
        where_clause: str = "",
    ) -> pd.DataFrame:
        """Fetch a limited preview from the selected table."""
        if max_rows <= 0:
            raise ValueError("Maximum rows must be a positive integer.")
        if not selected_columns:
            raise ValueError("At least one column must be selected.")

        available_columns = set(self.list_columns(table_name))
        unknown_columns = [col for col in selected_columns if col not in available_columns]
        if unknown_columns:
            raise ValueError(
                "Selected columns are not present in the table: "
                + ", ".join(unknown_columns)
            )

        quoted_table = quote_mysql_identifier(table_name)
        quoted_columns = ", ".join(
            quote_mysql_identifier(column_name) for column_name in selected_columns
        )
        validated_where = validate_where_clause(where_clause)
        where_sql = f" WHERE {validated_where}" if validated_where else ""
        sql = text(
            f"SELECT {quoted_columns} FROM {quoted_table}{where_sql} LIMIT :max_rows"
        )
        return pd.read_sql_query(sql, self.engine, params={"max_rows": int(max_rows)})

    def dispose(self) -> None:
        """Dispose the SQLAlchemy engine if it exists."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
