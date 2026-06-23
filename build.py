#!/usr/bin/env python3
"""Agent Fleet Observability Dashboard — build entry point.

Runs on Mac Mini cron at 06:00 ET daily.
Reads vault data, aggregates telemetry, renders two HTML passes
(public to repo root + private to ~/Sites/agent-fleet-private),
optionally diff-and-commits public output.

Usage:
  python build.py            # full build + git commit/push if changes
  python build.py --no-push  # build only, skip commit/push
  python build.py --dry-run  # print what would be done, write nothing
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from lib import aggregations, anonymize, kanban, readers, render  # noqa: F401 — render is used

logger = logging.getLogger("build")

REPO = Path(__file__).resolve().parent
VAULT = Path.home() / "Code-Brain/code-brain/vault"
PRIVATE_OUT = Path.home() / "Sites/agent-fleet-private"
EVAL_LAST_RUN = Path.home() / "Code-Brain/code-brain/evals/vault-synthesizer/last-run.md"

# Job-hunt-2026 markdown trackers for §4d live-wire panels
TARGET_COMPANIES_PATH = (
    Path.home()
    / "Code-Brain/code-brain/vault"
    / "20_projects/prj-job-hunt-2026/target-companies.md"
)
WARM_INTROS_PATH = (
    Path.home() / "Code-Brain/code-brain/vault/20_projects/prj-job-hunt-2026/warm-intros.md"
)

AGENT_NAMES = [
    "vault_indexer", "vault_synthesizer", "deep_researcher", "meta_agent",
    "daily_driver", "knowledge_lint", "flush", "job_feed",
]


def _read_all_sources() -> dict:
    """Read every data source the renderers need."""
    return {
        "agent_runs": readers.read_run_history(
            VAULT / "90_system/agent-logs/agent-run-history.csv"
        ),
        "synth_manifests": readers.read_synth_manifests(VAULT / "health"),
        "gemini_spend": readers.read_gemini_spend(
            VAULT / f"health/gemini-spend-{datetime.now(UTC).strftime('%Y-%m')}.json"
        ),
        "council_spend": readers.read_council_spend(VAULT / "health"),
        "lint_reports": readers.read_lint_reports(VAULT / "health"),
        "eval_last_run": readers.read_eval_last_run(EVAL_LAST_RUN),
        "job_feed_db": readers.read_job_feed_db(VAULT / ".job-feed.db"),
        "job_feed_manifests": readers.read_job_feed_manifests(VAULT / "health"),
        "research_queue": readers.read_research_queue(VAULT / "00_inbox/research-queue.md"),
        "manual_tickets": readers.read_manual_tickets(VAULT / "00_inbox/tickets.md"),
        # §4d live-wire (Sean's 2026-05-16 decision):
        "target_companies": readers.read_target_companies(TARGET_COMPANIES_PATH),
        "warm_intros": readers.read_warm_intros(WARM_INTROS_PATH),
        "agent_names": AGENT_NAMES,
    }


def _has_public_changes() -> bool:
    """Return True if the generated public files differ from git index."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "diff", "--quiet", "--",
         "index.html", "kanban.html", "data.json"],
        check=False,
    )
    return result.returncode != 0  # 1 = changes, 0 = no changes


def _sync_to_origin() -> None:
    """Reset the working branch to the latest origin/main before rendering.

    The build commits its rendered snapshot to the same repo it pushes, and
    GitHub PR merges (e.g. a design change touching the rendered files) advance
    origin/main between nightly runs. Without syncing first, the post-render
    push is rejected non-fast-forward and the public dashboard freezes until
    reconciled by hand (the 2026-06-18 freeze: PR #11 merged, then every push
    was rejected). Building on a fresh origin/main makes the push a clean
    fast-forward. Best-effort: a fetch/checkout failure (e.g. offline) is logged
    and the build proceeds — the push step still rebases as a backstop.
    """
    fetch = subprocess.run(
        ["git", "-C", str(REPO), "fetch", "origin", "main"], check=False,
    )
    if fetch.returncode != 0:
        logger.warning("git fetch origin main failed; building on current HEAD")
        return
    checkout = subprocess.run(
        ["git", "-C", str(REPO), "checkout", "-f", "-B", "main", "origin/main"],
        check=False,
    )
    if checkout.returncode != 0:
        logger.warning("git checkout origin/main failed; building on current HEAD")


def _commit_and_push() -> None:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    subprocess.run(
        ["git", "-C", str(REPO), "add", "index.html", "kanban.html", "data.json"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(REPO), "commit", "-m", f"snapshot {ts}"],
        check=True,
    )
    # Backstop: rebase our snapshot onto the latest origin/main before pushing,
    # in case a commit landed since _sync_to_origin() (or the sync was skipped
    # offline). Without this a bare push is rejected non-fast-forward and the
    # dashboard freezes. Mirrors the portfolio bridge's commit_and_push.
    rebase = subprocess.run(
        ["git", "-C", str(REPO), "pull", "--rebase", "--autostash", "origin", "main"],
        check=False,
    )
    if rebase.returncode != 0:
        subprocess.run(["git", "-C", str(REPO), "rebase", "--abort"], check=False)
        raise subprocess.CalledProcessError(rebase.returncode, "git pull --rebase origin main")
    subprocess.run(["git", "-C", str(REPO), "push"], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-push", action="store_true",
                        help="Build but skip git commit/push")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan, write nothing")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logger.info("build start: repo=%s vault=%s private_out=%s", REPO, VAULT, PRIVATE_OUT)

    if not VAULT.exists():
        logger.error("Vault path does not exist: %s", VAULT)
        return 2

    data = _read_all_sources()
    agg = aggregations.compute_all(data)

    # Build kanban tickets for each render mode
    tickets_private = kanban.compose_tickets(data, include_job_feed=True)
    tickets_private = kanban.compute_columns(tickets_private, data["agent_runs"])

    # Public pass: redact vault paths and home-prefixed absolute paths from
    # every ticket field before they're frozen on the dict. Anonymize at the
    # agg layer can't see ticket details — the privacy boundary needs to
    # extend into the ticket pipeline itself.
    tickets_public = kanban.compose_tickets(
        data, include_job_feed=False, redact_paths=True
    )
    tickets_public = kanban.compute_columns(tickets_public, data["agent_runs"])

    if args.dry_run:
        logger.info("DRY RUN: would render %d public tickets, %d private tickets",
                    len(tickets_public), len(tickets_private))
        logger.info("DRY RUN: would write to %s and %s", REPO, PRIVATE_OUT)
        return 0

    # Land on the latest origin/main before rendering so the post-build push is
    # a clean fast-forward even if a PR merged since the last run. Skipped for
    # --no-push local/dev builds so they never disturb the working branch.
    if not args.no_push:
        _sync_to_origin()

    # Public pass — repo root
    render.render_public(agg, tickets_public, REPO)
    logger.info("rendered public to %s/{index.html,kanban.html,data.json}", REPO)

    # Private pass — ~/Sites/
    PRIVATE_OUT.mkdir(parents=True, exist_ok=True)
    render.render_private(agg, tickets_private, PRIVATE_OUT)
    logger.info("rendered private to %s/{index.html,kanban.html,data.json}", PRIVATE_OUT)

    # Diff-and-commit public only if changed
    if args.no_push:
        logger.info("--no-push set, skipping commit + push")
        return 0
    if not _has_public_changes():
        logger.info("no public changes — skipping commit")
        return 0
    try:
        _commit_and_push()
        logger.info("committed and pushed public snapshot")
    except subprocess.CalledProcessError as exc:
        logger.error("git commit/push failed: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
