# Kanban v1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the four silent ticket sources, swap the eval data origin to `agent-run-history.csv` failures, redesign the kanban card to a two-line uniform shape, and add column sparklines + agent-state dots so `/kanban` and `/fleet` read as one design system.

**Architecture:** All changes stay inside the existing static-build pipeline — readers → kanban composer → aggregations → render — with no new dependencies, no JS framework, no schema changes. The agent-state dot reuses the existing `compute_fleet_status` output. Column sparklines reuse the existing `svg_charts.sparkline` helper. Read-only v1 scope and v2 gate are preserved.

**Tech Stack:** Python 3.12, Jinja2, inline SVG, ruff, pytest. No new packages.

**Spec:** [docs/2026-05-18-kanban-v1-1-redesign.md](2026-05-18-kanban-v1-1-redesign.md)

---

## File map

Create:
- (none — all changes modify existing files)

Modify:
- `lib/readers.py` — fix research bullet regex; refactor `read_lint_reports` to return parsed `issues` list
- `lib/kanban.py` — research title parser; lint composer rewrite; new failures-from-runs composer; drop old eval-from-`eval_last_run` branch
- `lib/aggregations.py` — new `compute_agent_state(fleet_status)` adapter; new `compute_column_sparklines(runs)`; wire both into `compute_all`
- `lib/render.py` — thread `agent_state` + `column_sparkline_svgs` into common context
- `templates/partials/kanban_board.html` — new two-line card markup; agent-state dot; column-header sparkline
- `assets/styles.css` — new `.ticket-title`, `.ticket-meta`, `.agent-dot`, `.column-spark`, `.agent-dot--healthy/degraded/down` rules
- `tests/fixtures/sample-lint-report.md` — replace with real-shape (`## CRITICAL/HIGH/MEDIUM/LOW` sections + `**rule** (Tn)` bullets)
- `tests/fixtures/sample-research-queue.md` — add a `[x]` item under `## Pending` to exercise the regex fix
- `tests/test_readers.py` — update lint reader test for new return shape; update research test to assert the `[x]` item is excluded
- `tests/test_kanban.py` — rewrite eval-source test to use runs; add lint cap-20 + title parser + agent-state + sparkline tests
- `tests/test_aggregations.py` — add tests for `compute_agent_state` and `compute_column_sparklines`

Vault (REPO 2, one-line manual step in Task 0):
- `touch /Users/seanwinslow/Code-Brain/code-brain/vault/00_inbox/tickets.md`

---

## Task 0: Baseline + vault prerequisite

**Files:**
- Create (vault): `/Users/seanwinslow/Code-Brain/code-brain/vault/00_inbox/tickets.md`

- [ ] **Step 1: Create the empty manual-tickets file in the vault**

```bash
touch /Users/seanwinslow/Code-Brain/code-brain/vault/00_inbox/tickets.md
ls -la /Users/seanwinslow/Code-Brain/code-brain/vault/00_inbox/tickets.md
```
Expected: file exists, 0 bytes.

- [ ] **Step 2: Confirm baseline test suite passes**

Run: `cd /Users/seanwinslow/Code-Brain/agent-fleet-observability && .venv/bin/pytest -q`
Expected: PASS, ~55 tests. (This is the pre-change baseline so any failures introduced later are clearly attributable.)

- [ ] **Step 3: No commit** — Task 0 only changes vault state; nothing to commit in this repo.

---

## Task 1: Fix the research `[ ]` vs `[x]` regex bug

**Files:**
- Modify: `lib/readers.py:247-248` (the two `_BULLET_RE` and `_PLAIN_BULLET_RE` lines)
- Modify: `tests/fixtures/sample-research-queue.md` (add a `[x]` row under `## Pending`)
- Modify: `tests/test_readers.py:110-114` (`test_read_research_queue_parses_sections`)

- [ ] **Step 1: Update the fixture to include a done item under `## Pending`**

Edit `tests/fixtures/sample-research-queue.md` — replace the `## Pending` block with:

```markdown
## Pending

- [ ] **Substrate repricing in 2026 agent boards** — single-shape, local LDR
- [ ] **MCP catalog survey** — heavy, route to Gemini DR
- [ ] **AgentField vs LangSmith Fleet pricing** — single-shape
- [x] **Old completed topic still under Pending header** — done 2026-05-01
```

The `[x]` row is the bug-reproducer: today's code matches it as pending.

- [ ] **Step 2: Run the existing research test to confirm the bug is reproducible**

Run: `.venv/bin/pytest tests/test_readers.py::test_read_research_queue_parses_sections -v`
Expected: **FAIL** — assertion `len(out["pending"]) == 3` will get 4 because the `[x]` item is being matched.

- [ ] **Step 3: Fix the regex — split pending and done into separate patterns**

In `lib/readers.py`, replace lines 247-248:

```python
_BULLET_RE = re.compile(r"^- \[[ x]\]\s*(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
_PLAIN_BULLET_RE = re.compile(r"^-\s+(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
```

with:

```python
_BULLET_PENDING_RE = re.compile(r"^- \[ \]\s*(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
_BULLET_DONE_RE = re.compile(r"^- \[x\]\s*(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
_PLAIN_BULLET_RE = re.compile(r"^-\s+(.+?)(?:\s*—\s*assigned:\s*(\S+))?\s*$")
```

- [ ] **Step 4: Update `read_research_queue` to use the right pattern per section**

Replace `read_research_queue` (currently lines 299-308) with:

```python
def read_research_queue(path: Path) -> dict:
    """Parse research-queue.md into pending / in_flight / done item lists.

    `## Pending` and `## In Flight` only match unchecked `- [ ]` items; the
    `## Done` section matches checked `- [x]` items. The old single regex
    treated `[ ]` and `[x]` as equivalent, so completed items left under
    a stale `## Pending` header were silently surfaced as live tickets.
    """
    if not path.exists():
        return {"pending": [], "in_flight": [], "done": []}
    sections = _split_sections(path.read_text())
    return {
        "pending": _parse_section_items(sections.get("pending", []), _BULLET_PENDING_RE),
        "in_flight": _parse_section_items(sections.get("in_flight", []), _BULLET_PENDING_RE),
        "done": _parse_section_items(sections.get("done", []), _BULLET_DONE_RE),
    }
```

- [ ] **Step 5: Run the test to verify it now passes**

Run: `.venv/bin/pytest tests/test_readers.py::test_read_research_queue_parses_sections -v`
Expected: PASS — `len(out["pending"]) == 3` (the `[x]` is now excluded).

- [ ] **Step 6: Add a positive assertion for the done section**

Append to `tests/test_readers.py` (after `test_read_research_queue_parses_sections`):

```python
def test_read_research_queue_excludes_done_items_from_pending():
    """Items checked with [x] must not appear under pending, even when
    they live under a stale ## Pending heading."""
    out = readers.read_research_queue(FIXTURES / "sample-research-queue.md")
    titles_pending = [item["title"] for item in out["pending"]]
    assert not any("Old completed topic" in t for t in titles_pending)
```

- [ ] **Step 7: Run the new test**

Run: `.venv/bin/pytest tests/test_readers.py::test_read_research_queue_excludes_done_items_from_pending -v`
Expected: PASS.

- [ ] **Step 8: Run the full readers test file to confirm no regressions**

Run: `.venv/bin/pytest tests/test_readers.py -v`
Expected: PASS, all tests green.

- [ ] **Step 9: Commit**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/readers.py tests/test_readers.py tests/fixtures/sample-research-queue.md
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
fix(readers): research queue regex must not match done items

Split _BULLET_RE into _BULLET_PENDING_RE (- [ ]) and _BULLET_DONE_RE
(- [x]). The old character class [ x] matched both unchecked and
checked items, surfacing completed research topics as live pending
tickets whenever the source file left a stale ## Pending header.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Refactor `read_lint_reports` to return parsed issues

**Files:**
- Modify: `lib/readers.py` (replace `read_lint_reports` body + add a section parser)
- Modify: `tests/fixtures/sample-lint-report.md` (replace with real-shape format)
- Modify: `tests/test_readers.py::test_read_lint_reports_returns_latest`

- [ ] **Step 1: Replace the lint fixture with the real-shape format**

Overwrite `tests/fixtures/sample-lint-report.md` with:

```markdown
# Knowledge Lint Report — 2026-05-12

_4 issues found (3 structural, 1 semantic)._

## CRITICAL (1)

- **contradiction** (T2): `knowledge/concepts/foo.md` — contradicts bar (source=sql)

## HIGH (1)

- **broken-wikilink** (T1): `knowledge/connections/baz.md` — concept_edges

## MEDIUM (1)

- **stale-frontmatter** (T2): `vault/qux/quux.md` — old format

## LOW (1)

- **duplicate-title** (T2): `concepts/dup.md` — same as concepts/dup-2.md
```

Note: no YAML frontmatter — that's matches the real reports (frontmatter was a planned but never-implemented convention).

- [ ] **Step 2: Write the new test that asserts parsed issue shape**

Replace `test_read_lint_reports_returns_latest` (lines 86-92) in `tests/test_readers.py` with:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_readers.py::test_read_lint_reports_returns_latest -v`
Expected: FAIL — `out["issues"]` missing (current return shape has only `raw_body`).

- [ ] **Step 4: Add a section-parser helper to readers.py**

Add immediately after the existing `_LINT_NAME_RE` constant (around line 246) in `lib/readers.py`:

```python
_LINT_BULLET_RE = re.compile(
    r"^- \*\*(?P<rule>[\w\-]+)\*\*\s*\((?P<tier>T\d+)\)\s*:\s*"
    r"`?(?P<path>[^`—]+?)`?\s*—\s*(?P<context>.+?)\s*$"
)
_LINT_SECTION_RE = re.compile(r"^##\s+(CRITICAL|HIGH|MEDIUM|LOW)\b", re.IGNORECASE)


def _parse_lint_sections(text: str) -> list[dict]:
    """Walk a lint-report body and emit one dict per bullet under each
    ## CRITICAL / HIGH / MEDIUM / LOW section.

    Severity comes from the section header; rule/tier/path/context come
    from the bullet itself.
    """
    issues: list[dict] = []
    current_severity: str | None = None
    for line in text.splitlines():
        head = _LINT_SECTION_RE.match(line)
        if head:
            current_severity = head.group(1).upper()
            continue
        if current_severity is None:
            continue
        m = _LINT_BULLET_RE.match(line.strip())
        if not m:
            continue
        issues.append({
            "severity": current_severity,
            "rule": m.group("rule"),
            "tier": m.group("tier"),
            "path": m.group("path").strip().strip("`"),
            "context": m.group("context").strip(),
        })
    return issues
```

- [ ] **Step 5: Rewrite `read_lint_reports` to use the new parser**

Replace `read_lint_reports` (lines 251-270 in the original file) with:

```python
def read_lint_reports(dir_path: Path) -> dict:
    """Find the most recent lint report; return summary + parsed issues."""
    empty = {"latest_date": None, "issues_total": 0, "issues_by_severity": {}, "issues": []}
    if not dir_path.exists():
        return empty
    dated: list[tuple[str, Path]] = []
    for p in dir_path.glob("*-lint-report.md"):
        m = _LINT_NAME_RE.search(p.name)
        if m:
            dated.append((m.group(1), p))
    if not dated:
        return empty
    dated.sort(reverse=True)
    latest_date, latest_path = dated[0]
    body = latest_path.read_text()
    issues = _parse_lint_sections(body)
    by_severity: dict[str, int] = {}
    for iss in issues:
        by_severity[iss["severity"]] = by_severity.get(iss["severity"], 0) + 1
    return {
        "latest_date": latest_date,
        "issues_total": len(issues),
        "issues_by_severity": by_severity,
        "issues": issues,
    }
```

Note: drops the `raw_body` field. Any downstream consumer that reads `raw_body` must be updated — the kanban composer is the only one; we rewrite it in Task 4.

- [ ] **Step 6: Run the lint reader test to confirm it passes**

Run: `.venv/bin/pytest tests/test_readers.py::test_read_lint_reports_returns_latest -v`
Expected: PASS.

- [ ] **Step 7: Run the full readers test file**

Run: `.venv/bin/pytest tests/test_readers.py -v`
Expected: PASS, all green.

- [ ] **Step 8: Run the kanban tests — they should currently FAIL** because the lint composer still expects `raw_body`

Run: `.venv/bin/pytest tests/test_kanban.py -v`
Expected: FAIL — `test_compose_tickets_includes_all_sources_private` and friends now break because `data["lint_reports"]["raw_body"]` is gone. **This is expected.** Task 4 will fix it. The plan defers the commit until Task 4 ties the loose end.

- [ ] **Step 9: No commit yet** — `lib/readers.py` and `lib/kanban.py` move together. Hold this change in the working tree; we'll commit Tasks 2 + 3 + 4 together at the end of Task 4.

---

## Task 3: Add the research title parser

**Files:**
- Modify: `lib/kanban.py` (new helper near top of file)
- Modify: `tests/test_kanban.py` (new tests)

- [ ] **Step 1: Add failing tests for the parser**

Append to `tests/test_kanban.py`:

```python
def test_parse_research_title_topic_prefix():
    raw = (
        "Topic 8 — OpenRouter Python integration patterns for the agents-sdk fleet. "
        "Cover: (1) auth header pattern... — done 2026-05-12 02:54 → [[20_projects/research/foo]]"
    )
    out = kanban._parse_research_title(raw)
    assert out["title"] == "Topic 8 — OpenRouter Python integration patterns for the agents-sdk fleet"
    assert "Cover: (1) auth header pattern" in out["details"]


def test_parse_research_title_short_question_passes_through():
    raw = "What are the practical differences between MLX and GGUF for 14B models?"
    out = kanban._parse_research_title(raw)
    assert out["title"] == raw
    assert out["details"] == raw


def test_parse_research_title_long_falls_back_to_truncation():
    raw = (
        "A very long single-sentence research question that runs past eighty characters "
        "and therefore has no Topic prefix and no internal sentence break for the parser to use"
    )
    out = kanban._parse_research_title(raw)
    assert len(out["title"]) <= 81  # 80 + "…"
    assert out["title"].endswith("…")
    assert out["details"] == raw


def test_parse_research_title_strips_done_link_tail():
    raw = "Quick topic. — done 2026-05-01 02:00 → [[20_projects/research/old-topic]]"
    out = kanban._parse_research_title(raw)
    assert "[[" not in out["title"]
    assert "done 2026-05" not in out["title"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_kanban.py::test_parse_research_title_topic_prefix -v`
Expected: FAIL — `_parse_research_title` does not exist.

- [ ] **Step 3: Add the parser to `lib/kanban.py`**

Insert immediately after the existing `_LINT_LINE_RE` line (around line 12) in `lib/kanban.py`:

```python
_TOPIC_PREFIX_RE = re.compile(r"^(Topic \d+[a-z]?\s+—\s+[^.]+)")
_DONE_TAIL_RE = re.compile(r"\s*—\s*done\s+\d{4}-\d{2}-\d{2}.*$")


def _parse_research_title(raw: str) -> dict:
    """Distill a research-queue prompt into a card-sized title.

    Order of rules:
        1. Strip the `— done DATE → [[wikilink]]` tail if present.
        2. If the body starts with `Topic N — Short Title.`, use everything
           up to (and not including) the first period.
        3. Else if the whole body is ≤ 80 chars, use it verbatim.
        4. Else truncate to 80 chars + `…`.

    Returns dict with `title` (display) and `details` (original prose,
    minus the done-tail, for v2 expand-on-hover).
    """
    cleaned = _DONE_TAIL_RE.sub("", raw).strip()
    m = _TOPIC_PREFIX_RE.match(cleaned)
    if m:
        title = m.group(1).strip()
    elif len(cleaned) <= 80:
        title = cleaned
    else:
        title = cleaned[:80].rstrip() + "…"
    return {"title": title, "details": cleaned}
```

Make sure `import re` is already at the top of `lib/kanban.py` — it is (line 8).

- [ ] **Step 4: Run the parser tests**

Run: `.venv/bin/pytest tests/test_kanban.py -k "_parse_research_title" -v`
Expected: PASS, all four new tests green.

- [ ] **Step 5: No commit yet** — bundle with Task 4.

---

## Task 4: Rewrite `compose_tickets` (research uses parser, lint uses parsed issues, eval dropped)

**Files:**
- Modify: `lib/kanban.py` (`compose_tickets` body)
- Modify: `tests/test_kanban.py` (rewrite the per-source assertions)

- [ ] **Step 1: Rewrite the test fixture in `tests/test_kanban.py` to match new shapes**

Replace the existing `_data()` helper (lines 6-37) with:

```python
def _data():
    return {
        "research_queue": {
            "pending": [
                {"title": "Topic 5 — OpenRouter routing config. Some long prose.",
                 "assigned_agent": None},
                {"title": "Short question that fits in a card?",
                 "assigned_agent": None},
            ],
            "in_flight": [
                {"title": "Topic 7 — FDE intake pattern. Long prose continues.",
                 "assigned_agent": "deep_researcher"},
            ],
            "done": [],
        },
        "lint_reports": {
            "latest_date": "2026-05-12",
            "issues_total": 4,
            "issues_by_severity": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 1},
            "issues": [
                {"severity": "CRITICAL", "rule": "contradiction", "tier": "T2",
                 "path": "knowledge/concepts/foo.md", "context": "contradicts bar"},
                {"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                 "path": "knowledge/connections/baz.md", "context": "concept_edges"},
                {"severity": "MEDIUM", "rule": "stale-frontmatter", "tier": "T2",
                 "path": "vault/qux.md", "context": "old format"},
                {"severity": "LOW", "rule": "duplicate-title", "tier": "T2",
                 "path": "concepts/dup.md", "context": "same as dup-2"},
            ],
        },
        "agent_runs": [],  # Task 5 will populate this for the eval tests
        "manual_tickets": {
            "todo": [{"title": "Bump synth eval suite to 12", "assigned_agent": None},
                     {"title": "Rotate ldr api token", "assigned_agent": "Sean"}],
            "in_progress": [{"title": "Substack post 2 draft", "assigned_agent": "Sean"}],
            "done": [],
        },
        "job_feed": {
            "total_postings": 4,
            "top_fit": [
                {"company": "Sierra", "title": "Agent PM", "fit_score": 91, "status": "new"},
                {"company": "Anthropic", "title": "FDE", "fit_score": 88, "status": "screen-scheduled"},  # noqa: E501
            ],
            "by_status": {"new": 1, "screen-scheduled": 1},
            "active_count": 3,
        },
    }
```

- [ ] **Step 2: Replace `test_compose_tickets_eval_failures_only`**

Replace the existing `test_compose_tickets_eval_failures_only` (lines 61-66) with a placeholder that will be filled in Task 5:

```python
def test_compose_tickets_eval_source_pending_for_task_5():
    """Eval-source assertions live in test_compose_failures_to_tickets_*
    after Task 5 wires agent_runs into compose_tickets."""
    pass
```

- [ ] **Step 3: Update `test_compose_tickets_includes_all_sources_private`** — eval temporarily drops out (Task 5 brings it back via runs)

Replace the assertion:

```python
def test_compose_tickets_includes_all_sources_private():
    tickets = kanban.compose_tickets(_data(), include_job_feed=True)
    sources = {t["source"] for t in tickets}
    # eval re-enters via agent_runs in Task 5
    assert sources == {"research", "lint", "manual", "feed"}
```

And the public variant similarly:

```python
def test_compose_tickets_excludes_job_feed_when_public():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    sources = {t["source"] for t in tickets}
    assert "feed" not in sources
    assert sources == {"research", "lint", "manual"}
```

- [ ] **Step 4: Add lint cap-20 + title-shape test**

Append to `tests/test_kanban.py`:

```python
def test_compose_tickets_lint_drains_severity_in_order():
    data = _data()
    # Inflate fixture: 5 CRITICAL, 30 HIGH, 50 MEDIUM
    extra = []
    for i in range(4):  # already 1 CRITICAL in fixture
        extra.append({"severity": "CRITICAL", "rule": "contradiction", "tier": "T2",
                      "path": f"c{i}.md", "context": "x"})
    for i in range(29):  # already 1 HIGH in fixture
        extra.append({"severity": "HIGH", "rule": "broken-wikilink", "tier": "T1",
                      "path": f"h{i}.md", "context": "x"})
    for i in range(49):  # already 1 MEDIUM
        extra.append({"severity": "MEDIUM", "rule": "stale-frontmatter", "tier": "T2",
                      "path": f"m{i}.md", "context": "x"})
    data["lint_reports"]["issues"] = (
        data["lint_reports"]["issues"][:3] + extra  # keep original ordering
    )
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    lint_tickets = [t for t in tickets if t["source"] == "lint"]
    assert len(lint_tickets) == 20
    # First 5 must be CRITICAL, then HIGH fills the rest
    severities = [t["_severity"] for t in lint_tickets]
    assert severities[:5] == ["CRITICAL"] * 5
    assert all(s == "HIGH" for s in severities[5:])


def test_compose_tickets_lint_title_uses_basename():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    lint = [t for t in tickets if t["source"] == "lint"][0]
    # basename only in the displayed title
    assert "/" not in lint["title"]
    # full path preserved in details
    assert "knowledge/concepts/foo.md" in lint["details"]


def test_compose_tickets_research_title_parsed():
    tickets = kanban.compose_tickets(_data(), include_job_feed=False)
    research = [t for t in tickets if t["source"] == "research"]
    titles = [t["title"] for t in research]
    # Topic-N prefix items collapse to short title
    assert "Topic 5 — OpenRouter routing config" in titles
    # Short questions pass through verbatim
    assert "Short question that fits in a card?" in titles
    # Full prose preserved in details for one of the Topic-N items
    topic_5 = next(t for t in research if t["title"].startswith("Topic 5"))
    assert "Some long prose" in topic_5["details"]
```

- [ ] **Step 5: Run the new tests — they should fail**

Run: `.venv/bin/pytest tests/test_kanban.py -k "lint_drains or lint_title or research_title_parsed or includes_all_sources or excludes_job_feed" -v`
Expected: FAIL — composer still uses old shapes.

- [ ] **Step 6: Rewrite `compose_tickets`**

Replace the entire function in `lib/kanban.py` (lines 20-96) with:

```python
def compose_tickets(data: dict, *, include_job_feed: bool) -> list[dict]:
    """Build a single list of tickets across all sources.

    Each ticket has: id, title, source, assigned_agent, column (filled by
    compute_columns), is_running (default False), created_at, moved_at, details,
    plus optional source-specific fields (_severity for lint, etc.).
    """
    out: list[dict] = []
    now = datetime.now(UTC).isoformat()

    # --- research --------------------------------------------------------
    rq = data.get("research_queue", {})
    for section_name, hint in [("pending", "pending"), ("in_flight", "in_flight")]:
        for item in rq.get(section_name, []):
            parsed = _parse_research_title(item["title"])
            out.append({
                "id": _stable_id("research", parsed["title"]),
                "title": parsed["title"],
                "source": "research",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": parsed["details"],
            })

    # --- lint (top 20, severity-drain) -----------------------------------
    lint = data.get("lint_reports", {})
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues = lint.get("issues", []) or []
    ordered = sorted(
        enumerate(issues),
        key=lambda pair: (severity_order.get(pair[1].get("severity"), 99), pair[0]),
    )
    for _idx, iss in ordered[:20]:
        from os.path import basename
        title = f"{iss['rule']} ({iss['tier']}) · {basename(iss['path'])}"
        out.append({
            "id": _stable_id("lint", f"{iss['severity']}|{iss['rule']}|{iss['path']}"),
            "title": title,
            "source": "lint",
            "assigned_agent": None,
            "_section_hint": "pending",
            "_severity": iss["severity"],
            "_tier": iss["tier"],
            "created_at": now, "moved_at": now,
            "details": f"{iss['path']} — {iss['context']}",
        })

    # --- eval (failures from agent_runs) ---------------------------------
    # Implemented in Task 5; passes through empty for now.
    runs = data.get("agent_runs") or []
    for ticket in _failures_to_tickets(runs):
        out.append(ticket)

    # --- manual ----------------------------------------------------------
    mt = data.get("manual_tickets", {})
    for section_name, hint in [("todo", "todo"), ("in_progress", "in_progress"), ("done", "done")]:
        for item in mt.get(section_name, []):
            out.append({
                "id": _stable_id("manual", item["title"]),
                "title": item["title"], "source": "manual",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now, "details": None,
            })

    # --- feed (private only) ---------------------------------------------
    if include_job_feed:
        for p in data.get("job_feed", {}).get("top_fit", []):
            title = f"{p['company']} · {p['title']}"
            out.append({
                "id": _stable_id("feed", title),
                "title": title, "source": "feed",
                "assigned_agent": "Sean",
                "_section_hint": p.get("status", "new"),
                "created_at": now, "moved_at": now,
                "details": f"fit {p.get('fit_score')}",
            })

    return out


def _failures_to_tickets(runs: list[dict]) -> list[dict]:
    """Stub — populated in Task 5. Returns [] so compose_tickets is callable."""
    return []
```

(`_failures_to_tickets` lands now as a stub so the import structure is stable; Task 5 fills the body.)

- [ ] **Step 7: Run the kanban tests**

Run: `.venv/bin/pytest tests/test_kanban.py -v`
Expected: PASS, all green (including the eval placeholder which just `pass`es).

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit Tasks 2 + 3 + 4 together**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/readers.py lib/kanban.py tests/fixtures/sample-lint-report.md tests/test_readers.py tests/test_kanban.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
feat(kanban): real-shape lint composer + research title parser

Three coupled changes that have to land together:

1. read_lint_reports now returns a parsed issues list, matching the
   vault's actual ## CRITICAL/HIGH/MEDIUM/LOW + **rule** (Tn) format.
   The old _LINT_LINE_RE in the composer matched 0 of 640 real issues.

2. _parse_research_title extracts Topic-N — Short Title prefixes (or
   falls back to first-sentence truncation at 80 chars). Full prose
   preserved in ticket.details for a future v2 expand-on-hover.

3. compose_tickets rebuilds around these: research uses the parser,
   lint drains severities CRITICAL→HIGH→MEDIUM→LOW capping at 20 cards
   total, eval is wired through a stub _failures_to_tickets (Task 5
   implements the body).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Implement `_failures_to_tickets` from agent_runs

**Files:**
- Modify: `lib/kanban.py` (`_failures_to_tickets` body)
- Modify: `tests/test_kanban.py` (eval tests)
- Modify: `build.py:51-72` (`_read_all_sources` — pass `agent_runs` into the data dict already; verify it's there)

- [ ] **Step 1: Verify `agent_runs` already flows into the data dict**

Run: `grep -n agent_runs /Users/seanwinslow/Code-Brain/agent-fleet-observability/build.py`
Expected: `"agent_runs": readers.read_run_history(...)` exists already (line ~54). If it does, no build.py change needed.

- [ ] **Step 2: Add failing tests for the failures composer**

Append to `tests/test_kanban.py`:

```python
def _run(agent, status, minutes_ago, notes=""):
    return {
        "agent": agent, "status": status,
        "ts": datetime.now(UTC) - timedelta(minutes=minutes_ago),
        "cost_usd": 0.0, "duration_ms": None, "turns": None,
        "mode": None, "notes": notes,
    }


def test_failures_to_tickets_one_per_unresolved_failure():
    runs = [
        _run("vault_indexer", "ok", 60 * 24),         # yesterday: ok
        _run("vault_indexer", "failed", 60 * 5),      # 5h ago: failed
        _run("vault_synthesizer", "failed", 60 * 3),  # 3h ago: failed
    ]
    out = kanban._failures_to_tickets(runs)
    agents = sorted(t["assigned_agent"] for t in out)
    assert agents == ["vault_indexer", "vault_synthesizer"]
    assert all(t["source"] == "eval" for t in out)


def test_failures_to_tickets_resolved_by_subsequent_success():
    runs = [
        _run("vault_indexer", "failed", 60 * 5),  # 5h ago: failed
        _run("vault_indexer", "ok", 60 * 2),      # 2h ago: recovered
    ]
    out = kanban._failures_to_tickets(runs)
    assert out == []


def test_failures_to_tickets_ages_off_after_7_days():
    runs = [
        _run("vault_indexer", "failed", 60 * 24 * 8),  # 8 days ago
    ]
    out = kanban._failures_to_tickets(runs)
    assert out == []


def test_failures_to_tickets_title_uses_notes_then_status():
    runs = [
        _run("agent_a", "failed", 30, notes="ConnectTimeout to backend"),
        _run("agent_b", "failed", 60),  # no notes
    ]
    out = sorted(kanban._failures_to_tickets(runs), key=lambda t: t["assigned_agent"])
    assert "ConnectTimeout" in out[0]["title"]
    assert out[0]["title"].startswith("agent_a failed:")
    assert "failed" in out[1]["title"]


def test_failures_to_tickets_title_truncates_at_60_chars():
    long_notes = "x" * 200
    runs = [_run("agent_a", "failed", 30, notes=long_notes)]
    out = kanban._failures_to_tickets(runs)
    # "agent_a failed: " is 16 chars; the tail must be 60 chars + "…"
    tail = out[0]["title"].split("failed: ", 1)[1]
    assert len(tail) <= 61
    assert tail.endswith("…")


def test_failures_to_tickets_section_hint_is_todo():
    runs = [_run("agent_a", "failed", 30)]
    out = kanban._failures_to_tickets(runs)
    assert out[0]["_section_hint"] == "todo"
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_kanban.py -k "failures_to_tickets" -v`
Expected: FAIL — stub returns [].

- [ ] **Step 4: Implement `_failures_to_tickets`**

Replace the stub in `lib/kanban.py` with:

```python
_ERR_STATUSES = {"error", "failed", "capped", "timeout"}
_OK_STATUSES = {"ok", "success", "completed", "passed"}
_FAILURE_WINDOW = timedelta(days=7)


def _failures_to_tickets(runs: list[dict]) -> list[dict]:
    """Emit one ticket per (agent × most-recent unresolved failure within 7 days).

    "Unresolved" = there is no `ok`/`success`/`completed`/`passed` run for the
    same agent at a timestamp AFTER the failure. Failures older than 7 days
    age off; subsequent successes resolve. Title format:
    "{agent} failed: {notes_or_status_word}" truncated to 60 chars + ….
    """
    now = datetime.now(UTC)
    cutoff = now - _FAILURE_WINDOW
    by_agent: dict[str, list[dict]] = {}
    for r in runs:
        if r["ts"] < cutoff:
            continue
        by_agent.setdefault(r["agent"], []).append(r)

    out: list[dict] = []
    for agent, agent_runs in by_agent.items():
        # Sort newest first so we find the latest failure quickly
        agent_runs.sort(key=lambda r: r["ts"], reverse=True)
        latest_failure: dict | None = None
        latest_success_ts = None
        for r in agent_runs:
            status = r["status"].lower()
            if status in _OK_STATUSES and latest_success_ts is None:
                latest_success_ts = r["ts"]
            if status in _ERR_STATUSES:
                latest_failure = r
                break
        if not latest_failure:
            continue
        # If any success exists after the failure timestamp, ticket is resolved
        if latest_success_ts is not None and latest_success_ts > latest_failure["ts"]:
            continue

        notes = (latest_failure.get("notes") or "").strip()
        tail = notes if notes else latest_failure["status"].lower()
        if len(tail) > 60:
            tail = tail[:60].rstrip() + "…"
        title = f"{agent} failed: {tail}"
        out.append({
            "id": _stable_id("eval", f"{agent}|{latest_failure['ts'].isoformat()}"),
            "title": title,
            "source": "eval",
            "assigned_agent": agent,
            "_section_hint": "todo",
            "created_at": latest_failure["ts"].isoformat(),
            "moved_at": latest_failure["ts"].isoformat(),
            "details": notes or None,
        })
    return out
```

- [ ] **Step 5: Restore the eval source check in the broader `compose_tickets` test**

In `tests/test_kanban.py`, update `test_compose_tickets_includes_all_sources_private` so it passes a failure run through:

```python
def test_compose_tickets_includes_all_sources_private():
    d = _data()
    d["agent_runs"] = [_run("vault_indexer", "failed", 60)]
    tickets = kanban.compose_tickets(d, include_job_feed=True)
    sources = {t["source"] for t in tickets}
    assert sources == {"research", "lint", "eval", "manual", "feed"}


def test_compose_tickets_excludes_job_feed_when_public():
    d = _data()
    d["agent_runs"] = [_run("vault_indexer", "failed", 60)]
    tickets = kanban.compose_tickets(d, include_job_feed=False)
    sources = {t["source"] for t in tickets}
    assert "feed" not in sources
    assert sources == {"research", "lint", "eval", "manual"}
```

Also delete the `test_compose_tickets_eval_source_pending_for_task_5` placeholder — it's no longer needed.

- [ ] **Step 6: Run the kanban test file**

Run: `.venv/bin/pytest tests/test_kanban.py -v`
Expected: PASS, all green.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/kanban.py tests/test_kanban.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
feat(kanban): eval source reads agent_runs failures, not last-run.md

evals/vault-synthesizer/last-run.md was specified in the design doc but
never produced by the synth eval suite. Replace with a 7-day rolling
read of failures from agent-run-history.csv: one ticket per (agent ×
unresolved failure), where 'unresolved' means no subsequent ok/success
run. Title: "{agent} failed: {notes_or_status}" capped at 60 chars.

Chip label stays "Eval"; no template, CSS, or anonymize changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `compute_agent_state` adapter

**Files:**
- Modify: `lib/aggregations.py` (new helper near `compute_fleet_status`)
- Modify: `tests/test_aggregations.py` (new tests)

- [ ] **Step 1: Add failing test**

Append to `tests/test_aggregations.py`:

```python
def test_compute_agent_state_maps_normalized_names_to_health():
    fleet_status = [
        {"agent": "vault_indexer", "health": "healthy"},
        {"agent": "vault-synthesizer", "health": "degraded"},  # CSV-style name
        {"agent": "deep_researcher", "health": "down"},
        {"agent": "flush", "health": "unknown"},
    ]
    out = aggregations.compute_agent_state(fleet_status)
    # Normalized: dash→underscore
    assert out["vault_indexer"] == "healthy"
    assert out["vault_synthesizer"] == "degraded"
    assert out["deep_researcher"] == "down"
    # unknown is kept (caller decides whether to render a dot)
    assert out["flush"] == "unknown"
```

(Ensure `from lib import aggregations` is already imported at the top of `tests/test_aggregations.py`. If not, add it.)

- [ ] **Step 2: Run the test to confirm failure**

Run: `.venv/bin/pytest tests/test_aggregations.py::test_compute_agent_state_maps_normalized_names_to_health -v`
Expected: FAIL — `compute_agent_state` does not exist.

- [ ] **Step 3: Add the helper to `lib/aggregations.py`**

Insert after `compute_fleet_status` (after the function body ending at the existing `return tiles`):

```python
def compute_agent_state(fleet_status: list[dict]) -> dict[str, str]:
    """Adapt fleet_status (list of per-agent tiles) into a dict keyed by
    normalized agent name. Used by the kanban template to render the
    agent-state dot on cards with the same source of truth as /fleet.
    """
    return {_norm_agent(t["agent"]): t["health"] for t in fleet_status}
```

- [ ] **Step 4: Wire into `compute_all`**

Find `compute_all` (around line 251 per the earlier grep). After the line `"fleet_status": compute_fleet_status(runs, agent_names),`, add a new entry:

```python
        "agent_state": compute_agent_state(compute_fleet_status(runs, agent_names)),
```

To avoid double-computing, refactor slightly — replace those two lines with:

```python
        # compute once, expose both shapes
        **({
            "fleet_status": (_fs := compute_fleet_status(runs, agent_names)),
            "agent_state": compute_agent_state(_fs),
        }),
```

If walrus-in-dict feels off, fall back to:

```python
    fs = compute_fleet_status(runs, agent_names)
    # ... earlier in the function, then in the returned dict:
    "fleet_status": fs,
    "agent_state": compute_agent_state(fs),
```

(Pick whichever fits the existing style of `compute_all` — read the function body first and match its idiom.)

- [ ] **Step 5: Run the test**

Run: `.venv/bin/pytest tests/test_aggregations.py::test_compute_agent_state_maps_normalized_names_to_health -v`
Expected: PASS.

- [ ] **Step 6: Run the full aggregations file + smoke test**

Run: `.venv/bin/pytest tests/test_aggregations.py tests/test_render_smoke.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/aggregations.py tests/test_aggregations.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
feat(agg): compute_agent_state — normalized name → fleet health

Thin adapter over compute_fleet_status so the kanban template can
render per-card agent dots from the same source of truth as the
fleet ribbon. No new logic; just a shape change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `compute_column_sparklines`

**Files:**
- Modify: `lib/aggregations.py` (new function + wire into `compute_all`)
- Modify: `tests/test_aggregations.py` (new tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_aggregations.py`:

```python
def test_compute_column_sparklines_has_todo_in_progress_done_only():
    out = aggregations.compute_column_sparklines([])
    assert set(out.keys()) == {"todo", "in_progress", "done"}
    # Backlog and Testing intentionally absent — no honest 7-day series


def test_compute_column_sparklines_counts_per_day_7_points():
    now = datetime.now(UTC)
    runs = [
        # 2 starts today, 1 failed yesterday, 1 ok 3 days ago
        {"agent": "a", "status": "started", "ts": now, "cost_usd": 0,
         "duration_ms": None, "turns": None, "mode": None, "notes": ""},
        {"agent": "a", "status": "started", "ts": now - timedelta(hours=2),
         "cost_usd": 0, "duration_ms": None, "turns": None, "mode": None, "notes": ""},
        {"agent": "b", "status": "failed", "ts": now - timedelta(days=1),
         "cost_usd": 0, "duration_ms": None, "turns": None, "mode": None, "notes": ""},
        {"agent": "c", "status": "ok", "ts": now - timedelta(days=3),
         "cost_usd": 0, "duration_ms": None, "turns": None, "mode": None, "notes": ""},
    ]
    out = aggregations.compute_column_sparklines(runs)
    # 7 data points each, oldest → newest (last index = today)
    assert len(out["todo"]) == 7
    assert len(out["in_progress"]) == 7
    assert len(out["done"]) == 7
    assert out["in_progress"][-1] == 2  # 2 starts today
    assert out["todo"][-2] == 1  # 1 failed yesterday
    assert out["done"][-4] == 1  # 1 ok 3 days ago
```

(Ensure `from datetime import UTC, datetime, timedelta` is at the top of `tests/test_aggregations.py`. Add if missing.)

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_aggregations.py -k "column_sparklines" -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement `compute_column_sparklines`**

Append to `lib/aggregations.py` (after `compute_agent_state`):

```python
def compute_column_sparklines(runs: list[dict]) -> dict[str, list[int]]:
    """7-day per-day series for ToDo / InProgress / Done columns.

    - todo:        count of `failed`/`error`/`capped`/`timeout` runs per day
    - in_progress: count of `started` runs per day
    - done:        count of `ok`/`success`/`completed`/`passed` runs per day

    Backlog and Testing are intentionally absent — we don't snapshot ticket
    state history daily, so there's no honest 7-day series for them.
    """
    now = datetime.now(UTC)
    todo = [0] * 7
    in_progress = [0] * 7
    done = [0] * 7
    err = {"failed", "error", "capped", "timeout"}
    ok = {"ok", "success", "completed", "passed"}
    for r in runs:
        delta_days = (now - r["ts"]).days
        if delta_days < 0 or delta_days >= 7:
            continue
        idx = 6 - delta_days  # oldest=0, today=6
        status = r["status"].lower()
        if status in err:
            todo[idx] += 1
        elif status == "started":
            in_progress[idx] += 1
        elif status in ok:
            done[idx] += 1
    return {"todo": todo, "in_progress": in_progress, "done": done}
```

- [ ] **Step 4: Wire into `compute_all`**

In `compute_all`, add a new dict entry after `"agent_state": ...`:

```python
        "column_sparklines": compute_column_sparklines(runs),
```

- [ ] **Step 5: Run the new tests**

Run: `.venv/bin/pytest tests/test_aggregations.py -k "column_sparklines" -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS, plus the new tests; ~62-64 total.

- [ ] **Step 7: Commit**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/aggregations.py tests/test_aggregations.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
feat(agg): compute_column_sparklines — 7-day series for ToDo/InProgress/Done

Per-day counts from agent-run-history: failures → todo column, started
→ in_progress, ok/success → done. Backlog and Testing intentionally
absent because no daily ticket-state snapshot exists yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Thread `agent_state` + column sparkline SVGs into render context

**Files:**
- Modify: `lib/render.py` (build sparkline SVGs in `_build_charts`; expose in `_common_context`)
- Modify: `tests/test_render_smoke.py` (assert new keys in rendered HTML)

- [ ] **Step 1: Add failing smoke assertion**

Append to `tests/test_render_smoke.py` (or modify the kanban smoke test if one exists — read the file first to find the right spot):

```python
def test_render_kanban_includes_agent_dot_and_column_spark(tmp_path):
    """Smoke: rendered kanban.html contains the new chrome."""
    # Reuse the harness used by the existing render_public smoke test;
    # if the file already defines a `_minimal_agg()` helper, use it.
    import json
    from lib import render
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    runs = [
        {"agent": "vault_indexer", "status": "failed",
         "ts": now - timedelta(hours=2), "cost_usd": 0.0,
         "duration_ms": None, "turns": None, "mode": None, "notes": "x"},
    ]
    # Hand-build the minimal agg the kanban view needs
    agg = _minimal_agg() if "_minimal_agg" in dir() else None
    if agg is None:
        # If the smoke test file doesn't have a helper, fall back to
        # building one inline matching the keys _common_context reads.
        # See render.py:_common_context for the list.
        from lib import aggregations
        agg = aggregations.compute_all({
            "agent_runs": runs, "synth_manifests": [], "gemini_spend": {},
            "council_spend": {}, "lint_reports": {}, "eval_last_run": {},
            "job_feed_db": {}, "job_feed_manifests": {}, "research_queue": {},
            "manual_tickets": {}, "target_companies": {}, "warm_intros": {},
            "agent_names": ["vault_indexer"],
        })
    tickets = [{
        "id": "x", "title": "vault_indexer failed: x", "source": "eval",
        "assigned_agent": "vault_indexer", "column": "todo", "is_running": False,
        "_section_hint": "todo", "details": None,
        "created_at": now.isoformat(), "moved_at": now.isoformat(),
    }]
    render.render_public(agg, tickets, tmp_path)
    html = (tmp_path / "kanban.html").read_text()
    assert "agent-dot" in html
    assert "column-spark" in html
```

(Read `tests/test_render_smoke.py` first to find any existing helper named `_minimal_agg` or similar and reuse it — match conventions. If the existing smoke test uses a different setup pattern, conform.)

- [ ] **Step 2: Run the test to confirm it fails**

Run: `.venv/bin/pytest tests/test_render_smoke.py -k "agent_dot_and_column_spark" -v`
Expected: FAIL — markers absent.

- [ ] **Step 3: Build sparkline SVGs in `_build_charts`**

In `lib/render.py`, inside `_build_charts` after the existing `eval_spark_svg = ...` line (around line 57), add:

```python
    col_spark = agg.get("column_sparklines", {})
    column_sparkline_svgs = {
        "todo": svg_charts.sparkline(
            col_spark.get("todo", []), width=48, height=12, color=svg_charts.ALERT),
        "in_progress": svg_charts.sparkline(
            col_spark.get("in_progress", []), width=48, height=12, color=svg_charts.AMBER),
        "done": svg_charts.sparkline(
            col_spark.get("done", []), width=48, height=12, color=svg_charts.OK),
    }
```

Then in the return dict at the bottom of `_build_charts`, add:

```python
        "column_sparkline_svgs": column_sparkline_svgs,
```

(Verify `svg_charts.ALERT`, `svg_charts.AMBER`, `svg_charts.OK` exist. From the earlier grep, `AMBER` and `OK` are present in svg_charts; check for `ALERT` and add a constant if missing. If the file uses different names — `RED`, `GREEN` — use those instead and verify by reading `lib/svg_charts.py:1-50` for the constants block.)

- [ ] **Step 4: Expose `agent_state` in `_common_context`**

In `lib/render.py`, inside `_common_context`'s returned dict, add:

```python
        "agent_state": agg.get("agent_state", {}),
```

- [ ] **Step 5: Run the smoke test (should still fail — template not updated yet)**

Run: `.venv/bin/pytest tests/test_render_smoke.py -k "agent_dot_and_column_spark" -v`
Expected: FAIL — Python side is wired but template still emits the old DOM. Task 9 closes the loop.

- [ ] **Step 6: No commit yet** — Task 9 lands the template change.

---

## Task 9: New kanban template — two-line card, agent dot, column sparkline

**Files:**
- Modify: `templates/partials/kanban_board.html`

- [ ] **Step 1: Replace the entire partial body** (the file is short)

Overwrite `templates/partials/kanban_board.html` with:

```html
{# Vars: tickets, is_private, agent_state (dict), column_sparkline_svgs (dict) #}
{% set chips = [
  ('research', 'Research'),
  ('lint', 'Lint'),
  ('eval', 'Eval'),
  ('manual', 'Manual'),
] %}
{% if is_private %}
  {% set chips = chips + [('feed', 'Job Feed')] %}
{% endif %}

<div class="kanban-filters">
  {% for src, label in chips %}
    {% set count = tickets|selectattr('source','equalto', src)|list|length %}
    <button class="filter-chip {{ src }}" data-source="{{ src }}" data-active="true">
      ● {{ label }} {{ count }}{% if src == 'feed' %} [private]{% endif %}
    </button>
  {% endfor %}
</div>

<div class="kanban-board">
  {% set columns = [
    ('backlog', 'Backlog'),
    ('todo', 'ToDo'),
    ('in_progress', 'InProgress'),
    ('testing', 'Testing'),
    ('done', 'Done'),
  ] %}
  {% for col_key, col_label in columns %}
    {% set col_tickets = tickets|selectattr('column','equalto', col_key)|list %}
    <div class="kanban-column" data-column="{{ col_key }}">
      <div class="kanban-column-header">
        <span class="column-label">{{ col_label }}</span>
        <span class="column-count">{{ col_tickets|length }}</span>
        {% if column_sparkline_svgs and col_key in column_sparkline_svgs %}
          <span class="column-spark">{{ column_sparkline_svgs[col_key] | safe }}</span>
        {% endif %}
      </div>
      {% for t in col_tickets %}
        <div class="ticket" data-source="{{ t.source }}" data-id="{{ t.id }}">
          <div class="ticket-title">
            {% if t.is_running %}<span class="pulse-dot"></span>{% endif %}
            {{ t.title }}
          </div>
          <div class="ticket-meta">
            {{ t.source }}
            {% if t.assigned_agent %}
              {% set state = agent_state.get(t.assigned_agent|lower|replace('-', '_'), 'unknown') %}
              · <span class="agent-dot agent-dot--{{ state }}"></span>@{{ t.assigned_agent }}
            {% endif %}
            {% if t._tier %} · {{ t._tier }}{% endif %}
            {% if t.details and t.source == 'feed' %} · {{ t.details }}{% endif %}
          </div>
        </div>
      {% endfor %}
      {% if col_tickets|length == 0 %}
        <div class="kanban-empty">Nothing in {{ col_label }} right now.</div>
      {% endif %}
    </div>
  {% endfor %}
</div>
```

- [ ] **Step 2: Run the smoke test — should now pass**

Run: `.venv/bin/pytest tests/test_render_smoke.py -v`
Expected: PASS.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 4: No commit yet** — pair with Task 10 (CSS) so the visual change lands atomically.

---

## Task 10: CSS for two-line card + agent dot + column sparkline

**Files:**
- Modify: `assets/styles.css`

- [ ] **Step 1: Update existing `.ticket` rule + add the new selectors**

Locate the current `.ticket { ... }` block (around line 573). Replace `.ticket` and `.ticket-meta` with:

```css
.ticket {
  display: block;
  background: var(--bg-base);
  border: 1px solid var(--hairline);
  border-left-width: 2px;
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
  transition: transform var(--t-fast) var(--ease-out),
              border-color var(--t-fast) var(--ease-out);
}
.ticket:hover { transform: translateY(-1px); border-color: var(--hairline-strong); }

.ticket-title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ticket-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.agent-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.agent-dot--healthy  { background: var(--accent-ok); }
.agent-dot--degraded { background: var(--accent-amber); }
.agent-dot--down     { background: var(--accent-alert); }
.agent-dot--unknown  { background: var(--text-tertiary); }

.kanban-column-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.column-spark {
  margin-left: auto;
  line-height: 0;
}

.kanban-empty {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
  padding: var(--space-3);
  text-align: center;
  font-style: italic;
}
```

(Read the existing `.kanban-column-header` rule first — if it already declares display/gap/etc., merge rather than duplicate. The grep showed it exists at line 564.)

- [ ] **Step 2: Run a build to render the visual change**

Run: `cd /Users/seanwinslow/Code-Brain/agent-fleet-observability && .venv/bin/python build.py --no-push`
Expected: build completes, `kanban.html` updated. Inspect the file:

```bash
grep -c 'class="ticket-title"' kanban.html
grep -c 'class="agent-dot' kanban.html
grep -c 'class="column-spark"' kanban.html
```
All three should be > 0.

- [ ] **Step 3: Visual sanity check**

Open `kanban.html` in a browser (e.g., `open kanban.html`) and confirm:
- Every card has a 2-line clamped title and a mono telemetry footer
- ToDo / InProgress / Done column headers each have a sparkline at the right edge
- Backlog and Testing have no sparkline (count only)
- Cards with an `@agent` token show a colored dot before the agent name

If anything looks wrong (e.g., sparkline pushes the count off-screen), iterate on CSS until it lands; commit only when it looks right.

- [ ] **Step 4: Run lint + format**

```bash
cd /Users/seanwinslow/Code-Brain/agent-fleet-observability && .venv/bin/ruff check . && .venv/bin/ruff format --check .
```
Expected: clean.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit Tasks 8 + 9 + 10 together**

```bash
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/render.py templates/partials/kanban_board.html assets/styles.css tests/test_render_smoke.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
feat(kanban): two-line card + agent dot + column sparklines

- Card chrome: Sora 13/600 title with 2-line clamp, JBMono 10px
  telemetry footer
- Agent dot: 6px circle keyed to compute_fleet_status health
  (healthy/degraded/down), reusing the fleet ribbon's source of truth
- Column header sparkline: 7-day series for ToDo/InProgress/Done
  via svg_charts.sparkline; Backlog/Testing show count only because
  we don't snapshot ticket-state history daily
- Empty-column microcopy in the design doc's voice

No new JS. No new dependencies. Page weight delta negligible.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Anonymize pass — ensure new fields survive the public render

**Files:**
- Read: `lib/anonymize.py`
- Modify (only if needed): `lib/anonymize.py`
- Modify (only if needed): `tests/test_anonymize.py`

- [ ] **Step 1: Read `lib/anonymize.py` to confirm what `public_pass` zeros**

Run: `cat /Users/seanwinslow/Code-Brain/agent-fleet-observability/lib/anonymize.py`
Note any zero-out of `column_sparklines`, `agent_state`, or `lint_reports.issues`.

- [ ] **Step 2: Add a regression test asserting the new fields pass through public**

Append to `tests/test_anonymize.py`:

```python
def test_public_pass_preserves_agent_state():
    agg = {
        "agent_state": {"vault_indexer": "healthy"},
        "column_sparklines": {"todo": [0]*7, "in_progress": [0]*7, "done": [0]*7},
        # ...minimal other keys public_pass touches
    }
    # Read public_pass first to see what other keys it requires; supply
    # neutral defaults for the rest. Then:
    out = anonymize.public_pass(agg)
    assert out["agent_state"] == {"vault_indexer": "healthy"}
    assert out["column_sparklines"]["todo"] == [0]*7
```

If `public_pass` requires more keys (it does — `job_feed`, `target_companies`, etc.), copy the harness from existing tests in `test_anonymize.py`.

- [ ] **Step 3: Run the test**

Run: `.venv/bin/pytest tests/test_anonymize.py -k "preserves_agent_state" -v`
- If PASS → no `anonymize.py` change needed; the new fields pass through by virtue of not being explicitly stripped.
- If FAIL because the fields are missing from the output dict → add explicit pass-through in `public_pass`:
  ```python
  out["agent_state"] = agg.get("agent_state", {})
  out["column_sparklines"] = agg.get("column_sparklines", {})
  ```

- [ ] **Step 4: Run the full suite + the build**

```bash
cd /Users/seanwinslow/Code-Brain/agent-fleet-observability && .venv/bin/pytest -q && .venv/bin/python build.py --no-push
```
Expected: tests PASS; build writes `index.html`, `kanban.html`, `data.json`. Open `kanban.html` and re-verify the visual.

- [ ] **Step 5: Commit (only if files changed)**

```bash
# Run git status first to see what changed
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability status

# If anonymize.py or test_anonymize.py changed:
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability add lib/anonymize.py tests/test_anonymize.py
git -C /Users/seanwinslow/Code-Brain/agent-fleet-observability commit -m "$(cat <<'EOF'
test(anonymize): pin agent_state + column_sparklines through public_pass

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: End-to-end verification

**Files:**
- (read-only) `index.html`, `kanban.html`, `data.json`

- [ ] **Step 1: Full clean build**

```bash
cd /Users/seanwinslow/Code-Brain/agent-fleet-observability && .venv/bin/python build.py --no-push -v 2>&1 | tail -30
```
Expected: build succeeds, log shows ticket counts from at least 3 sources (research, lint, manual), eval if any failures exist in the run log.

- [ ] **Step 2: Inspect `data.json` for ticket-source distribution**

```bash
.venv/bin/python -c "
import json
from collections import Counter
d = json.load(open('data.json'))
ts = d['tickets']
print('total:', len(ts))
print('by source:', Counter(t['source'] for t in ts))
print('by column:', Counter(t['column'] for t in ts))
print('research title lengths:', sorted({len(t['title']) for t in ts if t['source']=='research'}))
"
```
Expected:
- `by source` contains at least `research` and `lint`. `manual` appears with 0 unless you've added rows to `tickets.md`. `eval` appears if any agent had a recent unresolved failure.
- All research titles ≤ 80 chars OR end with `…`.

- [ ] **Step 3: Visual sanity in browser**

```bash
open kanban.html
```
Verify the §13 acceptance criteria from the spec:
- Every card fits the two-line shape
- ToDo / InProgress / Done columns have sparklines; Backlog / Testing don't
- Cards with `@agent` have a colored dot matching the fleet ribbon state for that agent
- `/fleet` (`index.html`) is unchanged

- [ ] **Step 4: Final lint + format pass**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
Expected: clean.

- [ ] **Step 5: Full test count**

Run: `.venv/bin/pytest -q 2>&1 | tail -3`
Expected: ≥ 63 tests, all PASS.

- [ ] **Step 6: Page-weight check**

```bash
wc -c index.html kanban.html
```
Expected: kanban.html under 50 KB pre-data (data is inline JSON only on `index.html` if at all; kanban.html is mostly markup).

- [ ] **Step 7: No commit** — verification only. The visible artifacts (`index.html`, `kanban.html`, `data.json`) regenerate at the next 06:00 build and commit themselves via the existing diff-and-commit logic in `build.py`.

---

## Out of scope (do not implement)

- Drag-to-reassign, agent write-back, `tickets.json` source-of-truth — v2 only
- Activity-timeline strip on `/kanban` — v2 only
- Hover-expand for full research prose — v2 only
- Daily ticket-count snapshot for Backlog/Testing sparklines — v2 only
- Reskinning the chip taxonomy (Knowledge/Engineering/Hunt facets) — v2 only
- Writing `evals/vault-synthesizer/last-run.md` from the synth suite — separate cross-repo project
