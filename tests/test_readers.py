from datetime import datetime

from lib import readers


def test_read_run_history_parses_rows(run_history_path):
    rows = readers.read_run_history(run_history_path)
    assert len(rows) == 10
    row = rows[0]
    assert row["agent"] == "vault_synthesizer"
    assert row["status"] == "ok"
    assert row["cost_usd"] == 0.0
    assert row["duration_ms"] == 2719760
    assert isinstance(row["ts"], datetime)


def test_read_run_history_handles_blank_duration(run_history_path):
    rows = readers.read_run_history(run_history_path)
    skipped = [r for r in rows if r["status"] == "skipped"][0]
    assert skipped["duration_ms"] is None


def test_read_run_history_returns_utc_aware_timestamps(run_history_path):
    rows = readers.read_run_history(run_history_path)
    assert rows[0]["ts"].tzinfo is not None
