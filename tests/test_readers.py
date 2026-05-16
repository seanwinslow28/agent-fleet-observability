from datetime import date, datetime

from lib import readers

from .conftest import FIXTURES


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


def test_read_gemini_spend_returns_month_total(tmp_path):
    src = FIXTURES / "sample-gemini-spend.json"
    out = readers.read_gemini_spend(src)
    assert out["total_usd"] == 8.20
    assert out["run_count"] == 2
    assert out["tiers"] == {"dr": 1, "max": 1}


def test_read_gemini_spend_empty_when_missing(tmp_path):
    out = readers.read_gemini_spend(tmp_path / "nope.json")
    assert out == {"total_usd": 0.0, "run_count": 0, "tiers": {}}


def test_read_council_spend_aggregates_files(tmp_path):
    # symlink the fixture into a tmp dir to test glob behavior
    (tmp_path / "council-spend-2026-05-14.json").write_text(
        (FIXTURES / "sample-council-spend-2026-05-14.json").read_text()
    )
    out = readers.read_council_spend(tmp_path)
    assert out["month_total_usd"] == 0.41
    assert out["day_count"] == 1


def test_read_council_spend_empty_dir(tmp_path):
    out = readers.read_council_spend(tmp_path / "missing")
    assert out["month_total_usd"] == 0.0
