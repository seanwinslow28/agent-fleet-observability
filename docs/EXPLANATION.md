# EXPLANATION.md

A 4Q comprehension artifact (Nate B. Jones) for the Agent Fleet Observability Dashboard. The explanation that travels with the work: what this is, why this approach, what would break, what I learned.

---

## What is this?

A public board where my agent fleet has to answer, every morning, whether it still works, with dated evidence. Eight cron-scheduled agents (vault indexer, synthesizer, deep researcher, meta-agent, daily driver, knowledge lint, flush, job feed) generate about 30 runs a day across local and cloud models, scattering their evidence across twelve files. Without one surface, every night is a trust-fall: did the synthesizer run, did the eval pass, did the budget hold?

The dashboard makes the fleet inspectable in 30 seconds. A nightly build on a Mac Mini reads the twelve sources, aggregates, and renders twice: a public pass that commits itself and deploys to [fleet.seanwinslow.com](https://fleet.seanwinslow.com), and a private mirror that stays on local disk. The hero number counts nights since the last caught regression, because the board exists to make failure the headline, not a footnote.

## Why this approach?

**A static nightly print-run, not a live SaaS dashboard.** I rejected a hosted app with a database and auth. The fleet is local-first and $0-cloud by design; a server would be the most expensive and most fragile component in a system whose whole argument is cheap reliability. A static render has no runtime to crash and no auth to leak, and its history is git history: every snapshot is a commit, so the evidence is dated by the same mechanism that publishes it.

**Two render passes instead of one page with permissions.** The public page proves the fleet works; the private mirror carries what the public pass must never see (job-hunt data). I considered auth-gated sections on one page and threw the idea out. Privacy here is structural. The public render pass never reads the private sources at all, because a permission check can be misconfigured, and a read that never happens cannot leak. (It still leaked once anyway; see below.)

**Stdlib plus Jinja2 plus inline SVG. No framework, no Chart.js.** About 5,200 lines including tests. A JS charting stack would have been the conventional pick, but the charts are nightly artifacts, not interactive widgets; inline SVG keeps the page under 50 KB pre-data and keeps the whole system inspectable by one person in one sitting.

## What would break?

These are live, knowingly accepted risks, not fixed defects.

**1. The board relies on its own build to report its own death.** The entire pipeline is one launchd job on one Mac Mini: no failover machine, no external freshness alarm. If the Mini dies, the board does not go red. It goes quietly stale, "Live" label intact, serving its last good morning indefinitely. I accept this because the $0/local-first constraint is the design thesis, and an external uptime monitor would be a second system I'd then have to keep honest. The mitigation is the build stamp printed on the page (a reader on 2026-08-28 saw "2026-08-28 10:00 UTC"): staleness is visible to anyone who looks at the date, but the board cannot announce it, and a reader who trusts the "Live" label without checking the stamp will be wrong.

**2. The failure mode already fired once, inverted.** On 2026-08-28 I diagnosed the board as 17 days stale and opened a ticket to restart the build. The pipeline was healthy. My local clone hadn't been fetched since 2026-08-11, and I measured the board's freshness from a stale mirror of it. An observability system whose argument is dated evidence got misjudged by an undated copy of itself. The accepted residue: nothing in the system prevents that misread from happening again. The defense is a working rule (measure against origin or the live site, never a local checkout), which is discipline, not enforcement.

**3. Privacy is structural, and structure has failed before.** On 2026-05-21 a dedupe change put nineteen home-directory paths on the public board before redaction caught up. The boundary held everywhere except the one code path that bypassed it. The fix shipped. The accepted risk is the shape of the incident: every new aggregation is a new chance to route private data around the structural boundary, and the guard is review plus tests, not a mechanism that makes the leak impossible.

**4. The tests can silently age.** Two aggregation tests failed in 2026-08 because their fixtures aged out of the 7- and 30-day windows, a failure mode the test file itself had predicted in a docstring. I fixed it by injecting a frozen clock (2026-08-28), but the pattern generalizes: a system whose semantics are "the last N days" will keep growing checks that rot on a timer, and each new one has to remember the lesson.

## What did I learn?

**The regression that mattered was silent, and dated evidence is the antidote.** For nine consecutive nights the vault synthesizer wrote zero concepts while three layers of monitoring said "ok". The eval suite caught it on day ten. This board is the generalization of that incident: the point is not pretty charts, it's that an agent fleet will fail quietly unless something forces every night's evidence into one dated, public place.

**Honest displays have to be designed; defaults flatter.** The natural dashboard shows successes. Making "nights since the last caught regression" the hero number, and letting it reset publicly (as it did on 2026-08-26), was a deliberate inversion, and it is the single design choice this board is actually about.

**The stale-clone incident taught me the meta-lesson.** I built a system to stop trusting undated claims about the fleet, then made an undated claim about the system. Provenance discipline doesn't transfer by osmosis. Every measurement needs its own "measured against what, when."
