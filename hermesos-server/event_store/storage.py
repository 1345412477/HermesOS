"""Event Store backed by SQLite.

Stores and queries device events with flexible filtering.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from ..models.schemas import EventSummary
except ImportError:
    from models.schemas import EventSummary  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    device_id   TEXT NOT NULL,
    device_type TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT 'unknown',
    event_type  TEXT NOT NULL,
    result      TEXT DEFAULT NULL,
    source      TEXT NOT NULL DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_device_id ON events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
"""


class EventStore:
    """Persistent event store using a local SQLite database."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "events.db")
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(DB_SCHEMA)
        self._conn.commit()
        logger.info("Event store initialised at %s", self._db_path)

    # ── public API ────────────────────────────────────────────

    def store_event(self, event: EventSummary) -> None:
        """Persist a single event."""
        self._conn.execute(
            """INSERT OR REPLACE INTO events
               (event_id, timestamp, device_id, device_type, location,
                event_type, result, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id or str(uuid.uuid4()),
                event.timestamp.isoformat(),
                event.device_id,
                event.device_type,
                event.location,
                event.event_type,
                json.dumps(event.result, ensure_ascii=False) if event.result else None,
                event.source,
            ),
        )
        self._conn.commit()

    def query_events(
        self,
        time_range: Optional[tuple[datetime, datetime]] = None,
        device_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[EventSummary]:
        """Query events with optional filters."""
        conditions: list[str] = []
        params: list = []

        if time_range:
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.extend([time_range[0].isoformat(), time_range[1].isoformat()])
        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM events{where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_recent(self, limit: int = 50) -> list[EventSummary]:
        """Return the most recent events."""
        cursor = self._conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventSummary:
        result_raw = row["result"]
        return EventSummary(
            event_id=row["event_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            device_id=row["device_id"],
            device_type=row["device_type"],
            location=row["location"],
            event_type=row["event_type"],
            result=json.loads(result_raw) if result_raw else None,
            source=row["source"],
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
