"""Writing Sean's label and his decision back into the ticket file."""
import pytest
import yaml

from dashboard.cards import cards
from dashboard.labels import ReviewError, act, save_label

NIGHT = "2026-10-07"
SOURDOUGH = f"{NIGHT}-sourdough-starter-temperature"
HOUSEPLANT = f"{NIGHT}-houseplant-light"
NO_GOAL = f"{NIGHT}-no-goal"
TEA = "2026-10-06-tea-steeping"
YES = {"lane_agree": True, "deliverable": "pass", "judgement": "pass"}


def meta(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n")[1]), text


def ticket(brain, tid, done=False):
    return brain / "queue" / ("done" if done else "") / f"{tid}.md"


def test_an_all_yes_label_saves_the_four_fields(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=95)
    m, _ = meta(ticket(brain, SOURDOUGH))
    (label,) = m["verdicts"]
    assert label["attempt"] == 1 and label["lane"] == "Verified"
    assert label["read"] is True and label["lane_agree"] is True
    assert label["deliverable"] == "pass" and label["judgement"] == "pass"
    assert label["judge_seen_first"] is False and label["seconds"] == 95
    assert "verdict" not in label and label["at"]


def test_the_ticket_body_and_other_fields_survive(brain):
    _, before = meta(ticket(brain, SOURDOUGH))
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    m, after = meta(ticket(brain, SOURDOUGH))
    assert after.split("---\n", 2)[2] == before.split("---\n", 2)[2]
    assert m["status"] == "ready" and m["notes"] == ["notes/baking.md"]


def test_any_no_needs_a_critique(brain):
    with pytest.raises(ReviewError, match="one sentence"):
        save_label(brain, HOUSEPLANT, 1, {**YES, "deliverable": "fail"}, critique=" ", judge_seen_first=False,
                   seconds=1)
    save_label(brain, HOUSEPLANT, 1, {**YES, "deliverable": "fail"}, critique="Claim 2 is made up.",
               judge_seen_first=False, seconds=1)
    m, _ = meta(ticket(brain, HOUSEPLANT))
    assert m["verdicts"][0]["note"] == "Claim 2 is made up."


def test_every_question_on_the_card_must_be_answered(brain):
    with pytest.raises(ReviewError, match="judgement"):
        save_label(brain, SOURDOUGH, 1, {"lane_agree": True, "deliverable": "pass"}, critique=None,
                   judge_seen_first=False, seconds=1)


def test_a_malformed_ticket_needs_only_the_lane(brain):
    save_label(brain, NO_GOAL, 1, {"lane_agree": True}, critique=None, judge_seen_first=False, seconds=1)
    m, _ = meta(ticket(brain, NO_GOAL))
    assert "deliverable" not in m["verdicts"][0]


def test_a_label_is_saved_once(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    with pytest.raises(ReviewError, match="already"):
        save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)


def test_only_the_latest_attempt_can_be_labeled(brain):
    with pytest.raises(ReviewError, match="Attempt 1"):
        save_label(brain, TEA, 1, YES, critique=None, judge_seen_first=False, seconds=1)


def test_a_labeled_card_stays_until_sean_decides(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    (c,) = [c for c in cards(brain) if c["id"] == SOURDOUGH]
    assert c["label"]["lane_agree"] is True


def test_accept_closes_the_ticket_into_done(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    act(brain, SOURDOUGH, 1, "accept")
    assert not ticket(brain, SOURDOUGH).exists()
    m, _ = meta(ticket(brain, SOURDOUGH, done=True))
    assert m["verdicts"][0]["verdict"] == "pass"
    assert SOURDOUGH not in [c["id"] for c in cards(brain)]


def test_a_decision_needs_a_label_first(brain):
    with pytest.raises(ReviewError, match="label"):
        act(brain, SOURDOUGH, 1, "accept")


def test_blocked_work_cannot_be_accepted(brain):
    save_label(brain, HOUSEPLANT, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    with pytest.raises(ReviewError, match="Blocked"):
        act(brain, HOUSEPLANT, 1, "accept")


def test_a_brief_sean_wont_keep_cannot_be_accepted(brain):
    save_label(brain, SOURDOUGH, 1, {**YES, "deliverable": "fail"}, critique="Too thin.", judge_seen_first=False,
               seconds=1)
    with pytest.raises(ReviewError, match="keep"):
        act(brain, SOURDOUGH, 1, "accept")


def test_send_back_leaves_a_draft_in_the_queue_with_the_note(brain):
    save_label(brain, HOUSEPLANT, 1, {**YES, "deliverable": "fail"}, critique="Claim 2 is made up.",
               judge_seen_first=False, seconds=1)
    act(brain, HOUSEPLANT, 1, "send_back", note="Drop the fiddle-leaf claim and rerun.")
    m, _ = meta(ticket(brain, HOUSEPLANT))
    assert m["status"] == "draft"
    assert m["verdicts"][0]["verdict"] == "fail"
    assert m["verdicts"][0]["rerun_note"] == "Drop the fiddle-leaf claim and rerun."
    assert HOUSEPLANT not in [c["id"] for c in cards(brain)]


def test_send_back_needs_a_note(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    with pytest.raises(ReviewError, match="note"):
        act(brain, SOURDOUGH, 1, "send_back", note="")


def test_drop_closes_the_ticket_as_dropped(brain):
    save_label(brain, NO_GOAL, 1, {"lane_agree": True}, critique=None, judge_seen_first=False, seconds=1)
    act(brain, NO_GOAL, 1, "drop")
    m, _ = meta(ticket(brain, NO_GOAL, done=True))
    assert m["verdicts"][0]["verdict"] == "fail" and m["verdicts"][0]["dropped"] is True


def test_a_calibration_label_is_the_whole_decision(brain):
    save_label(brain, TEA, 2, {**YES, "deliverable": "fail", "judgement": "fail"}, critique="Five minutes is wrong.",
               judge_seen_first=False, seconds=1)
    m, _ = meta(ticket(brain, TEA, done=True))
    label = m["verdicts"][1]
    assert label["attempt"] == 2 and label["calibration"] is True and label["verdict"] == "fail"
    assert TEA not in [c["id"] for c in cards(brain)]


def test_a_peek_is_recorded(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=True, seconds=1)
    m, _ = meta(ticket(brain, SOURDOUGH))
    assert m["verdicts"][0]["judge_seen_first"] is True


def test_comments_and_timestamps_in_the_frontmatter_survive(brain):
    path = ticket(brain, SOURDOUGH)
    text = path.read_text().replace("status: ready\n", "status: ready  # Sean's\nlast_edit: 2026-10-06T21:00:00-04:00\n")
    path.write_text(text)
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    after = path.read_text()
    assert "status: ready  # Sean's" in after and "last_edit: 2026-10-06T21:00:00-04:00" in after


def test_a_frontmatter_the_checker_reads_is_read_the_same_way(brain):
    path = ticket(brain, SOURDOUGH)
    text = path.read_text()
    path.write_text("﻿" + text.replace("\n---\n\n#", "\n--- \n\n#", 1))
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    m, _ = meta(path)
    assert m["status"] == "ready" and m["type"] == "research-brief" and len(m["verdicts"]) == 1


def test_a_broken_frontmatter_is_never_rewritten(brain):
    path = ticket(brain, SOURDOUGH)
    broken = path.read_text().replace("status: ready", "status: [ready")
    path.write_text(broken)
    with pytest.raises(ReviewError):
        save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    assert path.read_text() == broken


def test_no_temp_file_is_left_in_the_queue(brain):
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    assert not [p for p in (brain / "queue").iterdir() if p.name.startswith(".")]


def test_send_back_keeps_the_critique_beside_the_rerun_note(brain):
    save_label(brain, HOUSEPLANT, 1, {**YES, "deliverable": "fail"}, critique="Claim 2 is made up.",
               judge_seen_first=False, seconds=1)
    act(brain, HOUSEPLANT, 1, "send_back", note="Rerun without the fig.")
    label = meta(ticket(brain, HOUSEPLANT))[0]["verdicts"][0]
    assert label["note"] == "Claim 2 is made up." and label["rerun_note"] == "Rerun without the fig."


def test_send_back_on_a_closed_ticket_returns_it_to_the_queue(brain):
    ticket(brain, SOURDOUGH).rename(ticket(brain, SOURDOUGH, done=True))
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    act(brain, SOURDOUGH, 1, "send_back", note="Again, please.")
    assert ticket(brain, SOURDOUGH).is_file() and not ticket(brain, SOURDOUGH, done=True).exists()
    assert meta(ticket(brain, SOURDOUGH))[0]["status"] == "draft"


def test_a_peek_is_recorded_in_the_file_before_the_label(brain):
    from dashboard.labels import record_peek
    record_peek(brain, SOURDOUGH, 1)
    assert meta(ticket(brain, SOURDOUGH))[0]["verdicts"][0]["judge_seen_first"] is True
    assert SOURDOUGH in [c["id"] for c in cards(brain)]
    save_label(brain, SOURDOUGH, 1, YES, critique=None, judge_seen_first=False, seconds=1)
    (label,) = meta(ticket(brain, SOURDOUGH))[0]["verdicts"]
    assert label["judge_seen_first"] is True and label["lane_agree"] is True


def test_the_dashboard_waits_for_the_sync_lock(brain):
    import fcntl
    import threading
    lock = brain / ".runtime" / "locks" / "sync.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock, "w")
    fcntl.flock(fd, fcntl.LOCK_EX)
    done = threading.Event()
    t = threading.Thread(target=lambda: (save_label(brain, SOURDOUGH, 1, YES, critique=None,
                                                    judge_seen_first=False, seconds=1), done.set()))
    t.start()
    assert not done.wait(0.5)
    fcntl.flock(fd, fcntl.LOCK_UN)
    assert done.wait(5)
