import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def run_history_path() -> Path:
    return FIXTURES / "sample-run-history.csv"


@pytest.fixture
def synth_manifests_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def job_feed_db_path(tmp_path_factory) -> Path:
    db_path = tmp_path_factory.mktemp("data") / "job-feed.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE job_postings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_role_id TEXT NOT NULL,
            url TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            salary_disclosed TEXT,
            posted_at TEXT,
            first_seen_at TEXT NOT NULL,
            description_excerpt TEXT,
            rules_passed INTEGER NOT NULL,
            rules_rejection_reason TEXT,
            fit_score INTEGER,
            role_band TEXT,
            rationale TEXT,
            concerns TEXT,
            fit_dimensions TEXT,
            scored_at TEXT,
            status TEXT DEFAULT 'new',
            UNIQUE(source, source_role_id)
        );
    """)
    conn.executemany(
        """INSERT INTO job_postings
           (source, source_role_id, url, company, title, first_seen_at,
            rules_passed, fit_score, role_band, status)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
        [
            # (source, source_role_id, url, company, title, first_seen_at,
            #  rules_passed, fit_score, role_band, status)
            ("greenhouse", "anthropic-fde", "https://x", "Anthropic", "FDE",
             "2026-05-12T10:00:00Z", 88, "ai-pm", "screen-scheduled"),
            ("greenhouse", "klaviyo-pm", "https://y", "Klaviyo", "Senior PM",
             "2026-05-13T10:00:00Z", 72, "tech-pm", "applied"),
            ("ats-watch", "sierra-1", "https://z", "Sierra", "Agent PM",
             "2026-05-14T10:00:00Z", 91, "ai-pm", "new"),
            ("ats-watch", "decagon-1", "https://w", "Decagon", "Agent PM",
             "2026-05-14T11:00:00Z", 84, "ai-pm", "rejected"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path
