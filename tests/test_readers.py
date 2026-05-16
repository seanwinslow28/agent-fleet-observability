from datetime import date, datetime

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


def test_read_synth_manifests_returns_dated_records(synth_manifests_dir):
    records = readers.read_synth_manifests(synth_manifests_dir)
    assert len(records) == 2
    by_date = {r["date"]: r for r in records}
    assert by_date[date(2026, 5, 13)]["concepts_written"] == 114
    assert by_date[date(2026, 5, 12)]["status"] == "skipped"


def test_read_synth_manifests_sorts_by_date(synth_manifests_dir):
    records = readers.read_synth_manifests(synth_manifests_dir)
    assert records[0]["date"] < records[1]["date"]
