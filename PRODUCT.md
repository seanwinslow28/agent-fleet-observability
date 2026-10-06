# PRODUCT.md

## What it is

A dashboard over Sean Winslow's second brain and the agents that work in it overnight. One app, two modes:

| | Private: the command center | Public: the showcase |
|---|---|---|
| Who | Sean, on his phone and laptop | anyone who visits `fleet.seanwinslow.com` |
| Runs | on his Mac Mini, reachable only over his own private network | a static site |
| Reads | the brain's files, live, every time a page loads | a showcase bundle: real past nights Sean picked and sanitized |
| Does | records Sean's decisions as files in the brain | replays the same screens; a visitor's clicks change nothing but their own browser |

The private mode comes first. The showcase is built after the first weeks of real use, from nights that actually happened.

## Who it's for, and why

**Sean, every morning.** Overnight, agents work the tickets he queued the evening before. A checker the agents can't edit tests each result and files a card in one of four lanes: Verified (every check passed), Unverified-done (the agent says done, but no check could confirm it), Blocked (stopped short, with a reason), or Needs-decision (a yes or no only Sean can give). At about 6 a.m., often on his phone and before his day job, Sean has a few minutes to see what ran, what needs him, and to label each finished piece of work at about three minutes a card.

His labels are the point. Every one becomes a row in the eval set that the checker's AI judge is measured against, so the morning review has to be quick enough to do every day and honest enough to trust:

- **One card at a time, one question at a time.** The card leads with the evidence (which checks passed and one plain sentence about what happened), then the answer, then a map from each claim to the quote that backs it. Everything else waits under "More details", or in the audio.
- **Unverified-done never looks like Verified.** Finished-without-proof is an outline; only proven work gets a solid stamp.
- **Sean answers before the judge.** The judge's verdict stays hidden until his label is saved, so his labels stay a fair test of the judge.

**Visitors, second.** The showcase shows how the system works on real nights, including the ones where the checker caught an agent's made-up quote. It shows only tickets Sean marked open and picked by hand. Nothing private is copied into it.

## What it never does

- **It never starts work.** Work starts only in the night run. The dashboard writes Sean's decisions (labels, accept, send back, drop) and nothing else.
- **It keeps no state of its own.** Every decision is a file write in the brain, so the brain stays the single source of truth.
- **The repo holds code, never data.** The private mode reads the brain at runtime on the Mini; the public build reads only the bundle. The test cards in `tests/fixtures/` are invented.
- **Nothing publishes on a schedule.** Sean publishes the showcase by hand.

## Pages

| Page | Status |
|---|---|
| Review: the morning cards | built |
| Desk: last night, what needs Sean, the machinery's health | next, during the first weeks |
| Queue, Brain, Evals, Agents | later |
| Public mode and the export | after the first weeks |

The look follows [`DESIGN.md`](DESIGN.md).
