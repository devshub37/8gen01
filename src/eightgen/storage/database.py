"""SQLite schema and connection helper."""

import sqlite3
import threading
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'arcade',
    tags TEXT,
    current_version INTEGER DEFAULT 1,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    html_content TEXT NOT NULL,
    model TEXT NOT NULL,
    change_summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    UNIQUE (game_id, version)
);

CREATE INDEX IF NOT EXISTS idx_games_updated ON games(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_game_versions_game_id ON game_versions(game_id);
"""


class Database:
    """Manages SQLite database connections and table creation."""

    _initialized_paths: set[str] = set()
    _init_lock = threading.Lock()

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables once per database file for this process."""
        key = str(self.db_path.resolve())
        with self._init_lock:
            if key in self._initialized_paths and self.db_path.exists():
                return
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_SQL)
                conn.commit()
            self._initialized_paths.add(key)

    def init_db(self) -> None:
        """Public compatibility wrapper for explicit schema creation."""
        self._init_schema()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a tuned SQLite connection.

        WAL + a busy timeout let generation, refinement, and dashboard reads
        overlap without immediately raising ``database is locked``.
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            yield conn
        finally:
            conn.close()
