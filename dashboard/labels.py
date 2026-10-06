"""Sean's label and decision, written back into the ticket file (#8 §7, #23 Amendments 2 and 3).

Each attempt gets one entry in the ticket's `verdicts:` list. Saving the label
writes the four label fields; the decision then adds `verdict:` and moves the
file where it belongs:

- accept: `verdict: pass`, moved to queue/done/
- send back: `verdict: fail` with the note, `status: draft`, left in queue/
- drop: `verdict: fail`, `dropped: true`, moved to queue/done/
- a calibration attempt's label is its whole decision; the ticket is already closed.

On the Mini, autosave commits queue/, so these writes need no commit here.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
from pathlib import Path

import yaml

from dashboard.cards import NotACard, card, label_for, split_doc, ticket_path

_lock = threading.Lock()


class ReviewError(ValueError):
    """Something Sean needs to fix before the write can happen, in plain words."""


def save_label(brain: Path, ticket_id: str, attempt: int, answers: dict, *, critique: str | None,
               judge_seen_first: bool, seconds: int | None) -> dict:
    brain = Path(brain)
    with _lock:
        c, path, meta, body = _open(brain, ticket_id, attempt)
        if c["label"]:
            raise ReviewError("This card's label is already saved.")
        entry = {"attempt": attempt, "lane": c["lane"], "read": True}
        for q in c["questions"]:
            value = answers.get(q["field"])
            if q["field"] == "lane_agree":
                if not isinstance(value, bool):
                    raise ReviewError("Answer lane_agree first: does it belong in this lane?")
            elif value not in ("pass", "fail"):
                raise ReviewError(f"Answer {q['field']} first.")
            entry[q["field"]] = value
        critique = (critique or "").strip()
        if (entry["lane_agree"] is False or "fail" in entry.values()) and not critique:
            raise ReviewError("Write one sentence on what's wrong first.")
        entry["judge_seen_first"] = bool(judge_seen_first)
        if critique:
            entry["note"] = critique
        if isinstance(seconds, int) and seconds >= 0:
            entry["seconds"] = seconds
        if c["calibration"]:
            entry["calibration"] = True
            entry["verdict"] = "fail" if entry.get("deliverable", "pass") == "fail" or not entry["lane_agree"] \
                else "pass"
        entry["at"] = _now()
        meta.setdefault("verdicts", [])
        if not isinstance(meta["verdicts"], list):
            raise ReviewError(f"{path.name} has a `verdicts:` field that isn't a list; fix it by hand.")
        meta["verdicts"].append(entry)
        _write(path, meta, body)
        return entry


def act(brain: Path, ticket_id: str, attempt: int, action: str, *, note: str | None = None) -> dict:
    brain = Path(brain)
    with _lock:
        c, path, meta, body = _open(brain, ticket_id, attempt)
        label = label_for(meta, attempt)
        if not label:
            raise ReviewError("Save the label first.")
        if action == "accept":
            if c["lane"] == "Blocked":
                raise ReviewError("Blocked work can't be accepted. Send it back or drop it.")
            if label.get("deliverable") == "fail":
                raise ReviewError("You said not to keep the brief. Send it back or drop it.")
            label["verdict"] = "pass"
            target = brain / "queue" / "done" / path.name
        elif action == "send_back":
            note = (note or "").strip()
            if not note:
                raise ReviewError("Write a note for the rerun first.")
            label.update(verdict="fail", note=note)
            meta["status"] = "draft"
            target = path
        elif action == "drop":
            label.update(verdict="fail", dropped=True)
            target = brain / "queue" / "done" / path.name
        else:
            raise ReviewError(f"There's no action called {action!r}.")
        label["decided_at"] = _now()
        _write(target, meta, body)
        if target != path:
            path.unlink()
        return label


def _open(brain: Path, ticket_id: str, attempt: int) -> tuple[dict, Path, dict, str]:
    try:
        c = card(brain, ticket_id)
    except NotACard as exc:
        raise ReviewError(f"That card isn't waiting for review any more ({exc}).") from exc
    if attempt != c["attempt"]:
        raise ReviewError(f"Attempt {attempt} isn't the one waiting for review; attempt {c['attempt']} is.")
    path = ticket_path(brain, ticket_id)
    meta, body = split_doc(path.read_text(encoding="utf-8"))
    return c, path, meta, body


def _write(path: Path, meta: dict, body: str) -> None:
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000) + "---\n" + body
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.writing-{os.getpid()}")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")
