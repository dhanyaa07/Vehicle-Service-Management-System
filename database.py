"""Database connection and lightweight transaction helpers.

SQLite is the default so the desktop app runs without a database server. Set
DB_BACKEND=mysql to use the MySQL schema supplied with this project.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


PROJECT_DIR = Path(__file__).resolve().parent


@dataclass
class ExecutionResult:
    lastrowid: int | None
    rowcount: int


class Session:
    """A cursor-safe session used inside one committed/rolled-back transaction."""

    def __init__(self, connection: Any, backend: str):
        self.connection = connection
        self.backend = backend

    def _cursor(self):
        if self.backend == "mysql":
            return self.connection.cursor(dictionary=True)
        return self.connection.cursor()

    def _sql(self, sql: str) -> str:
        # All application SQL uses qmark placeholders; mysql-connector uses %s.
        return sql.replace("?", "%s") if self.backend == "mysql" else sql

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        cursor = self._cursor()
        try:
            cursor.execute(self._sql(sql), tuple(params))
            rows = cursor.fetchall()
            if self.backend == "mysql":
                return [dict(row) for row in rows]
            return [dict(row) for row in rows]
        finally:
            cursor.close()

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple | list = ()) -> ExecutionResult:
        cursor = self._cursor()
        try:
            cursor.execute(self._sql(sql), tuple(params))
            return ExecutionResult(
                lastrowid=getattr(cursor, "lastrowid", None),
                rowcount=getattr(cursor, "rowcount", 0),
            )
        finally:
            cursor.close()


class Database:
    def __init__(
        self,
        backend: str = "sqlite",
        sqlite_path: str | Path | None = None,
        mysql_config: dict[str, Any] | None = None,
    ):
        backend = backend.strip().lower()
        if backend not in {"sqlite", "mysql"}:
            raise ValueError("DB_BACKEND must be either 'sqlite' or 'mysql'.")
        self.backend = backend
        self.sqlite_path = Path(sqlite_path or PROJECT_DIR / "data" / "vehicle_service.db")
        self.mysql_config = mysql_config or {}

    @classmethod
    def from_env(cls) -> "Database":
        backend = os.getenv("DB_BACKEND", "sqlite").strip().lower()
        sqlite_path = os.getenv("DB_PATH", str(PROJECT_DIR / "data" / "vehicle_service.db"))
        path = Path(sqlite_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_DIR / path
        config = {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "vehicle_service_db"),
            "connection_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8")),
        }
        return cls(backend=backend, sqlite_path=path, mysql_config=config)

    def _connect(self):
        if self.backend == "sqlite":
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.sqlite_path), timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 30000")
            return connection

        try:
            import mysql.connector  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "MySQL mode needs mysql-connector-python. Install it with: "
                "python -m pip install -r requirements.txt"
            ) from exc
        try:
            return mysql.connector.connect(**self.mysql_config, autocommit=False)
        except Exception as exc:
            raise RuntimeError(
                "Could not connect to MySQL. Check DB_HOST, DB_PORT, DB_NAME, "
                "DB_USER and DB_PASSWORD, and create the database before launching. "
                f"Details: {exc}"
            ) from exc

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        connection = self._connect()
        try:
            yield Session(connection, self.backend)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self.transaction() as session:
            return session.query(sql, params)

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        with self.transaction() as session:
            return session.one(sql, params)

    def execute(self, sql: str, params: tuple | list = ()) -> ExecutionResult:
        with self.transaction() as session:
            return session.execute(sql, params)

    def initialize(self) -> None:
        if self.backend == "sqlite":
            schema_path = PROJECT_DIR / "schema_sqlite.sql"
            script = schema_path.read_text(encoding="utf-8")
            connection = self._connect()
            try:
                connection.executescript(script)
                connection.commit()
            finally:
                connection.close()
            return

        schema_path = PROJECT_DIR / "schema_mysql.sql"
        self._execute_mysql_script(schema_path.read_text(encoding="utf-8"))

    def _execute_mysql_script(self, script: str) -> None:
        """Execute a MySQL script with DELIMITER-aware trigger parsing."""
        connection = self._connect()
        delimiter = ";"
        buffer: list[str] = []
        try:
            cursor = connection.cursor()
            for line in script.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("--"):
                    continue
                if stripped.upper().startswith("DELIMITER "):
                    delimiter = stripped.split(None, 1)[1]
                    continue
                buffer.append(line)
                statement_buffer = "\n".join(buffer).rstrip()
                if statement_buffer.endswith(delimiter):
                    statement = statement_buffer[: -len(delimiter)].strip()
                    buffer = []
                    if statement:
                        cursor.execute(statement)
                        connection.commit()
            if "\n".join(buffer).strip():
                raise RuntimeError("The MySQL schema script ended with an incomplete statement.")
        except Exception:
            connection.rollback()
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            connection.close()

    def health(self) -> str:
        if self.backend == "sqlite":
            return f"SQLite · {self.sqlite_path.name}"
        cfg = self.mysql_config
        return f"MySQL · {cfg.get('host')} / {cfg.get('database')}"
