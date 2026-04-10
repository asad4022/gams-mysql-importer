"""Unit tests for conservative database validation helpers."""

from __future__ import annotations

import pytest

from app.db import validate_where_clause


def test_validate_where_clause_accepts_simple_expression() -> None:
    assert validate_where_clause("Anno = 2023 AND profit > 0") == "Anno = 2023 AND profit > 0"


def test_validate_where_clause_rejects_sql_comments_and_statements() -> None:
    with pytest.raises(ValueError):
        validate_where_clause("Anno = 2023; DROP TABLE test")

    with pytest.raises(ValueError):
        validate_where_clause("profit > 0 UNION SELECT * FROM users")
