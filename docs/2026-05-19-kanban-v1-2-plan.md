---
name: Kanban v1.2 — Card Distillation + Multi-Source Enrichment Plan
description: Step-by-step plan for tightening kanban tickets (headline + date subheadline, click-to-modal for prose), wiring the eval emitter to last-run.md cases, and folding in the material v1.1 followups before the locked v2 gate trips.
type: plan
parent: docs/2026-05-15-agent-fleet-dashboard-design.md
created: 2026-05-19
---

# Kanban v1.2 Implementation Plan

> **Naming note.** The design doc §11 "v2" = the interactive-write-back kanban (gated on 1+ recruiter engagement OR 4 weeks live). That gate has **not** tripped yet. This plan ships a smaller refresh — kanban **v1.2** — that addresses two real UX gaps observed in the 2026-05-18 snapshot:
> 1. Tickets render full prose (the Topic 8 OpenRouter card is ~800 chars; the screenshot shows a 20-line card)
> 2. Several ticket sources silently render 0 (`tickets.md` is empty; eval emitter only reads `agent_runs` failures, not `evals/vault-synthesizer/last-run.md` failing cases as the design specs)
>
> This plan also folds in the **material** items from [docs/2026-05-18-kanban-v1-1-followups.md](2026-05-18-kanban-v1-1-followups.md) (status-set consolidation, per-source dates in subheadline, lint tier de-dup) and the highest-value polish items. Locked v2 (interactive write-back) stays gated.

> **Three decisions locked with Sean on 2026-05-19:**
> 1. Subheadline = parsed date (or empty when the source has no per-item date). No prose subheadline.
> 2. Full prose revealed via **click-to-modal** (not hover, not inline `<details>`). Modal is keyboard-accessible (Escape + backdrop click).
> 3. Task 9 seeds `vault/00_inbox/tickets.md` with the section skeleton (in addition to writing the schema doc in this repo).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tight, compact kanban cards (bold headline + small date below) sourced from every documented input, with full prose accessible via click-to-modal.

**Architecture:** Extend the ticket dict with `headline` (bold display) + `subheadline` (date string, may be `""`) + `details` (full prose for the modal). Add an eval-case emitter that pulls failing cases from `eval_last_run` (matching design §3e). Consolidate `_ERR_STATUSES`/`_OK_STATUSES` into a single module. Update the kanban template to render headline + subheadline and stash details on `data-details` for a tiny modal JS to read. `title` is preserved as a back-compat alias of `headline` for `data.json` consumers.

**Tech Stack:** Python 3.12, pytest, Jinja2 templates, hand-rolled CSS (no JS framework). Vanilla JS modal (~40 lines). No new runtime dependencies.

---

## File Structure

| Path | Responsibility | Action |
|---|---|---|
| `lib/statuses.py` | Single source of truth for `ERR_STATUSES`, `OK_STATUSES` | **CREATE** |
| `lib/kanban.py` | Ticket composer + column rules; add eval-case emitter; structured headline/subheadline | **MODIFY** |
| `lib/aggregations.py` | Replace local status-set literals with imports from `lib.statuses` (2 call sites) | **MODIFY** |
| `templates/partials/kanban_board.html` | Render `headline` + `subheadline`; drop redundant `(Tn)` in lint title; emit `data-details` attribute; render the modal shell once at the bottom | **MODIFY** |
| `assets/kanban-modal.js` | Click-to-modal: ticket click → fill modal → show; Escape + backdrop close | **CREATE** |
| `templates/kanban.html` | Add `<script src="assets/kanban-modal.js" defer></script>` | **MODIFY** |
| `assets/styles.css` | New `.ticket-headline` / `.ticket-subheadline` rules; modal overlay/dialog/close-button styles | **MODIFY** |
| `tests/test_kanban.py` | New tests: headline split, subheadline-as-date, eval-case emitter, empty-runs, status case-norm, multi-failure-same-agent | **MODIFY** |
| `tests/test_render_smoke.py` | Assert the rendered HTML contains the new headline/subheadline classes and a modal shell with `data-details` attributes on tickets | **MODIFY** |
| `docs/manual-tickets-schema.md` | Schema doc for the manual-tickets vault file | **CREATE** |
| `~/Code-Brain/claude-code-superuser-pack/vault/00_inbox/tickets.md` | Vault file — seed with empty section skeleton | **MODIFY (vault)** |
| `docs/2026-05-18-kanban-v1-1-followups.md` | Mark items closed by this plan | **MODIFY** |

Each file has one responsibility. The vault file is the only edit outside this repo — Sean explicitly approved seeding it (decision #3).

---

## Task 1: Consolidate status sets into `lib/statuses.py`

**Why first:** Closes followups §1 (the only flagged architectural item). Subsequent tasks import from here, so doing it first keeps later diffs small.

**Files:**
- Create: `lib/statuses.py`
- Modify: `lib/kanban.py:126-128`
- Modify: `lib/aggregations.py:50-51` and `lib/aggregations.py:131-132`
- Test: `tests/test_kanban.py` (existing tests must still pass — no new test for this task; existing kanban + aggregations tests are the regression net)

- [ ] **Step 1: Create `lib/statuses.py`**

```python
"""Single source of truth for agent-run terminal status sets.

Kept in its own module so kanban.py + aggregations.py can import from one
place; adding a new terminal status only needs one edit. See
docs/2026-05-18-kanban-v1-1-followups.md §1 for the motivation.
"""
from __future__ import annotations

ERR_STATUSES: frozenset[str] = frozenset({"error", "failed", "capped", "timeout"})
OK_STATUSES: frozenset[str] = frozenset({"ok", "success", "completed", "passed"})
```

- [ ] **Step 2: Run the existing test suite — must stay green**

Run: `.venv/bin/pytest -q`
Expected: 55 tests pass (no regressions).

- [ ] **Step 3: Replace the module-level constants in `lib/kanban.py`**

In `lib/kanban.py` near the top (after imports), replace:

```python
_ERR_STATUSES = {"error", "failed", "capped", "timeout"}
_OK_STATUSES = {"ok", "success", "completed", "passed"}
```

with:

```python
from lib.statuses import ERR_STATUSES, OK_STATUSES
```

Then in `_failures_to_tickets`, change `_OK_STATUSES` → `OK_STATUSES` and `_ERR_STATUSES` → `ERR_STATUSES` (two references).

- [ ] **Step 4: Replace the locals in `lib/aggregations.py`**

In `compute_fleet_status` (around line 50), delete the two local set literals and use the imports. In `compute_column_sparklines` (around line 131), delete `err` / `ok` locals likewise. Add `from lib.statuses import ERR_STATUSES, OK_STATUSES` at the top of the file. Update all internal references in those two functions accordingly.

- [ ] **Step 5: Re-run the test suite**

Run: `.venv/bin/pytest -q`
Expected: 55 pass.

- [ ] **Step 6: Commit**

```bash
git add lib/statuses.py lib/kanban.py lib/aggregations.py
git commit -m "refactor(kanban): consolidate ERR/OK status sets into lib/statuses.py"
```

---

## Task 2: `_parse_research_title` returns `{headline, details}` with empty-input guard (TDD)

**Why:** Today the function returns `{title, details}`. We rename `title` → `headline` to match the new uniform schema, drop the "next sentence" extraction (decision #1 — subheadline is the date, not prose), and add the empty-input guard from the followups doc.

**Files:**
- Modify: `lib/kanban.py:13-38` (`_parse_research_title`)
- Modify: `lib/kanban.py:60-69` (research branch of `compose_tickets`)
- Test: `tests/test_kanban.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kanban.py`:

```python
def test_parse_research_title_returns_headline_and_details():
    out = kanban._parse_research_title(
        "Topic 5 — OpenRouter routing config. Some long prose continues here."
    )
    assert out["headline"] == "Topic 5 — OpenRouter routing config"
    assert out["details"].startswith("Topic 5")
    assert "Some long prose" in out["details"]
    # No more `title` or `subheadline` keys from this function
    assert "subheadline" not in out


def test_parse_research_title_short_input_no_truncation():
    out = kanban._parse_research_title("Short question that fits?")
    assert out["headline"] == "Short question that fits?"
    assert "…" not in out["headline"]


def test_parse_research_title_strips_done_tail():
    out = kanban._parse_research_title(
        "Topic 12 — Foo bar. Details. — done 2026-05-16 02:46 → [[wikilink]]"
    )
    assert out["headline"] == "Topic 12 — Foo bar"
    # Done-tail stripped from details too
    assert "done 2026-05-16" not in out["details"]
    assert "wikilink" not in out["details"]


def test_parse_research_title_empty_input_guard():
    """Followups: previously returned headline="" for empty/whitespace input."""
    result = kanban._parse_research_title("   ")
    assert result["headline"] == "(no title)"
    assert result["details"] == "   "  # raw preserved


def test_research_ticket_uses_headline_and_empty_subheadline():
    """Pending research items have no per-item date → empty subheadline."""
    data = _data()
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    topic5 = next(t for t in tickets if t["source"] == "research"
                  and t["headline"].startswith("Topic 5"))
    assert topic5["headline"] == "Topic 5 — OpenRouter routing config"
    assert topic5["subheadline"] == ""
    assert topic5["title"] == topic5["headline"]  # back-compat
    # Full prose retained for the click-to-modal payload
    assert "Some long prose" in topic5["details"]
```

- [ ] **Step 2: Run the tests — must FAIL**

Run: `.venv/bin/pytest tests/test_kanban.py -k "parse_research_title or research_ticket_uses_headline" -v`
Expected: FAIL — current function returns `{title, details}` and the empty-input case returns `headline=""`.

- [ ] **Step 3: Rewrite `_parse_research_title`**

Replace the function body in `lib/kanban.py` (around line 17-38) with:

```python
def _parse_research_title(raw: str) -> dict:
    """Distill a research-queue prompt into a card-sized headline + full details.

    Returns:
        {
          "headline": short distilled title (≤ 80 chars, no trailing prose),
          "details": full cleaned prose, minus the "— done DATE → wikilink" tail.
        }

    Rules:
      1. Empty/whitespace input → headline="(no title)", details=raw or "".
      2. Strip `— done DATE → [[wikilink]]` tail if present.
      3. If body starts with `Topic N — Short Title.`, headline = that prefix
         (everything up to and not including the first period).
      4. Else if body is ≤ 80 chars, headline = body verbatim.
      5. Else truncate to 80 chars + `…`.
    """
    if not raw or not raw.strip():
        return {"headline": "(no title)", "details": raw or ""}
    cleaned = _DONE_TAIL_RE.sub("", raw).strip()
    if not cleaned:
        return {"headline": "(no title)", "details": raw}
    m = _TOPIC_PREFIX_RE.match(cleaned)
    if m:
        headline = m.group(1).strip()
    elif len(cleaned) <= 80:
        headline = cleaned
    else:
        headline = cleaned[:80].rstrip() + "…"
    return {"headline": headline, "details": cleaned}
```

- [ ] **Step 4: Update the research branch of `compose_tickets`**

In `compose_tickets` (around line 60-69), replace the research block:

```python
    # --- research --------------------------------------------------------
    rq = data.get("research_queue", {})
    for section_name, hint in [("pending", "pending"), ("in_flight", "in_flight")]:
        for item in rq.get(section_name, []):
            parsed = _parse_research_title(item["title"])
            headline = parsed["headline"]
            out.append({
                "id": _stable_id("research", headline),
                "title": headline,          # back-compat alias for data.json consumers
                "headline": headline,
                "subheadline": "",          # pending research has no per-item date
                "source": "research",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": parsed["details"],
            })
```

- [ ] **Step 5: Run the tests — must PASS**

Run: `.venv/bin/pytest tests/test_kanban.py -k "parse_research_title or research_ticket_uses_headline" -v`
Expected: 5 PASS.

- [ ] **Step 6: Run the full kanban test suite**

Run: `.venv/bin/pytest tests/test_kanban.py -q`
Expected: All pass. (Existing assertions on `title` still work — we set `title = headline`.)

- [ ] **Step 7: Commit**

```bash
git add lib/kanban.py tests/test_kanban.py
git commit -m "feat(kanban): research tickets use headline + details with empty-input guard"
```

---

## Task 3: Extend headline/subheadline/details schema to lint, eval-from-agent-runs, manual, feed (TDD)

**Why:** Uniform schema across all sources so the template renders one consistent card layout. Subheadline = the source's relevant date (decision #1). This also closes the followups §template-polish item "Tier redundancy on lint cards" — we move `(Tn)` out of the headline.

**Files:**
- Modify: `lib/kanban.py` — lint, manual, feed branches of `compose_tickets`; `_failures_to_tickets`
- Test: `tests/test_kanban.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kanban.py`:

```python
def test_lint_ticket_headline_strips_tier_subheadline_has_report_date():
    data = _data()
    # _data() sets lint_reports["latest_date"] = "2026-05-12"
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    crit = next(t for t in tickets if t["source"] == "lint"
                and "foo.md" in t["headline"])
    assert crit["headline"] == "contradiction · foo.md"
    assert "(T2)" not in crit["headline"]
    assert crit["subheadline"] == "2026-05-12"
    assert crit["_tier"] == "T2"  # still on the dict for meta line / future use
    assert "contradicts bar" in crit["details"]


def test_eval_failure_ticket_subheadline_is_failure_date():
    runs = [_run("vault_synthesizer", "failed", minutes_ago=30, notes="cap-hit")]
    data = {**_data(), "agent_runs": runs}
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    fail = next(t for t in tickets if t["source"] == "eval")
    assert fail["headline"].startswith("vault_synthesizer failed")
    # Subheadline is the failure timestamp date (YYYY-MM-DD)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    assert fail["subheadline"] == today
    # Full notes preserved in details for the modal
    assert "cap-hit" in (fail["details"] or "")


def test_manual_ticket_has_empty_subheadline():
    data = _data()
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    manual = next(t for t in tickets if t["source"] == "manual")
    assert manual["headline"] == manual["title"]
    assert manual["subheadline"] == ""  # tickets.md has no per-item date


def test_feed_ticket_subheadline_is_first_seen_date_or_empty():
    """Feed subheadline = first_seen_at date when present, else empty."""
    data = _data()
    # Augment one feed row with first_seen_at
    data["job_feed"]["top_fit"][0]["first_seen_at"] = "2026-05-15T08:30:00Z"
    tickets = kanban.compose_tickets(data, include_job_feed=True)
    sierra = next(t for t in tickets if t["source"] == "feed"
                  and t["headline"].startswith("Sierra"))
    assert sierra["headline"] == "Sierra · Agent PM"
    assert sierra["subheadline"] == "2026-05-15"
    # The second feed row had no first_seen_at → empty subheadline
    anthropic = next(t for t in tickets if t["source"] == "feed"
                     and t["headline"].startswith("Anthropic"))
    assert anthropic["subheadline"] == ""
```

- [ ] **Step 2: Run the tests — must FAIL**

Run: `.venv/bin/pytest tests/test_kanban.py -k "lint_ticket_headline or eval_failure_ticket_sub or manual_ticket_has or feed_ticket_subheadline" -v`
Expected: 4 FAIL.

- [ ] **Step 3: Update the lint emitter**

In `lib/kanban.py`, replace the lint block (around line 71-91):

```python
    # --- lint (top 20, severity-drain) -----------------------------------
    lint = data.get("lint_reports", {})
    lint_date = lint.get("latest_date") or ""
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues = lint.get("issues", []) or []
    ordered = sorted(
        enumerate(issues),
        key=lambda pair: (severity_order.get(pair[1].get("severity"), 99), pair[0]),
    )
    for _idx, iss in ordered[:20]:
        headline = f"{iss['rule']} · {basename(iss['path'])}"
        out.append({
            "id": _stable_id("lint", f"{iss['severity']}|{iss['rule']}|{iss['path']}"),
            "title": headline,
            "headline": headline,
            "subheadline": lint_date,
            "source": "lint",
            "assigned_agent": None,
            "_section_hint": "pending",
            "_severity": iss["severity"],
            "_tier": iss["tier"],
            "created_at": now, "moved_at": now,
            "details": f"{iss['path']} — {iss['context']}",
        })
```

- [ ] **Step 4: Update `_failures_to_tickets`**

In `lib/kanban.py`, replace the title + return block at the bottom of `_failures_to_tickets` (around line 168-183):

```python
        notes = (latest_failure.get("notes") or "").strip()
        status_word = latest_failure["status"].lower()
        headline = f"{agent} failed: {status_word}"
        out.append({
            "id": _stable_id("eval", f"{agent}|{latest_failure['ts'].isoformat()}"),
            "title": headline,
            "headline": headline,
            "subheadline": latest_failure["ts"].strftime("%Y-%m-%d"),
            "source": "eval",
            "assigned_agent": agent,
            "_section_hint": "todo",
            "created_at": latest_failure["ts"].isoformat(),
            "moved_at": latest_failure["ts"].isoformat(),
            "details": notes or None,
        })
```

- [ ] **Step 5: Update the manual + feed emitters**

Manual block (around line 98-108):

```python
    mt = data.get("manual_tickets", {})
    for section_name, hint in [("todo", "todo"), ("in_progress", "in_progress"), ("done", "done")]:
        for item in mt.get(section_name, []):
            title = item["title"]
            out.append({
                "id": _stable_id("manual", title),
                "title": title,
                "headline": title,
                "subheadline": "",
                "source": "manual",
                "assigned_agent": item.get("assigned_agent"),
                "_section_hint": hint,
                "created_at": now, "moved_at": now,
                "details": None,
            })
```

Feed block (around line 110-121):

```python
    if include_job_feed:
        for p in data.get("job_feed", {}).get("top_fit", []):
            headline = f"{p['company']} · {p['title']}"
            first_seen = (p.get("first_seen_at") or "")[:10]  # YYYY-MM-DD prefix
            out.append({
                "id": _stable_id("feed", headline),
                "title": headline,
                "headline": headline,
                "subheadline": first_seen,
                "source": "feed",
                "assigned_agent": "Sean",
                "_section_hint": p.get("status", "new"),
                "created_at": now, "moved_at": now,
                "details": f"fit {p.get('fit_score')}",
            })
```

- [ ] **Step 6: Run the new tests — must PASS**

Run: `.venv/bin/pytest tests/test_kanban.py -k "lint_ticket_headline or eval_failure_ticket_sub or manual_ticket_has or feed_ticket_subheadline" -v`
Expected: 4 PASS.

- [ ] **Step 7: Run the full kanban + render-smoke suite**

Run: `.venv/bin/pytest tests/test_kanban.py tests/test_render_smoke.py -q`
Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add lib/kanban.py tests/test_kanban.py
git commit -m "feat(kanban): uniform headline + date-subheadline + details across all sources"
```

---

## Task 4: Add eval-case ticket emitter from `eval_last_run` (TDD)

**Why:** Design doc §3e says eval tickets = "Failing eval cases from `evals/vault-synthesizer/last-run.md`". Today the eval branch only emits from `agent_runs` failures. Failing eval *cases* (e.g., `case-7-broken-wikilink-detection`) never become tickets. This task closes the design gap.

**Files:**
- Modify: `lib/kanban.py:93-96` (eval branch of `compose_tickets`) + new helper `_eval_cases_to_tickets`
- Test: `tests/test_kanban.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kanban.py`:

```python
def test_eval_cases_become_tickets():
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 7, "failed": 2, "skipped": 1, "total_cases": 10,
            "cases": [
                {"id": "case-1-broken-wikilink", "category": "lint", "status": "passed"},
                {"id": "case-7-cycle-detect",    "category": "lint", "status": "failed"},
                {"id": "case-9-concept-merge",   "category": "synth", "status": "failed"},
                {"id": "case-10-stale-frontmatter", "category": "lint", "status": "skipped"},
            ],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    eval_tix = [t for t in tickets if t["source"] == "eval"]
    headlines = {t["headline"] for t in eval_tix}
    assert "eval failed: case-7-cycle-detect" in headlines
    assert "eval failed: case-9-concept-merge" in headlines
    # Passed + skipped cases must NOT become tickets
    assert not any("case-1-broken" in h for h in headlines)
    assert not any("case-10-stale" in h for h in headlines)


def test_eval_case_subheadline_is_run_date_when_run_id_is_dated():
    data = {
        **_data(),
        "eval_last_run": {
            "passed": 9, "failed": 1, "skipped": 0, "total_cases": 10,
            "cases": [{"id": "case-3", "category": "synth", "status": "failed"}],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    case_tix = [t for t in tickets if t["source"] == "eval"
                and t["_eval_case_id"] == "case-3"]
    assert len(case_tix) == 1
    # Subheadline = first 10 chars of run_id when it parses as a date
    assert case_tix[0]["subheadline"] == "2026-05-18"


def test_eval_cases_and_agent_run_failures_coexist():
    runs = [_run("deep_researcher", "failed", minutes_ago=10, notes="timeout 900s")]
    data = {
        **_data(),
        "agent_runs": runs,
        "eval_last_run": {
            "passed": 9, "failed": 1, "skipped": 0, "total_cases": 10,
            "cases": [{"id": "case-3", "category": "synth", "status": "failed"}],
            "run_id": "2026-05-18-run",
        },
    }
    tickets = kanban.compose_tickets(data, include_job_feed=False)
    headlines = {t["headline"] for t in tickets if t["source"] == "eval"}
    assert any("deep_researcher failed" in h for h in headlines)
    assert any("case-3" in h for h in headlines)
```

- [ ] **Step 2: Run the tests — must FAIL**

Run: `.venv/bin/pytest tests/test_kanban.py -k "eval_cases or eval_case_subheadline" -v`
Expected: 3 FAIL.

- [ ] **Step 3: Add the `_eval_cases_to_tickets` helper**

In `lib/kanban.py`, after `_failures_to_tickets`, add:

```python
_RUN_ID_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _eval_cases_to_tickets(eval_last_run: dict) -> list[dict]:
    """Emit one ticket per failing eval case in evals/vault-synthesizer/last-run.md.

    Design doc §3e: "Failing eval cases from evals/vault-synthesizer/last-run.md".
    Only `status == "failed"` rows become tickets; passed/skipped/unknown are
    silently dropped. Each ticket's headline is `eval failed: {case_id}`;
    subheadline is the first 10 chars of run_id when it looks date-shaped
    (YYYY-MM-DD…), else empty.
    """
    now = datetime.now(UTC).isoformat()
    out: list[dict] = []
    run_id = eval_last_run.get("run_id") or ""
    subheadline = run_id[:10] if _RUN_ID_DATE_RE.match(run_id) else ""
    for case in eval_last_run.get("cases", []) or []:
        if (case.get("status") or "").lower() != "failed":
            continue
        case_id = case.get("id") or ""
        if not case_id:
            continue
        category = case.get("category") or ""
        headline = f"eval failed: {case_id}"
        out.append({
            "id": _stable_id("eval-case", f"{case_id}|{run_id or 'current'}"),
            "title": headline,
            "headline": headline,
            "subheadline": subheadline,
            "source": "eval",
            "assigned_agent": None,
            "_section_hint": "todo",
            "_eval_case_id": case_id,
            "created_at": now, "moved_at": now,
            "details": f"{case_id} ({category}) failed in eval run {run_id or 'current'}",
        })
    return out
```

- [ ] **Step 4: Wire the helper into `compose_tickets`**

Replace the eval block (around line 93-96):

```python
    # --- eval (agent_runs failures + failing eval cases) -----------------
    runs = data.get("agent_runs") or []
    out.extend(_failures_to_tickets(runs))
    out.extend(_eval_cases_to_tickets(data.get("eval_last_run", {}) or {}))
```

- [ ] **Step 5: Run the new tests — must PASS**

Run: `.venv/bin/pytest tests/test_kanban.py -k "eval_cases or eval_case_subheadline" -v`
Expected: 3 PASS.

- [ ] **Step 6: Run the full kanban + render-smoke suite**

Run: `.venv/bin/pytest tests/test_kanban.py tests/test_render_smoke.py -q`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add lib/kanban.py tests/test_kanban.py
git commit -m "feat(kanban): emit eval-case tickets from eval_last_run failing cases"
```

---

## Task 5: Update kanban template — headline, subheadline, data-details, modal shell (TDD)

**Why:** The data layer is ready; now the UI catches up. Headline is the bold 2-line clamp; subheadline is a small mono date underneath; full prose lives in a `data-details` attribute so the modal JS (Task 6) can read it. Modal markup is emitted **once** at the end of the partial.

**Files:**
- Modify: `templates/partials/kanban_board.html`
- Test: `tests/test_render_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_render_smoke.py`:

```python
def test_kanban_template_renders_headline_subheadline_and_modal_shell(tmp_path):
    """Kanban board uses .ticket-headline + .ticket-subheadline and emits a modal shell."""
    from lib import aggregations, kanban, render
    data = {
        "research_queue": {"pending": [
            {"title": "Topic 99 — Demo prompt. With prose body that should land in details.",
             "assigned_agent": None},
        ], "in_flight": [], "done": []},
        "lint_reports": {"latest_date": "2026-05-19", "issues_total": 0,
                         "issues_by_severity": {}, "issues": []},
        "manual_tickets": {"todo": [], "in_progress": [], "done": []},
        "agent_runs": [], "eval_last_run": {"cases": []},
        "job_feed": {"total_postings": 0, "by_status": {}, "top_fit": [], "active_count": 0},
        "synth_manifests": [], "gemini_spend": {"total_usd": 0, "run_count": 0, "tiers": {}},
        "council_spend": {"month_total_usd": 0, "day_count": 0, "days": []},
        "job_feed_manifests": {"latest": None, "last_7": []},
        "target_companies": {"tier_1": [], "tier_2": [], "tier_3": [], "by_status": {}, "total": 0},
        "warm_intros": {"active": [], "prospecting": [], "second_degree": [], "total": 0},
        "agent_names": ["vault_synthesizer"],
    }
    agg = aggregations.compute_all(data)
    tickets = kanban.compute_columns(
        kanban.compose_tickets(data, include_job_feed=False), data["agent_runs"]
    )
    out = tmp_path / "out"
    render.render_public(agg, tickets, out)
    html = (out / "kanban.html").read_text()
    assert 'class="ticket-headline"' in html
    # The Topic 99 ticket carries its full prose on data-details for the modal JS
    assert "data-details=" in html
    assert "With prose body" in html  # the details payload
    # Modal shell rendered once at the bottom of the partial
    assert 'id="ticket-modal"' in html
    assert "Topic 99 — Demo prompt" in html
```

- [ ] **Step 2: Run the test — must FAIL**

Run: `.venv/bin/pytest tests/test_render_smoke.py -k "headline_subheadline_and_modal" -v`
Expected: FAIL — current template still uses `.ticket-title` and emits no modal shell.

- [ ] **Step 3: Rewrite the ticket markup + add the modal shell**

Replace the body of `templates/partials/kanban_board.html` from line 39 onward (the `{% for t in col_tickets %}` block through end of file) with:

```jinja
      {% for t in col_tickets %}
        <button type="button" class="ticket" data-source="{{ t.source }}"
                data-id="{{ t.id }}"
                data-details="{{ (t.details or '') }}"
                data-headline="{{ t.headline or t.title }}"
                data-subheadline="{{ t.subheadline or '' }}"
                aria-haspopup="dialog">
          <div class="ticket-headline">
            {% if t.is_running %}<span class="pulse-dot"></span>{% endif %}
            {{ t.headline or t.title }}
          </div>
          {% if t.subheadline %}
            <div class="ticket-subheadline">{{ t.subheadline }}</div>
          {% endif %}
          <div class="ticket-meta">
            {{ t.source }}
            {% if t.assigned_agent %}
              {% set state = (agent_state or {}).get(t.assigned_agent|lower|replace('-', '_'), 'unknown') %}
              · <span class="agent-dot agent-dot--{{ state }}"></span>@{{ t.assigned_agent }}
            {% endif %}
            {% if t._tier %} · {{ t._tier }}{% endif %}
          </div>
        </button>
      {% endfor %}
      {% if col_tickets|length == 0 %}
        <div class="kanban-empty">Nothing in {{ col_label }} right now.</div>
      {% endif %}
    </div>
  {% endfor %}
</div>

<div id="ticket-modal" class="ticket-modal" hidden aria-hidden="true" role="dialog"
     aria-modal="true" aria-labelledby="ticket-modal-headline">
  <div class="ticket-modal__backdrop" data-modal-close></div>
  <div class="ticket-modal__dialog" role="document">
    <button type="button" class="ticket-modal__close" data-modal-close
            aria-label="Close ticket details">×</button>
    <div class="ticket-modal__source" id="ticket-modal-source"></div>
    <h2 class="ticket-modal__headline" id="ticket-modal-headline"></h2>
    <div class="ticket-modal__subheadline" id="ticket-modal-subheadline"></div>
    <div class="ticket-modal__details" id="ticket-modal-details"></div>
  </div>
</div>
```

Note: changed `<div class="ticket">` → `<button class="ticket">` so click + keyboard activation are native (Enter + Space). Jinja's `autoescape` ensures `data-details` is HTML-safe.

- [ ] **Step 4: Run the new render-smoke test — must PASS**

Run: `.venv/bin/pytest tests/test_render_smoke.py -k "headline_subheadline_and_modal" -v`
Expected: PASS.

- [ ] **Step 5: Run the full render-smoke + kanban suite**

Run: `.venv/bin/pytest tests/test_render_smoke.py tests/test_kanban.py -q`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add templates/partials/kanban_board.html tests/test_render_smoke.py
git commit -m "feat(kanban): render headline + date subheadline; emit modal shell"
```

---

## Task 6: Click-to-modal JS

**Why:** Vanilla JS, ~40 lines. Reads `data-details` off the clicked ticket and populates the modal. Closes on Escape or backdrop click. Restores focus to the originating ticket on close (a11y).

**Files:**
- Create: `assets/kanban-modal.js`
- Modify: `templates/kanban.html` — add `<script>` tag

- [ ] **Step 1: Create `assets/kanban-modal.js`**

```javascript
// Kanban click-to-modal — vanilla JS, ~40 lines.
// Reads data-* attributes off the clicked ticket; populates the modal; restores
// focus to the originating ticket on close. Escape + backdrop click also close.

(function () {
  "use strict";

  function init() {
    const modal = document.getElementById("ticket-modal");
    if (!modal) return;
    const elHeadline = modal.querySelector("#ticket-modal-headline");
    const elSub = modal.querySelector("#ticket-modal-subheadline");
    const elSource = modal.querySelector("#ticket-modal-source");
    const elDetails = modal.querySelector("#ticket-modal-details");
    let lastTrigger = null;

    function open(ticket) {
      lastTrigger = ticket;
      elHeadline.textContent = ticket.dataset.headline || "";
      elSub.textContent = ticket.dataset.subheadline || "";
      elSource.textContent = ticket.dataset.source || "";
      elDetails.textContent = ticket.dataset.details || "(no details)";
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
      const closeBtn = modal.querySelector(".ticket-modal__close");
      if (closeBtn) closeBtn.focus();
    }

    function close() {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
      if (lastTrigger) {
        lastTrigger.focus();
        lastTrigger = null;
      }
    }

    document.addEventListener("click", function (ev) {
      const ticket = ev.target.closest(".ticket");
      if (ticket && document.contains(ticket)) {
        // Don't fire when click originated inside the modal itself
        if (modal.contains(ticket)) return;
        ev.preventDefault();
        open(ticket);
        return;
      }
      if (ev.target.matches("[data-modal-close]")) {
        close();
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !modal.hidden) {
        close();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
```

- [ ] **Step 2: Wire the script into `templates/kanban.html`**

In `templates/kanban.html` near the existing `<script src="assets/kanban-filter.js"></script>` line, add directly after it:

```html
  <script src="assets/kanban-modal.js" defer></script>
```

- [ ] **Step 3: Manual smoke test in the browser**

```bash
.venv/bin/python build.py --no-push -v
open kanban.html
```

Verify:
- Clicking any ticket opens the modal with the full details.
- Escape closes the modal.
- Clicking the backdrop closes it.
- After close, keyboard focus returns to the originating ticket (Tab from there should hit the next ticket).

- [ ] **Step 4: Commit**

```bash
git add assets/kanban-modal.js templates/kanban.html
git commit -m "feat(kanban): vanilla-JS click-to-modal for full ticket details"
```

---

## Task 7: CSS — clamp headline, style subheadline as small mono date, style modal

**Why:** Visual delivery of v1.2. Without CSS the markup is unstyled prose with no modal styling.

**Files:**
- Modify: `assets/styles.css:573-614`

- [ ] **Step 1: Replace `.ticket-title` rule with `.ticket-headline` + `.ticket-subheadline`**

In `assets/styles.css`, replace lines 593-614 (the `.ticket-title` and `.ticket-meta` rules) with:

```css
.ticket-headline {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-align: left;
}
.ticket-subheadline {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
.ticket-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}
```

- [ ] **Step 2: Update `.ticket` to behave as a button**

The ticket element changed from `<div>` to `<button>` in Task 5. Find the existing `.ticket` rule at line 573 and append (do NOT rewrite — just add):

```css
.ticket {
  /* … existing properties … */
  display: block;        /* override button's inline-block default */
  width: 100%;
  font: inherit;         /* drop the browser button font */
  text-align: left;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}
.ticket:focus-visible {
  outline: 2px solid var(--accent-amber);
  outline-offset: 2px;
}
```

- [ ] **Step 3: Add modal styles**

Append to `assets/styles.css` (end of file):

```css
.ticket-modal[hidden] { display: none; }
.ticket-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
}
.ticket-modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(2px);
}
.ticket-modal__dialog {
  position: relative;
  background: var(--bg-panel);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  max-width: 560px;
  width: 100%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.8);
}
.ticket-modal__close {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.ticket-modal__close:hover { color: var(--text-primary); border-color: var(--text-tertiary); }
.ticket-modal__source {
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.ticket-modal__headline {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  margin: 0;
}
.ticket-modal__subheadline {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
  font-variant-numeric: tabular-nums;
}
.ticket-modal__details {
  margin-top: var(--space-3);
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
```

- [ ] **Step 4: Rebuild + eyeball**

```bash
.venv/bin/python build.py --no-push -v
open kanban.html
```

Verify:
- Cards are visibly compact — bold headline, small mono date underneath, meta line at the bottom.
- Lint cards: no `(T1)` in headline; tier still in meta line.
- Clicking a ticket opens the modal with the full prose.

- [ ] **Step 5: Run render-smoke suite**

Run: `.venv/bin/pytest tests/test_render_smoke.py -q`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add assets/styles.css
git commit -m "style(kanban): compact headline + mono-date subheadline + modal styling"
```

---

## Task 8: Add the followups' minor-polish test gaps (TDD)

**Why:** Closes the test gaps listed in followups §Tests with structural-but-untested invariants.

**Files:**
- Modify: `tests/test_kanban.py`

- [ ] **Step 1: Append the gap-filling tests in one block**

```python
def test_failures_to_tickets_empty_runs_returns_empty():
    """Followups: explicit contract — empty input → empty output."""
    assert kanban._failures_to_tickets([]) == []


def test_failures_to_tickets_status_case_normalized():
    """Followups: status comparison must be .lower()-aware."""
    runs = [
        {"agent": "x", "status": "FAILED", "ts": datetime.now(UTC),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "shouty"},
    ]
    out = kanban._failures_to_tickets(runs)
    assert len(out) == 1
    assert out[0]["source"] == "eval"


def test_failures_to_tickets_multiple_failures_same_agent_picks_latest():
    """Followups: with no intervening success, the newest failure wins."""
    base = datetime.now(UTC)
    runs = [
        {"agent": "x", "status": "failed", "ts": base - timedelta(hours=6),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "old"},
        {"agent": "x", "status": "failed", "ts": base - timedelta(hours=1),
         "cost_usd": 0.0, "duration_ms": None, "turns": None, "notes": "new"},
    ]
    out = kanban._failures_to_tickets(runs)
    assert len(out) == 1
    # Newest failure survives — its notes show up in details
    assert out[0]["details"] == "new"


def test_compose_tickets_all_empty_inputs_returns_empty_list():
    """Followups: cheap safety net for the all-empty-inputs path."""
    assert kanban.compose_tickets({}, include_job_feed=False) == []
```

- [ ] **Step 2: Run the tests — must all PASS**

Run: `.venv/bin/pytest tests/test_kanban.py -k "empty_runs or case_normalized or multiple_failures or all_empty_inputs" -v`
Expected: 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_kanban.py
git commit -m "test(kanban): close v1.1 followup test gaps (empty-runs, case-norm, latest-failure)"
```

---

## Task 9: Bootstrap manual tickets — schema doc in repo + skeleton in vault

**Why:** Manual chip always shows `0` because `vault/00_inbox/tickets.md` is 0 bytes. Sean explicitly approved seeding it (decision #3).

**Files:**
- Create: `docs/manual-tickets-schema.md`
- Modify (vault): `~/Code-Brain/claude-code-superuser-pack/vault/00_inbox/tickets.md`

- [ ] **Step 1: Create the schema doc**

Write `docs/manual-tickets-schema.md`:

```markdown
# Manual tickets — vault file schema

The dashboard reads `vault/00_inbox/tickets.md` (path defined in `build.py:67`)
to populate the Manual chip on the kanban board. The file is parsed by
`lib.readers.read_manual_tickets`, which splits on `## ` headers and matches
plain `-` bullets under each section.

## Expected structure

```markdown
## Todo

- A short ticket title here — assigned: Sean
- Another todo item without an assignee

## In Progress

- Substack post 2 draft — assigned: Sean

## Done

- Reset launchd plist permissions — assigned: meta_agent
```

## Rules

- Section headers MUST be `## Todo`, `## In Progress`, `## Done` (case-insensitive).
- One ticket per `- ` bullet. Sub-bullets are ignored.
- Optional ` — assigned: {agent}` suffix sets the `assigned_agent` field.
- Empty file → Manual chip shows `0`. That is the correct behavior, not a bug.

The dashboard rebuilds at 06:00 ET daily, or run `make build` from this repo
for an on-demand render.
```

- [ ] **Step 2: Seed the vault file with the section skeleton**

Show the user the exact file you're about to write **before** writing it, and pause for confirmation (this is a vault edit, outside the repo). If approved, write `~/Code-Brain/claude-code-superuser-pack/vault/00_inbox/tickets.md`:

```markdown
---
type: manual-tickets
description: Hand-curated Manual lane for the Agent Fleet Observability kanban board. One ticket per `-` bullet under the appropriate section. See agent-fleet-observability/docs/manual-tickets-schema.md for the parser rules.
---

# Manual tickets

Sean's hand-curated kanban entries. Parser is `lib.readers.read_manual_tickets`
in the agent-fleet-observability repo. Empty sections are fine; the chip will
show 0 until items land here.

## Todo

## In Progress

## Done
```

- [ ] **Step 3: Verify the build still works**

```bash
.venv/bin/python build.py --no-push -v
grep "filter-chip manual" kanban.html | head -2
```

Expected: Manual count still shows `0` (no bullets yet, but the file parses cleanly).

- [ ] **Step 4: Commit the repo-side change**

```bash
git add docs/manual-tickets-schema.md
git commit -m "docs(kanban): document manual tickets vault file schema"
```

(The vault edit is not in this repo; no commit there.)

---

## Task 10: Close out followups + verification

**Why:** Mark the v1.1 followups items this plan closes, so the next reader knows what's left, and one final integration check.

**Files:**
- Modify: `docs/2026-05-18-kanban-v1-1-followups.md`

- [ ] **Step 1: Run the full test suite one final time**

Run: `.venv/bin/pytest -q`
Expected: All pass (prior 55 + ~15 new tests added in Tasks 2, 3, 4, 5, 8 = ~70).

- [ ] **Step 2: Run a full build (no push)**

Run: `.venv/bin/python build.py --no-push -v`
Expected: `index.html`, `kanban.html`, `data.json` written to repo root + `~/Sites/agent-fleet-private/`.

- [ ] **Step 3: Final visual smoke**

```bash
open kanban.html
```

Acceptance:
- Cards are compact (≤ ~80 px collapsed). Bold headline + small mono date.
- Lint headlines: `contradiction · foo.md` (no `(T2)`); tier still in meta line.
- Research headlines: `Topic N — Title` (no prose subheadline; pending items have no date).
- Click any ticket → modal with full prose. Escape closes. Backdrop closes. Focus restores.
- Manual chip still `0` (vault `tickets.md` has skeleton but no items yet).
- Eval chip includes failing eval cases when `eval_last_run` has any.

- [ ] **Step 4: Update the followups doc**

In `docs/2026-05-18-kanban-v1-1-followups.md`, prepend a "Closed by v1.2" section before the "Material" heading:

```markdown
## Closed by v1.2 (this plan: 2026-05-19)

- §1 Status sets consolidation → `lib/statuses.py` (Task 1)
- Edge case: `_parse_research_title` empty-input guard (Task 2)
- Template polish: tier redundancy on lint cards removed (Task 3)
- Tests: empty-runs, status case-norm, multi-failure-same-agent, all-empty-inputs (Task 8)
- Template polish: per-source dates now surfaced as subheadline (Tasks 3, 4)

The remaining followup items (status case-norm test for `_failures_to_tickets`,
multi-bullet `_parse_lint_sections` test, naming refactors, `_LINT_BULLET_RE`
em-dash docstring, `_stable_id` severity-discriminator docstring) are still
open — none blocks v1.2 ship.
```

- [ ] **Step 5: Commit**

```bash
git add docs/2026-05-18-kanban-v1-1-followups.md
git commit -m "docs(followups): mark v1.2-closed items"
```

- [ ] **Step 6: Inspect the v1.2 commit series**

```bash
git log --oneline main..HEAD
```

Expected: 10 atomic commits. Use `make deploy` when ready to push the snapshot, or open a PR for review first.

---

## v2 (locked, deferred) — still gated

This plan deliberately does NOT touch:

- Interactive write-back kanban (`tickets.json` source of truth, agent runtime queue-awareness, drag-to-reassign UI). Gate: 1+ recruiter engagement attributed to v1 OR 4 weeks live. Tracked in `docs/project_agent_fleet_dashboard_kanban_v2.md`.
- Public archive page beyond 7 days (design doc §11). Done column 7-day rule still suffices.
- Knowledge graph deep-dive panel.

When the v2 gate trips, a new plan will be written off the v2 deferred-work memory.

---

## Self-Review

**Spec coverage:**
- ✅ "Smaller headline" — Tasks 2, 3, 5, 7 (bold 2-line clamp)
- ✅ "Parsed date subheadline" — Tasks 3, 4 (each source's relevant date; empty when none available)
- ✅ "Click-to-modal" — Tasks 5, 6, 7 (vanilla JS, Escape + backdrop close, focus restore)
- ✅ "Multi-source enrichment" (eval-cases from last-run.md) — Task 4
- ✅ "Manual tickets perception fix" — Task 9 (schema doc + vault skeleton)
- ✅ Material v1.1 followups: §1 status sets (Task 1), tier dedup (Task 3), per-source dates (Tasks 3+4), test gaps (Task 8), empty-input guard (Task 2)

**Placeholder scan:** None. Every code step has the full content. Every test step shows the assertion. Every CSS rule is complete. The JS file is full.

**Type consistency:**
- All emitters return ticket dicts containing `id, title, headline, subheadline, source, assigned_agent, _section_hint, created_at, moved_at, details` plus source-specific `_severity / _tier / _eval_case_id`. Verified across Tasks 2, 3, 4.
- `title == headline` everywhere (backwards compat for `data.json` consumers).
- `subheadline` is always a string (`""` when no date is available). Template uses `{% if t.subheadline %}` to skip empty subheadlines.
- `details` is `Optional[str]` (manual tickets pass `None`). The template renders `(t.details or '')` into `data-details`, and the modal JS shows `(no details)` if empty.
- `ERR_STATUSES`, `OK_STATUSES` are `frozenset[str]` — immutable singletons.
