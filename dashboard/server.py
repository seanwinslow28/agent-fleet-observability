"""The private dashboard's web server, run on the Mini and reached only over Tailscale.

It reads the brain on every request and keeps no state of its own. The only
writes are Sean's labels and decisions (dashboard/labels.py).

    uv run python -m dashboard.server --brain ~/Code-Brain/SWCB --bind <tailnet ip> [--port 8780]
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dashboard.cards import (TICKET_ID, NotACard, card, cards, judge_answer, label_for, latest_verdict, split_doc,
                             ticket_path)
from dashboard.labels import ReviewError, act, save_label

STATIC = Path(__file__).parent / "static"
RUN_LOG_LIMIT = 256 * 1024  # the last 256 KB of a run's tool log


class Handler(BaseHTTPRequestHandler):
    brain: Path  # set by make_server
    server_version = "swcb-dashboard"

    # -- reads --

    def do_GET(self) -> None:  # noqa: N802 (http.server's name)
        url = urlparse(self.path)
        path = unquote(url.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if path in ("/", "/review", "/index.html"):
            return self._file(STATIC / "index.html")
        if path.startswith("/static/"):
            name = path.removeprefix("/static/")
            target = STATIC / name
            if "/" in name or not target.is_file():
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return self._file(target)
        if path == "/api/review":
            return self._json({"cards": cards(self.brain)})
        if path == "/api/judge":
            return self._judge(query)
        if m := re.fullmatch(r"/audio/([^/]+)\.mp3", path):
            return self._audio(m.group(1))
        if m := re.fullmatch(r"/runlog/([^/]+)/(\d+)", path):
            return self._run_log(m.group(1), int(m.group(2)))
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _judge(self, query: dict) -> None:
        ticket_id, attempt = query.get("id", ""), query.get("attempt", "")
        path = ticket_path(self.brain, ticket_id)
        if path is None or not attempt.isdigit():
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        meta, _ = split_doc(path.read_text(encoding="utf-8"))
        if not label_for(meta, int(attempt)) and query.get("peek") != "1":
            return self._json({"error": "Save your label first, or peek."}, HTTPStatus.CONFLICT)
        return self._json(judge_answer(self.brain, ticket_id, int(attempt)))

    def _audio(self, ticket_id: str) -> None:
        target = self.brain / ".runtime" / "audio" / f"{ticket_id}.mp3"
        if not TICKET_ID.fullmatch(ticket_id) or not target.is_file():
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        data = target.read_bytes()
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if not m or (not m.group(1) and not m.group(2)):
            return self._send(HTTPStatus.OK, data, "audio/mpeg", {"Accept-Ranges": "bytes"})
        if m.group(1):
            start, end = int(m.group(1)), int(m.group(2)) if m.group(2) else len(data) - 1
        else:  # bytes=-N: the last N bytes
            start, end = max(len(data) - int(m.group(2)), 0), len(data) - 1
        end = min(end, len(data) - 1)
        if start > end:
            return self._send(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, b"", "audio/mpeg",
                              {"Content-Range": f"bytes */{len(data)}"})
        return self._send(HTTPStatus.PARTIAL_CONTENT, data[start:end + 1], "audio/mpeg",
                          {"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{len(data)}"})

    def _run_log(self, ticket_id: str, attempt: int) -> None:
        target = self.brain / ".runtime" / "runs" / ticket_id / str(attempt) / "tools.jsonl"
        if not TICKET_ID.fullmatch(ticket_id) or not target.is_file():
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        data = target.read_bytes()[-RUN_LOG_LIMIT:]
        return self._send(HTTPStatus.OK, data, "text/plain; charset=utf-8")

    # -- writes --

    def do_POST(self) -> None:  # noqa: N802
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._json({"error": "send JSON"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        # A browser always sends Origin on a cross-site POST, and JSON forces a preflight this
        # server never answers, so another site can't write. Tailscale serve forwards the page's
        # own host in X-Forwarded-Host.
        origin = self.headers.get("Origin")
        hosts = {self.headers.get("Host"), self.headers.get("X-Forwarded-Host")} - {None}
        if origin and urlparse(origin).netloc not in hosts:
            return self._json({"error": "writes come only from this page"}, HTTPStatus.FORBIDDEN)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            ticket_id, attempt = str(body.get("id", "")), body.get("attempt")
            if not isinstance(attempt, int):
                raise ReviewError("Which attempt? The page sent none.")
            path = urlparse(self.path).path
            if path == "/api/label":
                label = save_label(self.brain, ticket_id, attempt, body.get("answers") or {},
                                   critique=body.get("critique"), judge_seen_first=bool(body.get("judge_seen_first")),
                                   seconds=body.get("seconds"))
            elif path == "/api/action":
                label = act(self.brain, ticket_id, attempt, str(body.get("action")), note=body.get("note"))
            else:
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (ReviewError, ValueError, AttributeError) as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        try:
            after = card(self.brain, ticket_id)
        except NotACard:
            after = None
        worker = (latest_verdict(self.brain, ticket_id)[1] or {}).get("worker") or {}
        return self._json({"label": label, "card": after,
                           "worker": f"{worker.get('agent')} on {worker.get('model')}" if worker else None})

    # -- plumbing --

    def _file(self, target: Path) -> None:
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith("javascript"):
            kind += "; charset=utf-8"
        self._send(HTTPStatus.OK, target.read_bytes(), kind, {"Cache-Control": "no-cache"})

    def _json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(data, default=str).encode(), "application/json",
                   {"Cache-Control": "no-store"})

    def _send(self, status: HTTPStatus, data: bytes, kind: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")


def make_server(brain: Path, bind: str, port: int) -> ThreadingHTTPServer:
    handler = type("BrainHandler", (Handler,), {"brain": Path(brain).expanduser().resolve()})
    return ThreadingHTTPServer((bind, port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brain", required=True, type=Path)
    parser.add_argument("--bind", required=True, help="the Mini's tailnet address, or 127.0.0.1 to try it locally")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args(argv)
    if args.bind in ("0.0.0.0", "::", ""):
        parser.error("bind to the tailnet address, never every interface")
    if not (args.brain.expanduser() / "queue").is_dir():
        parser.error(f"{args.brain} has no queue/ folder; is it the brain?")
    server = make_server(args.brain, args.bind, args.port)
    print(f"dashboard on http://{args.bind}:{server.server_address[1]}, reading {args.brain}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
