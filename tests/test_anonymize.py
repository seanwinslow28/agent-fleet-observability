import copy
from datetime import UTC, datetime

from lib import anonymize


def _agg():
    return {
        "fleet_status": [
            {"agent": "vault_synthesizer", "last_notes": "vault/.job-feed.db hit cap"},
        ],
        "kpis": {"fleet_spend_30d_usd": 8.40, "fleet_spend_30d_label": "$8.40"},
        "recent_runs": [
            {"ts": datetime(2026, 5, 13, 12, tzinfo=UTC),
             "agent": "deep_researcher", "status": "ok", "cost_usd": 0.0,
             "notes": "vault/20_projects/research/2026-05-13-foo.md updated"},
        ],
        "job_feed": {"total_postings": 4, "by_status": {"new": 1}, "top_fit": [{"company": "X"}]},
        "research_queue": {"pending": [
            {"title": "Anthropic interview prep — vault/20_projects/prj-job-hunt-2026/notes.md",
             "assigned_agent": None},
        ]},
        "manual_tickets": {"todo": [], "in_progress": [], "done": []},
        "target_companies": {
            "tier_1": [{"id": 1, "company": "Anthropic", "status": "applied"}],
            "tier_2": [{"id": 4, "company": "Scale AI", "status": "not-applied"}],
            "tier_3": [],
            "by_status": {"applied": 1, "not-applied": 1},
            "total": 2,
        },
        "warm_intros": {
            "active": [{"person": "Larry", "target_company": "Messari"}],
            "prospecting": [],
            "second_degree": [],
            "total": 1,
        },
    }


def test_public_pass_strips_job_feed_db_content():
    pub = anonymize.public_pass(_agg())
    assert pub["job_feed"] == {
        "total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0
    }


def test_public_pass_strips_target_companies():
    pub = anonymize.public_pass(_agg())
    assert pub["target_companies"] == {
        "tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0
    }


def test_public_pass_strips_warm_intros():
    pub = anonymize.public_pass(_agg())
    assert pub["warm_intros"] == {"active": [], "prospecting": [], "second_degree": [], "total": 0}


def test_public_pass_redacts_vault_paths_in_notes():
    pub = anonymize.public_pass(_agg())
    assert "vault/" not in pub["fleet_status"][0]["last_notes"]
    assert "[redacted]" in pub["fleet_status"][0]["last_notes"]
    assert "vault/" not in pub["recent_runs"][0]["notes"]


def test_public_pass_redacts_vault_paths_in_ticket_titles():
    pub = anonymize.public_pass(_agg())
    title = pub["research_queue"]["pending"][0]["title"]
    assert "vault/" not in title


def test_public_pass_preserves_dollar_amounts():
    pub = anonymize.public_pass(_agg())
    assert pub["kpis"]["fleet_spend_30d_label"] == "$8.40"
    assert pub["kpis"]["fleet_spend_30d_usd"] == 8.40


def test_public_pass_does_not_mutate_input():
    src = _agg()
    snapshot = copy.deepcopy(src)
    anonymize.public_pass(src)
    assert src == snapshot
