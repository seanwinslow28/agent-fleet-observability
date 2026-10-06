"""Sean's label and decision, written back into the ticket file (#8 §7, #23 Amendments 2 and 3).

Each attempt gets one entry in the ticket's `verdicts:` list. Saving the label
writes the four label fields; the decision then adds `verdict:` and moves the
file where it belongs:

- accept: `verdict: pass`, moved to queue/done/
- send back: `verdict: fail`, the rerun note beside the critique, `status: draft`, in queue/
- drop: `verdict: fail`, `dropped: true`, moved to queue/done/
- a calibration attempt's label is its whole decision; the ticket is already closed.

A peek at the judge before the label is written at once (`judge_seen_first: true`),
so a reload or a switch of device can't lose it.

Every write holds the brain's sync lock, so autosave never commits or stashes a
half-made change, and edits the frontmatter in place: Sean's comments, quoting
and timestamps survive. On the Mini, autosave commits queue/.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import io
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from ruamel.yaml import YAML

from dashboard.cards import NotACard, card, label_for, saved, split_doc, split_text, ticket_path

LOCK_WAIT = 15  # seconds; a sync cycle takes a few
_lock = threading.Lock()


class ReviewError(ValueError):
    """Something Sean needs to fix before the write can happen, in plain words."""


def save_label(brain: Path, ticket_id: str, attempt: int, answers: dict, *, critique: str | None,
               judge_seen_first: bool, seconds: int | None) -> dict:
    with _writing(Path(brain), ticket_id, attempt) as (c, doc):
        entry = doc.entry()
        if saved(entry):
            raise ReviewError("This card's label is already saved.")
        fields = {"attempt": attempt, "lane": c["lane"], "read": True}
        for q in c["questions"]:
            value = answers.get(q["field"])
            if q["field"] == "lane_agree":
                if not isinstance(value, bool):
                    raise ReviewError("Answer lane_agree first: does it belong in this lane?")
            elif value not in ("pass", "fail"):
                raise ReviewError(f"Answer {q['field']} first.")
            fields[q["field"]] = value
        critique = (critique or "").strip()
        if (fields["lane_agree"] is False or "fail" in fields.values()) and not critique:
            raise ReviewError("Write one sentence on what's wrong first.")
        fields["judge_seen_first"] = bool(judge_seen_first or (entry and entry.get("judge_seen_first")))
        if critique:
            fields["note"] = critique
        if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds >= 0:
            fields["seconds"] = seconds
        if c["calibration"]:
            fields["calibration"] = True
            keep = fields.get("deliverable", "pass") == "pass" and fields["lane_agree"]
            fields["verdict"] = "pass" if keep else "fail"
        fields["at"] = _now()
        if entry is None:
            entry = doc.append({})
        for k, v in fields.items():
            entry[k] = v
        doc.save()
        return dict(entry)


def record_peek(brain: Path, ticket_id: str, attempt: int) -> None:
    """Sean looked at the judge before labeling: the row leaves the judge's validation set."""
    with _writing(Path(brain), ticket_id, attempt) as (c, doc):
        entry = doc.entry()
        if saved(entry):
            return
        if entry is None:
            entry = doc.append({"attempt": attempt, "lane": c["lane"]})
        entry["judge_seen_first"] = True
        entry["peeked_at"] = _now()
        doc.save()


def act(brain: Path, ticket_id: str, attempt: int, action: str, *, note: str | None = None) -> dict:
    brain = Path(brain)
    with _writing(brain, ticket_id, attempt) as (c, doc):
        label = doc.entry()
        if not saved(label):
            raise ReviewError("Save the label first.")
        if action == "accept":
            if c["lane"] == "Blocked":
                raise ReviewError("Blocked work can't be accepted. Send it back or drop it.")
            if label.get("deliverable") == "fail":
                raise ReviewError("You said not to keep the brief. Send it back or drop it.")
            label["verdict"] = "pass"
            target = brain / "queue" / "done" / doc.path.name
        elif action == "send_back":
            note = (note or "").strip()
            if not note:
                raise ReviewError("Write a note for the rerun first.")
            label["verdict"] = "fail"
            label["rerun_note"] = note
            doc.meta["status"] = "draft"
            target = brain / "queue" / doc.path.name  # back in the queue, even from done/
        elif action == "drop":
            label["verdict"] = "fail"
            label["dropped"] = True
            target = brain / "queue" / "done" / doc.path.name
        else:
            raise ReviewError(f"There's no action called {action!r}.")
        label["decided_at"] = _now()
        doc.save(target)
        return dict(label)


class _Doc:
    """One ticket file, its frontmatter loaded for a round trip that keeps comments and formatting."""

    def __init__(self, brain: Path, path: Path, attempt: int):
        self.brain, self.path, self.attempt = brain, path, attempt
        self.yaml = YAML(typ="rt")
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        head, self.body = split_text(path.read_text(encoding="utf-8"))
        self.meta = self.yaml.load(head)

    def entry(self):
        found = [v for v in self.meta.get("verdicts") or [] if hasattr(v, "get") and v.get("attempt") == self.attempt]
        return found[-1] if found else None

    def append(self, entry: dict):
        if "verdicts" not in self.meta or self.meta["verdicts"] is None:
            self.meta["verdicts"] = []
        if not isinstance(self.meta["verdicts"], list):
            raise ReviewError(f"{self.path.name} has a `verdicts:` field that isn't a list; fix it by hand.")
        self.meta["verdicts"].append(entry)
        return self.meta["verdicts"][-1]

    def save(self, target: Path | None = None) -> None:
        target = target or self.path
        out = io.StringIO()
        self.yaml.dump(self.meta, out)
        text = "---\n" + out.getvalue() + "---\n" + self.body
        split_doc(text)  # never write a file the checker couldn't read back
        staging = self.brain / ".runtime" / "dashboard"
        staging.mkdir(parents=True, exist_ok=True)
        temp = staging / f"{target.name}.writing-{os.getpid()}-{threading.get_ident()}"
        temp.write_text(text, encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp, target)
        if target != self.path:
            self.path.unlink()


@contextmanager
def _writing(brain: Path, ticket_id: str, attempt: int):
    with _lock, _sync_lock(brain):
        try:
            c = card(brain, ticket_id)
        except NotACard as exc:
            raise ReviewError(f"That card isn't waiting for review any more ({exc}).") from exc
        if attempt != c["attempt"]:
            raise ReviewError(f"Attempt {attempt} isn't the one waiting for review; attempt {c['attempt']} is.")
        try:
            doc = _Doc(brain, ticket_path(brain, ticket_id), attempt)
        except (OSError, ValueError) as exc:
            raise ReviewError(f"The ticket file can't be read, so nothing was written: {exc}") from exc
        yield c, doc


@contextmanager
def _sync_lock(brain: Path):
    """The brain's sync lock (agents/sync/sync.py RepoLock), so autosave and pulls wait for the write."""
    path = brain / ".runtime" / "locks" / "sync.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fd:
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ReviewError("The brain is syncing right now. Try again in a moment.") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")
