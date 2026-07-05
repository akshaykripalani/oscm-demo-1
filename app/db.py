"""Tiny local persistence layer (SQLite) so a running simulation survives a
page reload or a server restart. Holds exactly one active simulation at a
time, matching the app's single-session design -- saving overwrites the
prior snapshot."""

import json
import sqlite3
from pathlib import Path

from .models import SimulationConfig

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "simulation.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            config_json TEXT NOT NULL,
            current_week INTEGER NOT NULL,
            stages_json TEXT NOT NULL
        )
        """
    )
    return conn


def save_snapshot(config: SimulationConfig, current_week: int, stages: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO simulation (id, config_json, current_week, stages_json) "
            "VALUES (1, ?, ?, ?)",
            (config.model_dump_json(), current_week, json.dumps(stages)),
        )
        conn.commit()
    finally:
        conn.close()


def load_snapshot() -> tuple[SimulationConfig, int, dict] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT config_json, current_week, stages_json FROM simulation WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    config_json, current_week, stages_json = row
    config = SimulationConfig.model_validate_json(config_json)
    stages = json.loads(stages_json)
    return config, current_week, stages
