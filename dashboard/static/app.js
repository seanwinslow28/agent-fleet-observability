// The Review page: one card at a time, one question at a time (#16 §3–§7, DESIGN.md §6).
// Everything it shows comes from /api/review; every write goes back as one POST the server
// turns into a file write in the brain. No state is kept here beyond the morning's session.
"use strict";

const $app = document.getElementById("app");
const S = {
  cards: [],
  at: 0,              // index of the card on screen
  answers: {},        // card key -> {field: value}
  step: {},           // card key -> index of the question on screen
  peeked: {},         // card key -> true once Sean peeked at the judge
  judge: {},          // card key -> the judge's answer, once fetched
  shownAt: {},        // card key -> when the card first came on screen (seconds-per-card)
  sending: {},        // card key -> the send-back note box's text, once open
  busy: false,
  error: null,
  loadError: null,
};
const key = (c) => `${c.id}#${c.attempt}`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
const laneWord = (l) => String(l).replace("-", " ");
const MARK = { found: ["✓", "quote found on the page"], missing: ["≠", "quote not on the page"], unconfirmed: ["?", "page didn't load"] };
const audio = new Audio();
audio.preload = "none";

document.getElementById("date").textContent = new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

async function load(keepId) {
  try {
    const r = await fetch("/api/review", { cache: "no-store" });
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    S.cards = (await r.json()).cards;
    S.loadError = null;
  } catch (e) {
    S.loadError = `Couldn't read the brain: ${e.message}. Last good: ${S.cards.length ? "the cards below" : "nothing yet"}.`;
  }
  const i = keepId ? S.cards.findIndex((c) => c.id === keepId) : -1;
  S.at = Math.min(i >= 0 ? i : S.at, Math.max(S.cards.length - 1, 0));
  render(true);
}

async function post(path, body) {
  S.busy = true; S.error = null; render();
  try {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `the server answered ${r.status}`);
    return data;
  } catch (e) {
    S.error = e.message; return null;
  } finally {
    S.busy = false;
  }
}

// ---------------------------------------------------------------- actions

const ACT = {
  prev() { if (S.at > 0) { S.at--; stopAudio(); render(true); } },
  next() { if (S.at < S.cards.length - 1) { S.at++; stopAudio(); render(true); } },
  answer(field, value) {
    const c = S.cards[S.at], k = key(c);
    (S.answers[k] ??= {})[field] = value;
    const qs = c.questions, idx = qs.findIndex((q) => q.field === field);
    S.step[k] = idx + 1;
    if (S.step[k] >= qs.length && !anyNo(c)) return ACT.save();
    render();
  },
  back() { const k = key(S.cards[S.at]); S.step[k] = Math.max((S.step[k] || 0) - 1, 0); render(); },
  async save() {
    const c = S.cards[S.at], k = key(c);
    const critique = document.getElementById("critique")?.value ?? "";
    const seconds = Math.round((Date.now() - (S.shownAt[k] || Date.now())) / 1000);
    const data = await post("/api/label", { id: c.id, attempt: c.attempt, answers: S.answers[k] || {}, critique, judge_seen_first: !!S.peeked[k], seconds });
    if (data) {
      if (data.card) S.cards[S.at] = data.card;
      else S.cards[S.at] = { ...c, label: data.label, finished: true, details: { ...c.details, worker: data.worker } };
      if (c.judge?.answered) await fetchJudge(S.cards[S.at], false);
    }
    render();
  },
  async peek() {
    const c = S.cards[S.at];
    S.peeked[key(c)] = true;
    await fetchJudge(c, true);
    render();
  },
  openSendBack() {
    const c = S.cards[S.at], k = key(c);
    S.sending[k] = c.label?.note || "";
    render();
    document.getElementById("note")?.focus();
  },
  async decide(action) {
    const c = S.cards[S.at], k = key(c);
    const note = action === "send_back" ? document.getElementById("note")?.value ?? "" : undefined;
    const data = await post("/api/action", { id: c.id, attempt: c.attempt, action, note });
    if (data) { delete S.sending[k]; stopAudio(); return load(); }
    render();
  },
  done() { S.cards.splice(S.at, 1); stopAudio(); load(); },
  listen() {
    const c = S.cards[S.at];
    if (!audio.paused && audio.dataset.id === c.id) { audio.pause(); return render(); }
    if (audio.dataset.id !== c.id) { audio.src = `/audio/${encodeURIComponent(c.id)}.mp3`; audio.dataset.id = c.id; }
    audio.play().catch((e) => { S.error = `Couldn't play the audio: ${e.message}.`; render(); });
    render();
  },
};
audio.addEventListener("pause", () => render());
audio.addEventListener("ended", () => render());
function stopAudio() { if (!audio.paused) audio.pause(); }

async function fetchJudge(c, peek) {
  try {
    const r = await fetch(`/api/judge?id=${encodeURIComponent(c.id)}&attempt=${c.attempt}${peek ? "&peek=1" : ""}`, { cache: "no-store" });
    if (r.ok) S.judge[key(c)] = await r.json();
  } catch (_) { /* the judge line just won't show */ }
}

function anyNo(c) {
  const a = S.answers[key(c)] || {};
  return a.lane_agree === false || a.deliverable === "fail" || a.judgement === "fail";
}

$app.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.disabled || S.busy) return;
  const [name, ...args] = el.dataset.act.split("|");
  const parsed = args.map((a) => (a === "true" ? true : a === "false" ? false : a));
  ACT[name]?.(...parsed);
});
document.addEventListener("keydown", (e) => {
  if (e.target.closest("textarea, input")) return;
  if (e.key === "j") ACT.next();
  if (e.key === "k") ACT.prev();
});

// ---------------------------------------------------------------- render

function render(entering) {
  if (S.loadError && !S.cards.length) {
    $app.innerHTML = `<div class="empty"><p>${esc(S.loadError)}</p></div>`;
    return;
  }
  if (!S.cards.length) {
    $app.innerHTML = `<div class="empty"><h1>Nothing needs you</h1><p>Every card is labeled and decided.</p></div>`;
    return;
  }
  const c = S.cards[S.at], k = key(c);
  S.shownAt[k] ??= Date.now();
  // Keep whatever Sean opened (an evidence row, More details) open across a re-render of the same card.
  const open = entering ? [] : [...$app.querySelectorAll("details[open]")].map((d) => d.dataset.k);
  $app.innerHTML = `
    ${S.loadError ? `<div class="err">${esc(S.loadError)}</div>` : ""}
    <div class="pager">
      <button data-act="prev" ${S.at === 0 ? "disabled" : ""}>Previous</button>
      <span class="tnum">${S.at + 1} of ${S.cards.length} · about 3 minutes each</span>
      <button data-act="next" ${S.at === S.cards.length - 1 ? "disabled" : ""}>Next</button>
    </div>
    <article class="card ${entering ? "enter" : ""}" aria-label="${esc(c.title)}">
      <div class="cardhead">${stamp(c)}${listen(c)}</div>
      <h2 class="cq">${esc(c.title)}</h2>
      <div class="happened">
        <div class="dots" role="list" aria-label="Checks">${c.checks.map(dot).join("")}</div>
        <p>${esc(c.headline)}</p>
      </div>
      ${c.answer ? `<p class="lab">Answer</p><div class="ans">${paras(c.answer)}</div>` : ""}
      ${evidence(c)}
      ${spend(c)}
      ${more(c)}
      ${ask(c)}
    </article>`;
  open.forEach((name) => $app.querySelector(`details[data-k="${CSS.escape(name)}"]`)?.setAttribute("open", ""));
}

function stamp(c) {
  return `<span class="stamp ${esc(c.lane)}">${esc(laneWord(c.lane))}${c.calibration ? ` <span class="cal">calibration</span>` : ""}</span>`;
}

function listen(c) {
  if (!c.audio?.ready) return `<button class="btn listen" disabled title="${esc(c.audio?.why || "No audio")}">No audio</button>`;
  const playing = !audio.paused && audio.dataset.id === c.id;
  return `<button class="btn listen" data-act="listen" aria-pressed="${playing}">${playing ? "Pause" : "Listen"}</button>`;
}

function dot(k) {
  const label = `${k.name}: ${k.result}`;
  return `<i class="dot ${esc(k.result)}" role="listitem" aria-label="${esc(label)}" title="${esc(label + (k.summary ? " · " + k.summary : ""))}"></i>`;
}

function paras(text) {
  return String(text).split(/\n\s*\n/).map((p) => `<p>${esc(p.trim())}</p>`).join("");
}

function evidence(c) {
  if (!c.evidence.length) return "";
  const main = c.evidence.filter((r) => r.section === "Answer");
  const rest = c.evidence.filter((r) => r.section !== "Answer");
  const shown = main.length ? main : rest, hidden = main.length ? rest : [];
  const rows = (list) => { let last = null; return list.map((r) => { const html = evRow(r, r.claim === last); last = r.claim; return html; }).join(""); };
  const counts = c.evidence.reduce((n, r) => ((n[r.status] = (n[r.status] || 0) + 1), n), {});
  const tally = [["found", "found"], ["missing", "not on the page"], ["unconfirmed", "didn't load"]]
    .filter(([s]) => counts[s]).map(([s, w]) => `${counts[s]} ${w}`).join(" · ");
  return `<p class="lab">Evidence <span class="small tnum">· ${esc(tally)}</span></p>
    <div class="ev">${rows(shown)}
      ${hidden.length ? `<details class="more-ev" data-k="findings"><summary>${hidden.length} more from the findings</summary>${rows(hidden)}</details>` : ""}
    </div>`;
}

function evRow(r, repeat) {
  const k = `ev-${r.section}-${r.marker}-${r.claim}`;
  const [glyph, word] = MARK[r.status] || ["·", r.status];
  let open;
  if (r.status === "missing") {
    open = `<div class="vs"><div><b>Brief says</b>“${esc(r.quote)}”</div><div class="ne"><b>Page says</b>${r.passage ? esc(r.passage) : esc(r.why || "the page doesn't have it")}</div></div>`;
  } else if (r.status === "unconfirmed") {
    open = `<p>The page didn't load, so this quote is unchecked${r.why ? `: ${esc(r.why)}` : ""}.</p><p>Brief says “${esc(r.quote)}”</p>`;
  } else {
    open = `<p>${highlight(r.passage || "", r.quote || "")}</p>`;
  }
  return `<details class="evr ${esc(r.status)}" data-k="${esc(k)}"><summary>
      <span class="c ${repeat ? "again" : ""}">${repeat ? "Same claim, another source" : esc(r.claim)}</span>
      <span class="m" aria-hidden="true">${glyph}</span><span class="sr">${esc(word)}</span>
      <span class="h">${esc(r.host)}</span></summary>
    <div class="open">${open}${/^https?:\/\//i.test(r.url || "") ? `<p class="small"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open the page</a></p>` : ""}</div></details>`;
}

function highlight(passage, quote) {
  const norm = (s) => s.toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
  const at = quote ? norm(passage).indexOf(norm(quote)) : -1;
  if (at < 0) return esc(passage);
  return esc(passage.slice(0, at)) + `<mark>${esc(passage.slice(at, at + quote.length))}</mark>` + esc(passage.slice(at + quote.length));
}

function spend(c) {
  const s = c.spend;
  if (!s) return "";
  const b = s.budget || {};
  const usd = (n) => `$${Number(n).toFixed(2)}`;
  return `<p class="spend tnum">${s.minutes} of ${b.minutes ?? "?"} min · ${s.turns} of ${b.turns ?? "?"} turns · ${usd(s.usd)} of ${b.usd != null ? usd(b.usd) : "?"}</p>`;
}

function more(c) {
  const d = c.details, labeled = !!c.label;
  const worker = d.worker ?? (c.calibration && !labeled ? "hidden until your label is saved (calibration attempt)" : "unknown");
  const flags = d.flags.map((f) => (f === "compacted" ? "compacted: the session's memory was squeezed mid-run, so it may have lost track of earlier steps" : f));
  const rows = [
    ["Worker", esc(worker)],
    ["Run log", d.run_log ? `<a href="/runlog/${encodeURIComponent(c.id)}/${c.attempt}" target="_blank" rel="noopener">the tool calls, as logged</a>` : "none"],
    ["Drew on", d.drew_on.length ? d.drew_on.map(esc).join(", ") : "no notes"],
    flags.length ? ["Flags", flags.map(esc).join("; ")] : null,
    !c.audio?.ready ? ["Audio", esc(c.audio?.why || "none")] : null,
    c.judge ? ["Judge", esc(`${c.judge.model} (${c.judge.effort}) · ${c.judge.badge}`)] : null,
    ["Attempt", `${c.attempt}${d.checked_at ? ` · checked ${esc(String(d.checked_at).replace("T", " ").slice(0, 16))}` : ""}`],
  ].filter(Boolean);
  return `<details class="more" data-k="more"><summary>More details</summary>
    <dl>${rows.map(([t, v]) => `<dt>${t}</dt><dd>${v}</dd>`).join("")}</dl>
    <p class="lab">Every check</p>
    <ul class="checklist">${c.checks.map((k) => `<li class="r-${esc(k.result)}"><b>${esc(k.name)}</b>: ${esc(k.result)}${k.summary ? ` · ${esc(k.summary)}` : ""}</li>`).join("")}</ul>
    ${d.notes.length ? `<p class="lab" style="margin-top:12px">What the checks can't see</p><ul>${d.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
    ${d.summary ? `<p class="lab" style="margin-top:12px">The agent's own summary</p><div class="summary">${esc(d.summary)}</div>` : ""}
  </details>`;
}

function ask(c) {
  const k = key(c);
  const err = S.error ? `<div class="err" role="alert">${esc(S.error)}</div>` : "";
  if (c.label) return decide(c) + err;
  const qs = c.questions, step = Math.min(S.step[k] || 0, qs.length);
  const steps = `<div class="steps" aria-hidden="true">${qs.map((_, i) => `<i class="${i <= step ? "on" : ""}"></i>`).join("")}</div>`;
  const peek = c.judge?.answered && !S.peeked[k]
    ? `<button class="linkish" data-act="peek">Peek at the judge (takes this card out of the judge's test)</button>` : "";
  const peekLine = S.peeked[k] ? judgeLine(c, true) : "";
  if (step >= qs.length) {
    // every question answered and at least one no: one sentence first
    return `<div class="ask">${steps}${peekLine}
      <p class="askq">What's wrong, in one sentence?</p>
      <p class="askx">It goes into the ticket with your label, and becomes the send-back note.</p>
      <label class="sr" for="critique">What's wrong</label>
      <textarea id="critique" maxlength="600"></textarea>
      <div class="yn"><button class="btn primary ${S.busy ? "busy" : ""}" data-act="save">Save label</button></div>
      <div class="after"><button class="linkish" data-act="back">Change my last answer</button></div>${err}</div>`;
  }
  const q = qs[step], yes = q.field === "lane_agree" ? "true" : "pass", no = q.field === "lane_agree" ? "false" : "fail";
  return `<div class="ask">${steps}${peekLine}
    <p class="askq">${q.field === "judgement" ? `“${esc(q.question)}”` : esc(q.question)}</p>
    <p class="askx">${esc(q.explainer)}</p>
    <div class="yn">
      <button class="btn primary" data-act="answer|${q.field}|${yes}">Yes</button>
      <button class="btn" data-act="answer|${q.field}|${no}">No</button>
    </div>
    <div class="after">${step > 0 ? `<button class="linkish" data-act="back">Change my last answer</button>` : ""}${peek}</div>${err}</div>`;
}

function judgeLine(c, peeked) {
  if (!c.judge) return "";
  if (!c.judge.answered) return `<div class="judgeline"><p>The judge did not answer, so nothing confirms the judgement sentence.</p></div>`;
  const j = S.judge[key(c)];
  if (!j) return "";
  const mine = c.label?.judgement;
  const same = mine ? (mine === j.result ? `, same as you` : `; you said ${mine}`) : "";
  const tag = c.judge.status === "graduated" ? "graduated" : "unvalidated";
  return `<div class="judgeline"><p>Judge said ${esc(j.result)}${same} · ${tag}${peeked ? " · you peeked first" : ""}</p>
    ${j.critique ? `<p class="small">${esc(j.critique)}</p>` : ""}</div>`;
}

function decide(c) {
  const k = key(c), L = c.label;
  const saved = `<p class="saved">Label saved${L.note ? `: “${esc(L.note)}”` : "."}</p>`;
  if (c.finished || c.calibration) {
    return `<div class="ask">${judgeLine(c, L.judge_seen_first)}${saved}
      <p class="askx">A calibration attempt's label is the whole decision. The worker was ${esc(c.details.worker || "not recorded")}.</p>
      <div class="yn"><button class="btn primary" data-act="done">Next card</button></div></div>`;
  }
  if (S.sending[k] !== undefined) {
    return `<div class="ask">${judgeLine(c, L.judge_seen_first)}
      <p class="askq">Send it back with a note</p>
      <p class="askx">The ticket goes back to draft. Edit it and set it ready when you want it rerun.</p>
      <label class="sr" for="note">Note for the rerun</label>
      <textarea id="note" maxlength="1000">${esc(S.sending[k])}</textarea>
      <div class="yn"><button class="btn primary ${S.busy ? "busy" : ""}" data-act="decide|send_back">Send back</button></div>
      <div class="after"><button class="linkish" data-act="cancelSend">Cancel</button></div></div>`;
  }
  const blocked = c.lane === "Blocked", rejected = L.deliverable === "fail";
  const big = blocked || rejected
    ? `<button class="btn primary" data-act="openSendBack">Send back</button><button class="btn" data-act="decide|drop">Drop</button>`
    : `<button class="btn primary" data-act="decide|accept">Accept</button><button class="btn" data-act="openSendBack">Send back</button>`;
  const small = blocked || rejected ? "" : `<button class="linkish" data-act="decide|drop">Drop</button>`;
  return `<div class="ask">${judgeLine(c, L.judge_seen_first)}${saved}
    <div class="yn">${big}</div><div class="after">${small}</div></div>`;
}
ACT.cancelSend = () => { delete S.sending[key(S.cards[S.at])]; render(); };

load();
