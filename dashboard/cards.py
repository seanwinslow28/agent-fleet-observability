"""The morning's cards, read from the brain's files on every request.

A card is a work ticket whose latest attempt has a checker verdict and no
decision from Sean yet. The checker's files are the evidence: its verdict, its
claim-evidence table and the judge's answer. The agent's own summary comes
last, under More details. The judge's answer is never on the card; it's asked
for separately, after Sean's label is saved (judge_answer).
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yaml

LANES = ["Blocked", "Unverified-done", "Verified", "Needs-decision"]
TICKET_ID = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*")
ADVISORY_BADGE = "cross-vendor judge, unvalidated; reads agent-written text"
# When every other check passed, the judge alone picks Verified or Unverified-done, so
# the lane would give its answer away (#23 Amendment 3). Until Sean has answered the
# judgement sentence, such a card hides its lane and says this instead (Sean, 2026-10-06).
BLIND_WHY = "every command passed; the judge's answer shows once your label is saved"


class NotACard(LookupError):
    pass


class Unreadable(NotACard):
    """A ticket file the dashboard can't read, listed on the page rather than hidden."""


# -- the brain's files --

# The checker's own frontmatter rule (agents/checker/tickets.py), so both read a ticket the same way.
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n(.*))?\Z", re.S)


def split_text(text: str) -> tuple[str, str]:
    """A ticket's frontmatter text and its body. ValueError if it has none the checker can read."""
    match = FRONTMATTER.match(text.removeprefix("\ufeff").replace("\r\n", "\n"))
    if not match:
        raise ValueError("its frontmatter isn't between two `---` lines")
    return match.group(1) + "\n", match.group(2) or ""


def split_doc(text: str) -> tuple[dict, str]:
    """A ticket's YAML frontmatter, parsed, and the body after it. ValueError if unreadable."""
    head, body = split_text(text)
    try:
        meta = yaml.safe_load(head) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"its frontmatter isn't valid YAML ({str(exc).splitlines()[0]})") from exc
    if not isinstance(meta, dict):
        raise ValueError("its frontmatter isn't a set of fields")
    return meta, body


def ticket_path(brain: Path, ticket_id: str) -> Path | None:
    """queue/<id>.md, or queue/done/<id>.md once closed. None if neither, or not an id."""
    if not TICKET_ID.fullmatch(ticket_id):
        return None
    for path in (brain / "queue" / f"{ticket_id}.md", brain / "queue" / "done" / f"{ticket_id}.md"):
        if path.is_file():
            return path
    return None


def _yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def _genuine(brain: Path, ticket_id: str, attempt: int) -> bool:
    """Only a verdict the checker wrote counts, by the checker's own rule
    (agents/checker/verdict.py `genuine`): its hash matches the note in
    .runtime/verdicts/, or the checker's own commit added it."""
    path = brain / "work" / "checker" / ticket_id / f"attempt-{attempt}" / "verdict.yaml"
    note = brain / ".runtime" / "verdicts" / ticket_id / f"attempt-{attempt}.sha256"
    if note.is_file() and note.read_text().strip() == hashlib.sha256(path.read_bytes()).hexdigest():
        return True
    subject = subprocess.run(["git", "-C", str(brain), "log", "-1", "--format=%s", "--", str(path)],
                             capture_output=True, text=True).stdout.strip()
    return subject.startswith("checker:")


def latest_verdict(brain: Path, ticket_id: str) -> tuple[int, dict | None]:
    folder = brain / "work" / "checker" / ticket_id
    numbers = sorted((int(m.group(1)) for child in (folder.iterdir() if folder.is_dir() else [])
                      if (m := re.fullmatch(r"attempt-(\d+)", child.name)) and (child / "verdict.yaml").is_file()),
                     reverse=True)
    for n in numbers:
        if _genuine(brain, ticket_id, n):
            verdict = _yaml(folder / f"attempt-{n}" / "verdict.yaml")
            return n, verdict if isinstance(verdict, dict) else None
    return 0, None


def label_for(meta: dict, attempt: int) -> dict | None:
    """The attempt's entry in `verdicts:`, which may hold only a recorded peek so far."""
    labels = [v for v in meta.get("verdicts") or [] if isinstance(v, dict) and v.get("attempt") == attempt]
    return labels[-1] if labels else None


def saved(entry: dict | None) -> bool:
    """Whether Sean's label is saved: a peek alone writes an entry with no answers yet."""
    return bool(entry) and "lane_agree" in entry


# -- the cards --

def review(brain: Path) -> dict:
    """Every card, plus every ticket file that can't be read, so nothing waits unseen."""
    brain = Path(brain)
    found, unreadable = [], []
    for path in sorted([*(brain / "queue").glob("*.md"), *(brain / "queue" / "done").glob("*.md")]):
        try:
            found.append(_card(brain, path))
        except Unreadable as exc:
            unreadable.append({"file": str(path.relative_to(brain)), "why": str(exc)})
        except NotACard:
            continue
    found.sort(key=lambda c: (LANES.index(c["lane"]) if c["lane"] in LANES else len(LANES), c["id"]))
    return {"cards": found, "unreadable": unreadable}


def cards(brain: Path) -> list[dict]:
    return review(brain)["cards"]


def card(brain: Path, ticket_id: str) -> dict:
    path = ticket_path(Path(brain), ticket_id)
    if path is None:
        raise NotACard(f"there's no ticket {ticket_id}")
    return _card(Path(brain), path)


def _card(brain: Path, path: Path) -> dict:
    ticket_id = path.stem
    if not TICKET_ID.fullmatch(ticket_id):
        raise NotACard(f"{path.name} isn't a ticket")
    try:
        meta, body = split_doc(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable(f"it can't be read: {exc}") from exc
    attempt, verdict = latest_verdict(brain, ticket_id)
    if not verdict:
        raise NotACard(f"{ticket_id} has no verdict")
    entry = label_for(meta, attempt)
    label = entry if saved(entry) else None
    if label and "verdict" in label:
        raise NotACard(f"{ticket_id} attempt {attempt} is decided")

    lane = verdict.get("lane") or "Blocked"
    lane_hidden = not label and _judge_decides(verdict)
    if lane_hidden:
        verdict = {**verdict, "why": BLIND_WHY}
    worker = verdict.get("worker") if isinstance(verdict.get("worker"), dict) else {}
    calibration = bool(worker.get("calibration"))
    judge = verdict.get("judge") if isinstance(verdict.get("judge"), dict) else None
    checks = [_check(k, verdict) for k in verdict.get("checks") or [] if isinstance(k, dict)]
    judgement = next((k for k in verdict.get("checks") or [] if isinstance(k, dict) and k.get("kind") == "judgement"),
                     None)
    deliverable = brain / str(verdict["deliverable"]) if verdict.get("deliverable") else None
    folder = brain / "work" / "checker" / ticket_id / f"attempt-{attempt}"
    evidence = _yaml(folder / "evidence.yaml") if (folder / "evidence.yaml").is_file() else []
    runs = brain / ".runtime" / "runs" / ticket_id / str(attempt)
    facts = _yaml(runs / "facts.yaml") or {}
    flags = list(verdict.get("flags") or [])
    if isinstance(facts, dict) and facts.get("compacted") and "compacted" not in flags:
        flags.append("compacted")
    spent, budget = verdict.get("spent"), verdict.get("budget")

    return {
        "id": ticket_id,
        "attempt": attempt,
        "closed": path.parent.name == "done",
        "lane": lane,
        "lane_hidden": lane_hidden,
        "reason": verdict.get("reason"),
        "calibration": calibration,
        "title": _title(body) or ticket_id,
        "headline": _headline(verdict),
        "checks": checks,
        "answer": _section(deliverable, "Answer") if deliverable else None,
        "evidence": [_evidence(r) for r in evidence or [] if isinstance(r, dict)],
        "spend": {**spent, "budget": budget} if isinstance(spent, dict) else None,
        "judge": _judge(judge, judgement),
        "audio": _audio(brain, ticket_id, attempt, verdict),
        "details": {
            "worker": None if calibration and not label else
            (f"{worker.get('agent')} on {worker.get('model')}" if worker else None),
            # The run log and the agent's summary can name the model, so a calibration attempt
            # holds them back until the label is saved, like the worker.
            "run_log": (runs / "tools.jsonl").is_file() and not (calibration and not label),
            "drew_on": [str(n) for n in meta.get("notes") or []],
            "flags": flags,
            "notes": [str(n) for n in verdict.get("notes") or []],
            "summary": _read(brain / "work" / str(worker.get("agent")) / ticket_id / "result.md")
            if worker.get("agent") and not (calibration and not label) else None,
            "checked_at": verdict.get("checked_at"),
        },
        "questions": _questions(lane, verdict, deliverable is not None, judgement, judgement_first=lane_hidden),
        "label": label,
        "peeked": bool(entry and entry.get("judge_seen_first")),
    }


def _judge_decides(verdict: dict) -> bool:
    checks = [k for k in verdict.get("checks") or [] if isinstance(k, dict)]
    judged = [k for k in checks if k.get("kind") == "judgement"]
    return (verdict.get("lane") in ("Verified", "Unverified-done") and not verdict.get("unconfirmed_citations")
            and bool(judged) and all(k.get("result") in ("pass", "fail") for k in judged)
            and all(k.get("result") == "pass" for k in checks if k.get("kind") != "judgement"))


def _check(k: dict, verdict: dict) -> dict:
    result = k.get("result")
    summary = k.get("summary") or ""
    if k.get("kind") == "judgement" and result in ("pass", "fail"):
        result, summary = "hidden", "the judge's answer shows once your label is saved"
    elif k.get("name") == "quote-match" and result == "pass" and verdict.get("unconfirmed_citations"):
        result = "unconfirmed"
    return {"name": k.get("name"), "result": result, "summary": summary}


def _headline(verdict: dict) -> str:
    why = str(verdict.get("why") or "the checker gave no reason")
    sentence = why[0].upper() + why[1:]
    if verdict.get("reason") in ("checks-failed", "malformed"):
        failed = next((k for k in verdict.get("checks") or []
                       if isinstance(k, dict) and k.get("result") == "fail" and k.get("kind") != "judgement"), None)
        if failed and failed.get("summary"):
            sentence += ("; " if verdict["reason"] == "malformed" else ": ") + failed["summary"]
    return sentence.rstrip(".") + "."


def _judge(judge: dict | None, judgement: dict | None) -> dict | None:
    if not judgement:
        return None
    judge = judge or {}
    graduated = judge.get("status") == "graduated"
    return {
        "sentence": judgement.get("sentence"),
        "model": judge.get("model"),
        "effort": judge.get("effort"),
        "status": judge.get("status") or "advisory",
        "badge": f"{judge.get('model')}, graduated under prompt {str(judge.get('prompt_commit'))[:7]}"
        if graduated else ADVISORY_BADGE,
        "answered": judgement.get("result") in ("pass", "fail"),
    }


def judge_answer(brain: Path, ticket_id: str, attempt: int) -> dict:
    """What the judge said, for the card once Sean's label is saved, or on a peek."""
    folder = Path(brain) / "work" / "checker" / ticket_id / f"attempt-{attempt}"
    verdict = _yaml(folder / "verdict.yaml") or {}
    judge = verdict.get("judge") if isinstance(verdict.get("judge"), dict) else {}
    critique = None
    text = _read(folder / "judge.md")
    if text and "## Critique" in text:
        critique = text.split("## Critique", 1)[1].strip() or None
        if critique == "(none)":
            critique = None
    return {"result": judge.get("result"), "critique": critique, "why": judge.get("why")}


def _evidence(row: dict) -> dict:
    url = str(row.get("url") or "")
    return {
        "section": row.get("section"),
        "claim": row.get("claim"),
        "marker": row.get("marker"),
        "url": url,
        "host": urlparse(url).hostname or url,
        "quote": row.get("quote"),
        "status": row.get("status"),
        "passage": row.get("passage"),
        "why": row.get("why"),
    }


def _audio(brain: Path, ticket_id: str, attempt: int, verdict: dict) -> dict:
    if any(isinstance(k, dict) and k.get("result") == "fail" and k.get("kind") != "judgement"
           for k in verdict.get("checks") or []):
        return {"ready": False, "why": "no audio: a check failed"}
    said = None
    for record in sorted((brain / "work" / "runner").glob("*.yaml")):
        night = _yaml(record)
        for ran in (night.get("ran") or []) if isinstance(night, dict) else []:
            if isinstance(ran, dict) and ran.get("id") == ticket_id and ran.get("attempt") == attempt:
                said = ran.get("audio")
    if said == "audio rendered" and (brain / ".runtime" / "audio" / f"{ticket_id}.mp3").is_file():
        return {"ready": True, "why": None}
    return {"ready": False, "why": said or "no audio for this attempt"}


def _questions(lane: str, verdict: dict, has_deliverable: bool, judgement: dict | None, *,
               judgement_first: bool = False) -> list[dict]:
    why = str(verdict.get("why") or "it gave no reason")
    qs = [{"field": "lane_agree", "question": f"Does it belong in {lane.replace('-', ' ')}?",
           "explainer": f"The checker put it there because {why.rstrip('.')}."}]
    if has_deliverable:
        qs.append({"field": "deliverable", "question": "Keep the brief?",
                   "explainer": "Yes if it answers your question well enough to use as it is."})
    if judgement and judgement.get("sentence"):
        qs.append({"field": "judgement", "question": judgement["sentence"],
                   "explainer": "Answer it yourself from the evidence. The judge's answer shows once you save."})
    if judgement_first:
        qs.insert(0, qs.pop())
    return qs


def _title(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _section(path: Path, heading: str) -> str | None:
    text = _read(path)
    if not text:
        return None
    match = re.search(rf"^## {heading}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
