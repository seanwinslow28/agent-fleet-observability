"""Reading the morning's cards from the brain's files."""
import shutil

from dashboard.cards import card, cards, judge_answer

NIGHT = "2026-10-07"
SOURDOUGH = f"{NIGHT}-sourdough-starter-temperature"
BIKE = f"{NIGHT}-bike-chain-wax"
HOUSEPLANT = f"{NIGHT}-houseplant-light"
NO_GOAL = f"{NIGHT}-no-goal"
TEA = "2026-10-06-tea-steeping"


def ids(brain):
    return [c["id"] for c in cards(brain)]


def test_cards_come_blocked_first_then_unverified_then_verified_oldest_first(brain):
    assert ids(brain) == [HOUSEPLANT, NO_GOAL, TEA, BIKE, SOURDOUGH]


def test_a_ticket_whose_latest_attempt_is_labeled_is_not_a_card(brain):
    assert "2026-10-05-old-question" not in ids(brain)


def test_a_verdict_the_checker_did_not_write_is_ignored(brain):
    shutil.rmtree(brain / ".runtime" / "verdicts" / SOURDOUGH)
    assert SOURDOUGH not in ids(brain)


def test_the_card_leads_with_one_plain_sentence(brain):
    assert card(brain, SOURDOUGH)["headline"] == "Every check passed."
    assert card(brain, HOUSEPLANT)["headline"] == "Quote-match failed: 1 quote isn't on the page it cites."


def test_a_malformed_ticket_says_what_preflight_found(brain):
    assert card(brain, NO_GOAL)["headline"] == ("Preflight found the ticket malformed, so it never ran; "
                                                "the ticket has no goal: write two or three sentences under `## Goal`.")


def test_the_card_carries_the_question_answer_and_one_dot_per_check(brain):
    c = card(brain, SOURDOUGH)
    assert c["title"] == "What temperature keeps a sourdough starter most active?"
    assert c["answer"].startswith("Keep it between 24 and 27 degrees Celsius.")
    assert [k["result"] for k in c["checks"][:-1]] == ["pass"] * (len(c["checks"]) - 1)
    assert c["checks"][-1]["name"] == "judgement"


def test_the_judges_answer_is_never_on_the_card(brain):
    c = card(brain, HOUSEPLANT)
    judgement = c["checks"][-1]
    assert judgement["result"] == "hidden" and "said" not in judgement["summary"]
    assert "result" not in c["judge"] and "critique" not in c["judge"]
    assert c["judge"]["badge"] == "cross-vendor judge, unvalidated; reads agent-written text"


def test_judge_answer_reads_the_verdict_and_critique(brain):
    answer = judge_answer(brain, HOUSEPLANT, 1)
    assert answer["result"] == "fail"
    assert answer["critique"] == "Claim 2 is not supported: the page says the opposite."


def test_evidence_rows_map_each_claim_to_its_source_host(brain):
    rows = card(brain, SOURDOUGH)["evidence"]
    assert [r["status"] for r in rows] == ["found"] * 3
    assert rows[0]["host"] == "bakers-notes.example.org"
    assert "24 and 27 °C" in rows[0]["passage"]


def test_a_missing_quote_shows_brief_says_beside_page_says(brain):
    row = card(brain, HOUSEPLANT)["evidence"][1]
    assert row["status"] == "missing"
    assert row["quote"] == "fiddle-leaf figs need at least six hours of direct sun daily"
    assert "hours of harsh direct sun will scorch" in row["passage"]


def test_an_unconfirmed_citation_says_the_page_did_not_load(brain):
    row = card(brain, BIKE)["evidence"][1]
    assert row["status"] == "unconfirmed" and row["why"] == "the page timed out after 20 seconds"


def test_a_malformed_ticket_asks_only_whether_the_lane_is_right(brain):
    c = card(brain, NO_GOAL)
    assert c["answer"] is None and c["evidence"] == []
    assert [q["field"] for q in c["questions"]] == ["lane_agree"]


def test_a_brief_asks_lane_then_keep_then_the_judgement_sentence_verbatim(brain):
    qs = card(brain, SOURDOUGH)["questions"]
    assert [q["field"] for q in qs] == ["lane_agree", "deliverable", "judgement"]
    assert qs[2]["question"] == "Each claim is supported by the passage quoted for it."


def test_audio_only_when_rendered_and_no_check_failed(brain):
    assert card(brain, SOURDOUGH)["audio"] == {"ready": True, "why": None}
    assert card(brain, BIKE)["audio"] == {"ready": False, "why": "audio not rendered: punctuation check failed"}
    assert card(brain, HOUSEPLANT)["audio"] == {"ready": False, "why": "no audio: a check failed"}


def test_a_calibration_attempt_hides_its_worker(brain):
    c = card(brain, TEA)
    assert c["attempt"] == 2 and c["calibration"] is True
    assert c["details"]["worker"] is None


def test_more_details_carry_spend_drew_on_flags_notes_and_the_agents_summary(brain):
    d = card(brain, BIKE)["details"]
    assert d["worker"] == "researcher on claude-opus-5-5"
    assert "compacted" in d["flags"]
    assert d["summary"] == "I answered the question from five sources."
    assert any("Deny scan" in n for n in d["notes"])
    assert card(brain, SOURDOUGH)["details"]["drew_on"] == ["notes/baking.md"]
    assert card(brain, SOURDOUGH)["spend"] == {"minutes": 4.1, "turns": 31, "usd": 2.1,
                                               "budget": {"minutes": 45, "turns": 80, "usd": 8}}


def test_nothing_on_an_unlabeled_card_says_what_the_judge_answered(brain):
    c = card(brain, TEA)
    assert c["headline"] == "Every command passed; the judge's answer shows once your label is saved."
    assert "said" not in c["questions"][0]["explainer"]


def test_a_judges_fail_alone_doesnt_withhold_the_audio(brain):
    assert card(brain, TEA)["audio"] == {"ready": True, "why": None}


def test_an_unreadable_ticket_is_listed_not_fatal(brain):
    (brain / "queue" / "2026-10-07-bad-bytes.md").write_bytes(b"---\nstatus: draft\n---\n\n# caf\xe9\n")
    from dashboard.cards import review
    data = review(brain)
    assert len(data["cards"]) == 5
    assert [u["file"] for u in data["unreadable"]] == ["queue/2026-10-07-bad-bytes.md"]


def test_a_calibration_attempt_holds_back_the_agents_own_summary(brain):
    assert card(brain, TEA)["details"]["summary"] is None
    assert card(brain, TEA)["details"]["run_log"] is False
