import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "recovery.db"

def get_db_connection():
    """Establish a connection to the SQLite database and enable WAL mode."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """Initialize database tables for storing diagnoses and workflows."""
    with get_db_connection() as conn:
        # Create diagnoses table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS diagnoses (
                id TEXT PRIMARY KEY,
                method TEXT,
                url TEXT,
                status INTEGER,
                response TEXT,
                problem TEXT,
                category TEXT,
                retry BOOLEAN,
                fix TEXT,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create workflows table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                goal TEXT,
                history TEXT, -- stored as JSON stringified list
                next_step TEXT,
                reason TEXT,
                retry BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_diagnosis(diag_id: str, method: str, url: str, status: int, response: str, 
                   problem: str, category: str, retry: bool, fix: str, confidence: float):
    """Save a diagnosed failure case into SQLite."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO diagnoses (
                id, method, url, status, response, problem, category, retry, fix, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (diag_id, method, url, status, response, problem, category, int(retry), fix, confidence))
        conn.commit()

def get_diagnosis(diag_id: str):
    """Retrieve a saved diagnosis by ID."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM diagnoses WHERE id = ?", (diag_id,)).fetchone()
        if row:
            return dict(row)
        return None

def save_workflow(wf_id: str, goal: str, history: list, next_step: str, reason: str, retry: bool):
    """Save a workflow recovery context."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO workflows (
                id, goal, history, next_step, reason, retry
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (wf_id, goal, json.dumps(history), next_step, reason, int(retry)))
        conn.commit()

def get_workflow(wf_id: str):
    """Retrieve a saved workflow state by ID."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
        if row:
            d = dict(row)
            d["history"] = json.loads(d["history"])
            return d
        return None
