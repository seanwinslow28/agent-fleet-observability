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


def test_read_eval_last_run_extracts_counts():
    out = readers.read_eval_last_run(FIXTURES / "sample-eval-last-run.md")
    assert out["passed"] == 7
    assert out["total_cases"] == 10
    assert len(out["cases"]) == 10
    failed = [c for c in out["cases"] if c["status"] == "failed"]
    assert len(failed) == 2


def test_read_eval_last_run_missing_file(tmp_path):
    out = readers.read_eval_last_run(tmp_path / "no.md")
    assert out["passed"] == 0
    assert out["cases"] == []


def test_read_lint_reports_returns_latest(tmp_path):
    fixture = (FIXTURES / "sample-lint-report.md").read_text()
    (tmp_path / "2026-05-12-lint-report.md").write_text(fixture)
    (tmp_path / "2026-05-19-lint-report.md").write_text(fixture)
    out = readers.read_lint_reports(tmp_path)
    assert out["latest_date"] == "2026-05-19"
    assert out["issues_total"] == 4
    # New: parsed issues list with structured fields
    assert len(out["issues"]) == 4
    by_sev = {iss["severity"]: iss for iss in out["issues"]}
    assert by_sev["CRITICAL"]["rule"] == "contradiction"
    assert by_sev["CRITICAL"]["tier"] == "T2"
    assert by_sev["HIGH"]["rule"] == "broken-wikilink"
    assert by_sev["HIGH"]["path"] == "knowledge/connections/baz.md"
    assert by_sev["MEDIUM"]["context"] == "old format"


def test_read_job_feed_db_returns_funnel(job_feed_db_path):
    out = readers.read_job_feed_db(job_feed_db_path)
    assert out["total_postings"] == 4
    assert out["by_status"]["new"] == 1
    assert out["by_status"]["applied"] == 1
    assert out["by_status"]["screen-scheduled"] == 1
    assert out["by_status"]["rejected"] == 1
    assert out["top_fit"][0]["company"] == "Sierra"


def test_read_job_feed_db_missing(tmp_path):
    out = readers.read_job_feed_db(tmp_path / "missing.db")
    assert out["total_postings"] == 0


def test_read_research_queue_parses_sections():
    out = readers.read_research_queue(FIXTURES / "sample-research-queue.md")
    assert len(out["pending"]) == 3
    assert len(out["in_flight"]) == 1
    assert out["in_flight"][0]["assigned_agent"] == "deep_researcher"


def test_read_research_queue_excludes_done_items_from_pending():
    """Items checked with [x] must not appear under pending, even when
    they live under a stale ## Pending heading."""
    out = readers.read_research_queue(FIXTURES / "sample-research-queue.md")
    titles_pending = [item["title"] for item in out["pending"]]
    assert not any("Old completed topic" in t for t in titles_pending)


def test_read_manual_tickets_parses():
    out = readers.read_manual_tickets(FIXTURES / "sample-tickets.md")
    assert len(out["todo"]) == 2
    assert len(out["in_progress"]) == 1
    sean_ticket = [t for t in out["todo"] if t["assigned_agent"] == "Sean"][0]
    assert "Rotate" in sean_ticket["title"]


def test_read_job_feed_manifests(tmp_path):
    src = FIXTURES / "sample-job-feed-manifest-2026-05-13.json"
    (tmp_path / src.name.replace("sample-", "")).write_text(src.read_text())
    out = readers.read_job_feed_manifests(tmp_path)
    assert out["latest"]["new_postings"] == 14
    assert out["latest"]["date"] == "2026-05-13"


def test_read_target_companies_parses_three_tiers():
    out = readers.read_target_companies(FIXTURES / "sample-target-companies.md")
    assert out["total"] == 6
    assert len(out["tier_1"]) == 3
    assert len(out["tier_2"]) == 2
    assert len(out["tier_3"]) == 1
    # First Tier-1 row — strips markdown bold from company
    anthropic = out["tier_1"][0]
    assert anthropic["company"] == "Anthropic"
    assert anthropic["role"] == "Forward Deployed Engineer"
    assert anthropic["status"] == "not-applied"
    assert anthropic["id"] == 1


def test_read_target_companies_by_status_aggregates():
    out = readers.read_target_companies(FIXTURES / "sample-target-companies.md")
    # 3 not-applied (Anthropic, Scale AI, Sierra), 1 applied (Glean),
    # 1 talking (Pair Team), 1 rejected (OpenAI) — 6 rows, 6 statuses
    assert out["by_status"]["not-applied"] == 3
    assert out["by_status"]["applied"] == 1
    assert out["by_status"]["talking"] == 1
    assert out["by_status"]["rejected"] == 1


def test_read_target_companies_missing_file(tmp_path):
    out = readers.read_target_companies(tmp_path / "nope.md")
    assert out == {"tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0}


def test_read_warm_intros_parses_active_skips_placeholders():
    out = readers.read_warm_intros(FIXTURES / "sample-warm-intros.md")
    # Active has 2 real rows; prospecting + 2nd-degree have placeholder-only rows
    assert len(out["active"]) == 2
    assert out["active"][0]["person"] == "Larry"
    assert out["active"][0]["strength"] == "strong"
    assert out["active"][0]["target_company"] == "Messari (#29)"
    # Placeholder rows containing "_(to fill...)_" are dropped
    assert len(out["prospecting"]) == 0
    assert len(out["second_degree"]) == 0
    assert out["total"] == 2


def test_read_warm_intros_missing_file(tmp_path):
    out = readers.read_warm_intros(tmp_path / "nope.md")
    assert out == {"active": [], "prospecting": [], "second_degree": [], "total": 0}
