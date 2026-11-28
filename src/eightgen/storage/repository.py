"""Repository pattern for Game persistence in SQLite and filesystem."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from eightgen.storage.database import Database
from eightgen.storage.models import Game, GameVersion
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.storage")

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards so a tag is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class GameRepository:
    """Handles saving, retrieving, and updating games in SQLite & filesystem."""

    def __init__(self, db: Database, output_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, game: Game) -> Game:
        """Insert or update a game and its versions."""
        with self.db.get_connection() as conn:
            tags_json = json.dumps(game.tags)
            conn.execute(
                """
                INSERT INTO games (id, title, slug, description, category, tags, current_version, file_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    slug = excluded.slug,
                    description = excluded.description,
                    category = excluded.category,
                    tags = excluded.tags,
                    current_version = excluded.current_version,
                    file_path = excluded.file_path,
                    updated_at = excluded.updated_at
                """,
                (
                    game.id,
                    game.title,
                    game.slug,
                    game.description,
                    game.category,
                    tags_json,
                    game.current_version,
                    str(game.file_path),
                    game.created_at.isoformat(),
                    game.updated_at.isoformat(),
                ),
            )

            # Save versions
            for ver in game.versions:
                conn.execute(
                    """
                    INSERT INTO game_versions (game_id, version, prompt, html_content, model, change_summary, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id, version) DO UPDATE SET
                        prompt = excluded.prompt,
                        html_content = excluded.html_content,
                        model = excluded.model,
                        change_summary = excluded.change_summary
                    """,
                    (
                        game.id,
                        ver.version,
                        ver.prompt,
                        ver.html_content,
                        ver.model,
                        ver.change_summary,
                        ver.created_at.isoformat(),
                    ),
                )
            conn.commit()

        # Write latest HTML to file
        if game.versions:
            game.file_path.parent.mkdir(parents=True, exist_ok=True)
            game.file_path.write_text(game.latest_html, encoding="utf-8")

        return game

    def get_by_id(self, game_id: str) -> Optional[Game]:
        """Fetch game by exact ID, or by an unambiguous prefix."""
        if not game_id or not _ID_RE.match(game_id):
            return None
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            if row is None:
                rows = conn.execute(
                    "SELECT * FROM games WHERE id LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT 2",
                    (f"{_escape_like(game_id)}%",),
                ).fetchall()
                if len(rows) != 1:
                    return None
                row = rows[0]
            return self._build_game(conn, row)

    def get_by_slug(self, slug: str) -> Optional[Game]:
        """Fetch game by slug."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM games WHERE slug = ? LIMIT 1", (slug,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_game(conn, row)

    def get_latest(self) -> Optional[Game]:
        """Fetch the most recently updated game."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM games ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_game(conn, row)

    def list_all(self, limit: int = 50, tag: Optional[str] = None) -> List[Game]:
        """List games ordered by most recent update."""
        games: List[Game] = []
        with self.db.get_connection() as conn:
            if tag:
                cursor = conn.execute(
                    "SELECT * FROM games WHERE tags LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT ?",
                    (f"%{_escape_like(tag)}%", limit),
                )
            else:
                cursor = conn.execute("SELECT * FROM games ORDER BY updated_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            for row in rows:
                games.append(self._build_game(conn, row))
        return games

    def list_summaries(self, limit: int = 50, tag: Optional[str] = None) -> List[dict]:
        """List lightweight metadata without loading every version's HTML.

        The gallery only needs titles, badges, and timestamps. Loading full
        ``html_content`` for every version makes the list response grow without
        bound and causes an N+1 query per game.
        """
        limit = max(1, min(int(limit), 200))
        params: List[object] = []
        where = ""
        if tag:
            where = "WHERE g.tags LIKE ? ESCAPE '\\'"
            params.append(f"%{_escape_like(tag)}%")
        params.append(limit)
        query = f"""
            SELECT g.id, g.title, g.slug, g.description, g.category, g.tags,
                   g.current_version, g.created_at, g.updated_at,
                   COUNT(v.id) AS version_count
            FROM games g
            LEFT JOIN game_versions v ON v.game_id = g.id
            {where}
            GROUP BY g.id
            ORDER BY g.updated_at DESC
            LIMIT ?
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        summaries: List[dict] = []
        for row in rows:
            try:
                tags = json.loads(row["tags"]) if row["tags"] else []
            except Exception:
                tags = [t.strip() for t in (row["tags"] or "").split(",") if t.strip()]
            summaries.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "slug": row["slug"],
                    "description": row["description"] or "",
                    "category": row["category"] or "arcade",
                    "tags": tags,
                    "current_version": row["current_version"],
                    "version_count": row["version_count"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return summaries

    def delete(self, game_id: str) -> bool:
        """Delete game from database and remove HTML file."""
        game = self.get_by_id(game_id)
        if not game:
            return False
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM games WHERE id = ?", (game.id,))
            conn.commit()
        if game.file_path.exists():
            try:
                game.file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove file {game.file_path}: {e}")
        return True

    def add_version(self, game_id: str, version: GameVersion) -> Optional[Game]:
        """Append one version without re-upserting the entire history."""
        game = self.get_by_id(game_id)
        if not game:
            return None
        next_version = game.current_version + 1
        version.version = next_version
        updated_at = datetime.now(timezone.utc)
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO game_versions
                    (game_id, version, prompt, html_content, model, change_summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game.id,
                    next_version,
                    version.prompt,
                    version.html_content,
                    version.model,
                    version.change_summary,
                    version.created_at.isoformat(),
                ),
            )
            conn.execute(
                "UPDATE games SET current_version = ?, updated_at = ? WHERE id = ?",
                (next_version, updated_at.isoformat(), game.id),
            )
            conn.commit()

        game.file_path.parent.mkdir(parents=True, exist_ok=True)
        game.file_path.write_text(version.html_content, encoding="utf-8")
        return self.get_by_id(game.id)

    def _build_game(self, conn, row) -> Game:
        """Helper to construct Game model with versions."""
        v_cursor = conn.execute(
            "SELECT * FROM game_versions WHERE game_id = ? ORDER BY version ASC",
            (row["id"],),
        )
        version_rows = v_cursor.fetchall()
        versions = [
            GameVersion(
                version=v["version"],
                prompt=v["prompt"],
                html_content=v["html_content"],
                model=v["model"],
                change_summary=v["change_summary"],
                created_at=datetime.fromisoformat(v["created_at"]),
            )
            for v in version_rows
        ]

        tags = []
        if row["tags"]:
            try:
                tags = json.loads(row["tags"])
            except Exception:
                tags = [t.strip() for t in row["tags"].split(",") if t.strip()]

        return Game(
            id=row["id"],
            title=row["title"],
            slug=row["slug"],
            description=row["description"] or "",
            category=row["category"] or "arcade",
            tags=tags,
            current_version=row["current_version"],
            file_path=Path(row["file_path"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            versions=versions,
        )
