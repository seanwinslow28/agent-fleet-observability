"""The HTTP side: what the phone and laptop ask for, and what writes are allowed."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from dashboard.server import make_server

SOURDOUGH = "2026-10-07-sourdough-starter-temperature"
YES = {"lane_agree": True, "deliverable": "pass", "judgement": "pass"}


@pytest.fixture
def base(brain):
    server = make_server(brain, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {})) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def post(url, body, content_type="application/json", origin=None, forwarded_host=None):
    headers = {"Content-Type": content_type}
    if origin:
        headers["Origin"] = origin
    if forwarded_host:
        headers["X-Forwarded-Host"] = forwarded_host
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_page_and_its_script_are_served(base):
    status, headers, body = get(base + "/")
    assert status == 200 and b"<title>" in body and "text/html" in headers["Content-Type"]
    assert get(base + "/static/app.js")[0] == 200
    assert get(base + "/static/../cards.py")[0] == 404


def test_review_lists_the_cards(base):
    status, _, body = get(base + "/api/review")
    data = json.loads(body)
    assert status == 200 and len(data["cards"]) == 5


def test_a_label_and_a_decision_go_through(base, brain):
    status, data = post(base + "/api/label", {"id": SOURDOUGH, "attempt": 1, "answers": YES, "seconds": 40})
    assert status == 200 and data["label"]["read"] is True
    status, data = post(base + "/api/action", {"id": SOURDOUGH, "attempt": 1, "action": "accept"})
    assert status == 200 and (brain / "queue" / "done" / f"{SOURDOUGH}.md").is_file()


def test_a_review_error_comes_back_in_plain_words(base):
    status, data = post(base + "/api/action", {"id": SOURDOUGH, "attempt": 1, "action": "accept"})
    assert status == 400 and data["error"] == "Save the label first."


def test_writes_refuse_anything_but_json(base):
    status, _ = post(base + "/api/label", {"id": SOURDOUGH}, content_type="text/plain")
    assert status == 415


def test_writes_refuse_another_sites_origin(base):
    status, _ = post(base + "/api/label", {"id": SOURDOUGH, "attempt": 1, "answers": YES},
                     origin="https://evil.example.com")
    assert status == 403
    status, _ = post(base + "/api/label", {"id": SOURDOUGH, "attempt": 1, "answers": YES}, origin=base)
    assert status == 200


def test_the_judge_waits_for_the_label_unless_sean_peeks(base):
    url = f"{base}/api/judge?id={SOURDOUGH}&attempt=1"
    assert get(url)[0] == 409
    assert get(url + "&peek=1")[0] == 409  # a peek is a recorded write, never a read
    post(base + "/api/label", {"id": SOURDOUGH, "attempt": 1, "answers": YES})
    assert json.loads(get(url)[2])["critique"] == "Each quote supports its claim."


def test_audio_is_served_in_ranges(base, brain):
    whole = (brain / ".runtime" / "audio" / f"{SOURDOUGH}.mp3").read_bytes()
    status, headers, body = get(f"{base}/audio/{SOURDOUGH}.mp3", {"Range": "bytes=0-99"})
    assert status == 206 and body == whole[:100]
    assert headers["Content-Range"] == f"bytes 0-99/{len(whole)}"
    assert get(f"{base}/audio/..%2Fsecret.mp3")[0] == 404


def test_the_run_log_is_readable(base):
    status, headers, body = get(f"{base}/runlog/{SOURDOUGH}/1")
    assert status == 200 and b"web_search" in body and "text/plain" in headers["Content-Type"]


def test_a_calibration_label_reveals_the_worker(base):
    status, data = post(base + "/api/label", {"id": "2026-10-06-tea-steeping", "attempt": 2, "answers": YES})
    assert status == 200 and data["card"] is None
    assert data["worker"] == "researcher on claude-sonnet-5-5"


def test_writes_accept_the_page_tailscale_forwarded(brain):
    server = make_server(brain, "127.0.0.1", 0, allow_hosts=["mini.tailnet.example:8780"])
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, _ = post(url + "/api/label", {"id": SOURDOUGH, "attempt": 1, "answers": YES},
                         origin="http://mini.tailnet.example:8780", forwarded_host="mini.tailnet.example:8780")
        assert status == 200
    finally:
        server.shutdown()


def test_another_host_name_is_refused(base):
    assert get(base + "/api/review", {"Host": "evil.example:80"})[0] == 403


def test_a_required_tailnet_user_gates_every_request(brain):
    server = make_server(brain, "127.0.0.1", 0, require_user="sean@example.com")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert get(url + "/api/review")[0] == 403
        assert get(url + "/api/review", {"Tailscale-User-Login": "sean@example.com"})[0] == 200
    finally:
        server.shutdown()


def test_a_peek_is_a_recorded_write(base, brain):
    status, data = post(base + "/api/peek", {"id": SOURDOUGH, "attempt": 1})
    assert status == 200 and data["result"] == "pass"
    assert "judge_seen_first: true" in (brain / "queue" / f"{SOURDOUGH}.md").read_text()
