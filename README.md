# agent-fleet-observability

A dashboard over Sean Winslow's second brain and the agents that work in it overnight. One app in two modes: a private command center on his Mac Mini, and a public showcase that replays real, sanitized nights, including the ones where the checker caught an agent's made-up quote. What it's for is in [`PRODUCT.md`](PRODUCT.md); how it looks is in [`DESIGN.md`](DESIGN.md).

Until the first replay is published, [fleet.seanwinslow.com](https://fleet.seanwinslow.com) shows a holding page (`index.html`; `.vercelignore` keeps everything else off the public site). The previous dashboard lives in this repo's git history.

## The Review page

The first page of the private mode: the morning's cards, one at a time. Each card leads with the checker's evidence (a dot per check and one plain sentence), then the answer, then a map from each claim to the quote that backs it, with "Brief says ≠ Page says" where a quote isn't on its page. Sean labels it one question at a time; the judge's answer stays hidden until his label is saved. His label and his decision (accept, send back, drop) are written into the work ticket's file in the brain.

| Path | What |
|---|---|
| `dashboard/cards.py` | reads the cards from the brain's files |
| `dashboard/labels.py` | writes Sean's label and decision back into the ticket file |
| `dashboard/server.py` | the web server: the page, a JSON API, audio and run logs |
| `dashboard/static/` | the page: plain HTML, CSS and JavaScript, no build step |
| `dashboard/fixture.py` | an invented brain for tests and for trying the page |
| `install.sh` | runs it on the Mini as `com.swcb.dashboard`, reachable only over Tailscale |

## Use

```bash
uv sync
uv run pytest -q

# Try it on an invented brain (writes go to that folder only):
uv run python -m dashboard.fixture /tmp/fixture-brain
uv run python -m dashboard.server --brain /tmp/fixture-brain --bind 127.0.0.1 --port 8781

# On the Mini, over the real brain:
./install.sh               # or ./install.sh --uninstall
```

The repo holds code, never data: the server reads the brain at runtime, and everything in `dashboard/fixture.py` is made up.
