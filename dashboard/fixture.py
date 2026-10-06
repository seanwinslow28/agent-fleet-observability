"""An invented brain for tests and for trying the Review page end to end.

Every ticket, brief and URL here is made up. Real brain data never enters this
repo; a fixture is never published in the showcase.

    uv run python -m dashboard.fixture <folder>     # writes a fresh fixture brain
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

NIGHT = "2026-10-07"
JUDGEMENT = "Each claim is supported by the passage quoted for it."
NOTES = [
    "Deny scan: reads tool names and shell commands only; a side effect planted through a file edit passes it.",
    "citations resolve, quotes match; support unchecked",
    "cross-vendor judge, unvalidated; reads agent-written text",
]

TYPE = f"""---
agent: researcher
deliverable: note
deliverable_file: brief.md
privacy: open
routes:
  open:
    worker: claude-opus-5-5
    calibration: claude-sonnet-5-5
    judge: {{model: gpt-6.1-sol, effort: high}}
judgement: {JUDGEMENT}
---

# Research brief
"""

AUTOMATIC = [
    ("diff-within-scope", "automatic", "every change is inside the ticket's scope"),
    ("budget", "automatic", "4.1/45 minutes, 31/80 turns, 2.10/8 usd"),
    ("run-record", "automatic", "run.yaml says done; the record is complete"),
    ("state-changed", "automatic", "output exists and differs; content unchecked"),
    ("deny-scan", "automatic", "no send, spend, delete, publish or account change in 28 tool call(s)"),
    ("note-provenance", "type-supplied", "frontmatter complete: agent, model, ticket, attempt, generated, sources"),
    ("secret-scan", "type-supplied", "no secrets in the 4 file(s) the run committed"),
    ("brief-sections", "type-supplied", "Answer, Findings, Gaps and Sources, in order"),
    ("brief-word-caps", "type-supplied", "Answer 61/150 words, Findings 240/1200"),
    ("brief-markers", "type-supplied", "every Findings paragraph cited; 3 markers, each with a Sources line"),
    ("brief-sources", "type-supplied", "5 sources, every quote within 50 words"),
]


def _checks(quote_match: tuple[str, str], judge: tuple[str, str]) -> list[dict]:
    rows = [{"name": n, "kind": k, "result": "pass", "summary": s, "output": f"checks/{n}.txt"}
            for n, k, s in AUTOMATIC]
    rows.append({"name": "quote-match", "kind": "type-supplied", "result": quote_match[0],
                 "summary": quote_match[1], "output": "checks/quote-match.txt"})
    rows.append({"name": "judgement", "kind": "judgement", "result": judge[0], "summary": judge[1],
                 "sentence": JUDGEMENT, "output": "judge.md"})
    return rows


def _row(claim, marker, url, quote, status, passage=None, why=None):
    row = {"section": "Answer", "claim": claim, "marker": marker, "url": url, "quote": quote, "status": status}
    if passage:
        row["passage"] = passage
    if why:
        row["why"] = why
    return row


SOURDOUGH = [
    _row("A starter rises fastest between 24 and 27 degrees Celsius.", 1,
         "https://bakers-notes.example.org/starter-temperature",
         "peak activity came between 24 and 27 °C", "found",
         "We fed the same starter at five temperatures for two weeks. Its peak activity came between 24 and 27 °C, "
         "with the rise slowing sharply above 30."),
    _row("Below 20 degrees, it takes about twice as long to peak.", 2,
         "https://fermentation-lab.example.net/cool-kitchens",
         "at 19 °C the starter needed roughly double the time to peak", "found",
         "Cool kitchens are the usual culprit. In our trials, at 19 °C the starter needed roughly double the time "
         "to peak, though the flavour turned more sour."),
    _row("Feeding twice a day matters more than the exact temperature.", 3,
         "https://bakers-notes.example.org/feeding-schedule",
         "a steady twice-daily feed did more for reliability than any temperature tweak", "found",
         "Over the season, a steady twice-daily feed did more for reliability than any temperature tweak we tried."),
]

BIKE = [
    _row("Hot-melt wax lasts about three times as long between cleanings as a wet lube.", 1,
         "https://chain-tests.example.com/longevity",
         "hot-melt wax ran roughly three times the distance before needing a clean", "found",
         "Across 4,000 km of testing, hot-melt wax ran roughly three times the distance before needing a clean."),
    _row("Drip-on wax needs a full strip of the factory grease first.", 2,
         "https://workshop-guide.example.org/drip-wax",
         "strip every trace of factory grease before the first application", "unconfirmed",
         why="the page timed out after 20 seconds"),
    _row("Waxing adds about ten minutes a week of upkeep.", 3,
         "https://chain-tests.example.com/upkeep",
         "about ten minutes a week once the routine is set", "found",
         "Upkeep is modest: about ten minutes a week once the routine is set, mostly re-waxing a spare chain."),
]

HOUSEPLANT = [
    _row("A north-facing window gives a pothos enough light to keep growing.", 1,
         "https://plant-care.example.org/pothos-light",
         "pothos tolerate a north window and keep putting out new leaves", "found",
         "Pothos are forgiving. They tolerate a north window and keep putting out new leaves, just more slowly."),
    _row("A fiddle-leaf fig needs six hours of direct sun every day.", 2,
         "https://plant-care.example.org/fiddle-leaf",
         "fiddle-leaf figs need at least six hours of direct sun daily", "missing",
         "Fiddle-leaf figs want bright, indirect light for most of the day. A little gentle morning sun helps, but "
         "hours of harsh direct sun will scorch the leaves.",
         why="the quote isn't on the page the checker fetched"),
    _row("Grow lights at 30 centimetres can replace a sunny window.", 3,
         "https://lighting-guide.example.com/grow-lights",
         "a full-spectrum panel at 30 cm matched a south window", "found",
         "In our side-by-side, a full-spectrum panel at 30 cm matched a south window for most foliage plants."),
]

TEA = [
    _row("Green tea turns bitter when steeped above 80 degrees.", 1,
         "https://tea-guide.example.org/green-tea",
         "above 80 °C the leaves release bitter catechins quickly", "found",
         "Water temperature matters most for green tea: above 80 °C the leaves release bitter catechins quickly."),
    _row("Black tea needs five minutes to reach full strength.", 2,
         "https://tea-guide.example.org/black-tea",
         "three to four minutes brings out full strength", "found",
         "For most black teas, three to four minutes brings out full strength; longer mostly adds astringency."),
]


def _brief(title: str, answer: str, rows: list[dict]) -> str:
    sources = "\n".join(f"[{r['marker']}] {r['url']} — \"{r['quote']}\"" for r in rows)
    return (f"---\nwritten_by: agent\nagent: researcher\n---\n\n## Answer\n\n{answer}\n\n## Findings\n\n"
            f"The details behind the answer, with every paragraph cited [1].\n\n## Gaps\n\nNone found.\n\n"
            f"## Sources\n\n{sources}\n")


def _ticket(title: str, status: str, verdicts: list[dict] | None = None, notes: list[str] | None = None,
            goal: str | None = "Sean wants a short answer he can act on this week.") -> str:
    meta = {"type": "research-brief", "status": status, "privacy": "open", "notes": notes or []}
    if verdicts:
        meta["verdicts"] = verdicts
    body = f"# {title}\n"
    if goal:
        body += f"\n## Goal\n\n{goal}\n"
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _attempt(brain: Path, ticket_id: str, attempt: int, verdict: dict, evidence: list[dict] | None,
             judge_md: str | None) -> None:
    folder = brain / "work" / "checker" / ticket_id / f"attempt-{attempt}"
    verdict = {"ticket": ticket_id, "attempt": attempt, "type": "research-brief", **verdict}
    _write(folder / "verdict.yaml", yaml.safe_dump(verdict, sort_keys=False, allow_unicode=True, width=100))
    if evidence is not None:
        _write(folder / "evidence.yaml", yaml.safe_dump(evidence, sort_keys=False, allow_unicode=True))
    if judge_md:
        _write(folder / "judge.md", judge_md)
    # The checker's own note of the verdict it wrote, so the dashboard trusts it.
    digest = hashlib.sha256((folder / "verdict.yaml").read_bytes()).hexdigest()
    _write(brain / ".runtime" / "verdicts" / ticket_id / f"attempt-{attempt}.sha256", digest + "\n")


def _judge(result: str, critique: str, status: str = "advisory") -> tuple[dict, str]:
    judge = {"model": "gpt-6.1-sol", "effort": "high", "vendor": "openai", "prompt_commit": "0" * 40,
             "status": status, "result": result}
    md = (f"# Judge: gpt-6.1-sol\n\ncross-vendor judge, unvalidated; reads agent-written text.\n\n"
          f"Sentence: {JUDGEMENT}\nAnswer: {result}\n\n## Critique\n\n{critique}\n")
    return judge, md


def _finished(brain: Path, ticket_id: str, attempt: int, *, lane: str, why: str, reason: str | None,
              title: str, answer: str, rows: list[dict], quote_match: tuple[str, str], judge_result: str,
              critique: str, calibration: bool = False, unconfirmed: list[int] | None = None,
              summary: str = "I answered the question from five sources.", compacted: bool = False) -> None:
    deliverable = f"work/researcher/{ticket_id}/brief.md"
    _write(brain / deliverable, _brief(title, answer, rows))
    _write(brain / "work" / "researcher" / ticket_id / "result.md", summary + "\n")
    _write(brain / "work" / "researcher" / ticket_id / "run.yaml", f"attempt: {attempt}\noutcome: done\n")
    judge, judge_md = _judge(judge_result, critique)
    model = "claude-sonnet-5-5" if calibration else "claude-opus-5-5"
    _attempt(brain, ticket_id, attempt, {
        "lane": lane, "reason": reason, "why": why,
        "checks": _checks(quote_match, (judge_result, f"the judge said {judge_result}")),
        "judge": judge,
        "spent": {"minutes": 4.1, "turns": 31, "usd": 2.10},
        "budget": {"minutes": 45, "turns": 80, "usd": 8},
        "stopped_on": None,
        "started": f"{NIGHT}T01:04:00-04:00", "finished": f"{NIGHT}T01:08:10-04:00",
        "worker": {"agent": "researcher", "model": model, "calibration": calibration},
        "deliverable": deliverable,
        "unconfirmed_citations": unconfirmed or [],
        "flags": ["compacted"] if compacted else [],
        "notes": NOTES,
    }, rows, judge_md)
    runs = brain / ".runtime" / "runs" / ticket_id / str(attempt)
    _write(runs / "tools.jsonl", '{"tool": "web_search", "input": {"query": "an invented search"}}\n')
    _write(runs / "facts.yaml", f"attempt: {attempt}\ncompacted: {str(compacted).lower()}\n")


def build(brain: Path) -> Path:
    """Write the fixture brain into `brain` (which should be empty or absent)."""
    brain = Path(brain)
    _write(brain / "queue" / "types" / "research-brief.md", TYPE)
    _write(brain / "notes" / "baking.md", "# Baking\n")

    # Verified: every check passed.
    tid = f"{NIGHT}-sourdough-starter-temperature"
    title = "What temperature keeps a sourdough starter most active?"
    _write(brain / "queue" / f"{tid}.md", _ticket(title, "ready", notes=["notes/baking.md"]))
    _finished(brain, tid, 1, lane="Verified", why="every check passed", reason=None, title=title,
              answer="Keep it between 24 and 27 degrees Celsius. Below 20 it still works, but takes about twice as "
                     "long to peak, and a steady twice-daily feed matters more than the exact number.",
              rows=SOURDOUGH, quote_match=("pass", "all 3 quotes found on the pages they cite"),
              judge_result="pass", critique="Each quote supports its claim.")

    # Unverified-done: a page didn't load, so one citation is unconfirmed.
    tid = f"{NIGHT}-bike-chain-wax"
    title = "Is waxing a bike chain worth the effort over a wet lube?"
    _write(brain / "queue" / f"{tid}.md", _ticket(title, "ready"))
    _finished(brain, tid, 1, lane="Unverified-done", why="1 citation could not be confirmed", reason=None,
              title=title,
              answer="Yes, if you ride often. Hot-melt wax lasts about three times as long between cleanings, for "
                     "about ten minutes a week of upkeep. The first strip of factory grease is the only big job.",
              rows=BIKE, quote_match=("pass", "2 of 3 quotes found; 1 page didn't load"),
              judge_result="pass", critique="Supported, though one source could not be read.", unconfirmed=[2],
              compacted=True)

    # Blocked: checks-failed, a quote that isn't on the page.
    tid = f"{NIGHT}-houseplant-light"
    title = "Which common houseplants do well in a north-facing room?"
    _write(brain / "queue" / f"{tid}.md", _ticket(title, "ready"))
    _finished(brain, tid, 1, lane="Blocked", why="quote-match failed", reason="checks-failed", title=title,
              answer="Pothos will keep growing in a north window. A fiddle-leaf fig won't: it needs six hours of "
                     "direct sun. A grow light at 30 centimetres can stand in for a sunny window.",
              rows=HOUSEPLANT, quote_match=("fail", "1 quote isn't on the page it cites"),
              judge_result="fail", critique="Claim 2 is not supported: the page says the opposite.")

    # Blocked: malformed, never ran.
    tid = f"{NIGHT}-no-goal"
    _write(brain / "queue" / f"{tid}.md", _ticket("A ticket with no goal, so preflight blocks it.", "ready", goal=None))
    _attempt(brain, tid, 1, {
        "lane": "Blocked", "reason": "malformed", "why": "preflight found the ticket malformed, so it never ran",
        "checks": [{"name": "preflight", "kind": "automatic", "result": "fail",
                    "summary": "the ticket has no goal: write two or three sentences under `## Goal`",
                    "output": "checks/preflight.txt"}],
    }, None, None)

    # A calibration attempt on a ticket Sean already closed: the worker stays hidden until he labels it.
    tid = "2026-10-06-tea-steeping"
    title = "How long and how hot should green and black tea steep?"
    first = {"attempt": 1, "lane": "Verified", "verdict": "pass", "read": True, "lane_agree": True,
             "deliverable": "pass", "judgement": "pass", "judge_seen_first": False, "at": "2026-10-06T06:12:00-04:00"}
    _write(brain / "queue" / "done" / f"{tid}.md", _ticket(title, "ready", verdicts=[first]))
    _finished(brain, tid, 1, lane="Verified", why="every check passed", reason=None, title=title,
              answer="Green below 80 degrees for two minutes; black at a boil for three to four.", rows=TEA,
              quote_match=("pass", "all 2 quotes found"), judge_result="pass", critique="Supported.")
    _finished(brain, tid, 2, lane="Unverified-done", why="every command passed but the judge said fail",
              reason=None, title=title, calibration=True,
              answer="Green below 80 degrees; black for five minutes to reach full strength.", rows=TEA,
              quote_match=("pass", "all 2 quotes found"), judge_result="fail",
              critique="Claim 2 says five minutes; the passage says three to four.")

    # Already labeled and accepted: not a card.
    tid = "2026-10-05-old-question"
    done = {"attempt": 1, "lane": "Verified", "verdict": "pass", "read": True, "lane_agree": True,
            "deliverable": "pass", "judgement": "pass", "judge_seen_first": False, "at": "2026-10-06T06:00:00-04:00"}
    _write(brain / "queue" / "done" / f"{tid}.md", _ticket("An old question Sean already reviewed.", "ready",
                                                           verdicts=[done]))
    _finished(brain, tid, 1, lane="Verified", why="every check passed", reason=None, title="An old question",
              answer="Done already.", rows=TEA, quote_match=("pass", "all quotes found"), judge_result="pass",
              critique="Supported.")

    # The night's record: which cards got audio.
    record = {"night": NIGHT, "ran": [
        {"id": f"{NIGHT}-sourdough-starter-temperature", "attempt": 1, "lane": "Verified", "audio": "audio rendered"},
        {"id": f"{NIGHT}-bike-chain-wax", "attempt": 1, "lane": "Unverified-done",
         "audio": "audio not rendered: punctuation check failed"},
        {"id": f"{NIGHT}-houseplant-light", "attempt": 1, "lane": "Blocked", "reason": "checks-failed"},
        {"id": f"{NIGHT}-no-goal", "attempt": 1, "lane": "Blocked", "reason": "malformed"},
        {"id": "2026-10-06-tea-steeping", "attempt": 2, "calibration": True, "lane": "Unverified-done",
         "audio": "audio rendered"},
    ], "not_started": []}
    _write(brain / "work" / "runner" / f"{NIGHT}.yaml", yaml.safe_dump(record, sort_keys=False))
    audio = brain / ".runtime" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    for name in (f"{NIGHT}-sourdough-starter-temperature", "2026-10-06-tea-steeping"):
        (audio / f"{name}.mp3").write_bytes(TONE.read_bytes())
    return brain


# Two quiet seconds of a tone, so Listen has something to play in a fixture.
TONE = Path(__file__).parent / "assets" / "fixture-tone.mp3"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m dashboard.fixture <folder>")
    target = Path(sys.argv[1])
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} isn't empty; give a new folder")
    print(build(target))
