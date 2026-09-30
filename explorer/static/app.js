"use strict";

const PAGE_SIZE = 50;
const $ = (id) => document.getElementById(id);
const form = $("filters");
const state = { offset: 0, total: 0, activeId: null, seq: 0, actionNames: {} };

// ---------------------------------------------------------------------------
// Helpers

const fmt = (n) => Number(n).toLocaleString("en-US");
const fmtLen = (s) => (s == null ? "–" : `${s.toFixed(1)}s`);
const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reEscape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Same rules as the server: whitespace-separated terms, "quoted phrases" kept together.
function parseTerms(q) {
  return [...(q || "").matchAll(/"([^"]+)"|(\S+)/g)].map((m) => (m[1] || m[2]).toLowerCase());
}

// Escape text and wrap keyword matches in <mark>.
function highlight(text, terms) {
  text = String(text ?? "");
  if (!terms.length) return escapeHtml(text);
  const re = new RegExp(terms.map(reEscape).join("|"), "gi");
  let out = "";
  let last = 0;
  for (const m of text.matchAll(re)) {
    out += escapeHtml(text.slice(last, m.index)) + `<mark>${escapeHtml(m[0])}</mark>`;
    last = m.index + m[0].length;
  }
  return out + escapeHtml(text.slice(last));
}

async function getJSON(url) {
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function fillSelect(select, options) {
  for (const [value, label] of options) select.add(new Option(label, value));
}

// ---------------------------------------------------------------------------
// Filters <-> URL

function filterParams() {
  const p = new URLSearchParams();
  for (const [key, value] of new FormData(form)) {
    if (String(value).trim()) p.set(key, String(value).trim());
  }
  if (p.get("sort") === "id") p.delete("sort");
  return p;
}

function applyParams(p) {
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = p.get(el.name) === "1";
    else el.value = p.get(el.name) ?? (el.name === "sort" ? "id" : "");
  }
}

function syncUrl() {
  const p = filterParams();
  if (state.offset) p.set("offset", state.offset);
  if (state.activeId) p.set("video", state.activeId);
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

// ---------------------------------------------------------------------------
// Results table

async function load() {
  const params = filterParams();
  params.set("limit", PAGE_SIZE);
  params.set("offset", state.offset);
  syncUrl();

  const seq = ++state.seq;
  let data;
  try {
    data = await getJSON(`/api/videos?${params}`);
  } catch (err) {
    if (seq === state.seq) $("summary").textContent = `Error: ${err.message}`;
    return;
  }
  if (seq !== state.seq) return; // a newer request is in flight

  state.total = data.total;
  renderRows(data.results);
  renderSummary(data);
}

function renderSummary({ total, offset, results }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  $("summary").textContent = total
    ? `Showing ${fmt(offset + 1)}–${fmt(offset + results.length)} of ${fmt(total)} matching videos`
    : "0 matching videos";
  $("page").textContent = `Page ${page} of ${pages}`;
  $("prev").disabled = offset === 0;
  $("next").disabled = offset + PAGE_SIZE >= total;
}

function chips(names, terms, actionName) {
  if (!names.length) return '<span class="chip more">no actions</span>';
  // Put matching labels first so the visible ones explain why the row matched.
  const isHit = (n) => n === actionName || terms.some((t) => n.toLowerCase().includes(t));
  const ordered = [...names.filter(isHit), ...names.filter((n) => !isHit(n))];
  const shown = ordered.slice(0, 3).map((n) => `<span class="chip" title="${escapeHtml(n)}">${highlight(n, terms)}</span>`);
  if (ordered.length > 3) shown.push(`<span class="chip more">+${ordered.length - 3} more</span>`);
  return `<div class="chips">${shown.join("")}</div>`;
}

function renderRows(results) {
  const terms = parseTerms($("q").value);
  const actionName = state.actionNames[$("action").value];
  $("empty").hidden = results.length > 0;
  $("rows").innerHTML = results
    .map((v) => `
      <tr data-id="${escapeHtml(v.id)}" tabindex="0" class="${v.id === state.activeId ? "active" : ""}">
        <td class="id">${highlight(v.id, terms)}${v.verified ? "" :
          '<span class="tag-unverified" title="Annotators could not verify that the video matches its script">unverified</span>'}</td>
        <td class="scene">${escapeHtml(v.scene)}</td>
        <td class="num">${fmtLen(v.length)}</td>
        <td class="actions">${chips(v.actions, terms, actionName)}</td>
        <td class="objects">${highlight(v.objects.join(", "), terms) || "–"}</td>
        <td class="split">${escapeHtml(v.split)}</td>
      </tr>`)
    .join("");
}

// ---------------------------------------------------------------------------
// Detail panel

function timeline(segments, length, terms, actionCode) {
  if (!segments.length) return '<p class="note">No action segments are annotated for this video.</p>';
  const total = length || Math.max(...segments.map((s) => s.end));
  const clipped = segments.some((s) => s.end > total);
  // Emphasise segments matching the current search; if none match, show all equally.
  const matches = (s) => s.code === actionCode ||
    terms.some((t) => s.name.toLowerCase().includes(t) || s.code === t);
  const anyMatch = segments.some(matches);

  const rows = segments.map((s) => {
    const start = Math.min(s.start, total);
    const end = Math.min(s.end, total);
    const left = (start / total) * 100;
    const width = (Math.max(0, end - start) / total) * 100;
    const hit = !anyMatch || matches(s);
    const tip = escapeHtml(`${s.name} (${s.code}): ${s.start.toFixed(1)}s – ${s.end.toFixed(1)}s`);
    return `
      <div class="tl-label" title="${tip}">${escapeHtml(s.name)}</div>
      <div class="tl-track" title="${tip}">
        <div class="tl-bar${hit ? " hit" : ""}" style="left:${left}%;width:${width}%"></div>
      </div>`;
  }).join("");

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<span>${(total * f).toFixed(f ? 1 : 0)}s</span>`).join("");
  const note = clipped
    ? '<p class="note">Some segments end up to 1.5s after the recorded video length (a rounding quirk in the annotations). They are clipped to the end of the video here.</p>'
    : "";
  return `<div class="timeline">${rows}<div class="tl-axis">${ticks}</div></div>${note}`;
}

async function openVideo(id) {
  let v;
  try {
    v = await getJSON(`/api/videos/${encodeURIComponent(id)}`);
  } catch {
    return;
  }
  state.activeId = v.id;
  for (const tr of $("rows").children) tr.classList.toggle("active", tr.dataset.id === v.id);

  const terms = parseTerms($("q").value);
  const item = (label, value) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`;
  $("panel-title").textContent = `${v.id} · ${v.scene}`;
  $("panel-body").innerHTML = `
    <dl class="meta">
      ${item("Length", fmtLen(v.length))}
      ${item("Split", v.split)}
      ${item("Subject", v.subject)}
      ${item("Quality", v.quality ? `${v.quality} / 7` : "–")}
      ${item("Relevance", v.relevance ? `${v.relevance} / 7` : "–")}
      ${item("Verified", v.verified ? "Yes" : "No")}
    </dl>
    ${v.scene_full !== v.scene ? `<h3>Scene</h3><p>${escapeHtml(v.scene_full)}</p>` : ""}
    <h3>Script</h3>
    <p>${highlight(v.script, terms) || "–"}</p>
    <h3>Descriptions (${v.descriptions.length})</h3>
    <ul class="descriptions">${v.descriptions.map((d) => `<li>${highlight(d, terms)}</li>`).join("")}</ul>
    <h3>Objects</h3>
    <div class="chips">${v.objects.map((o) => `<span class="chip">${highlight(o, terms)}</span>`).join("") || "–"}</div>
    <h3>Action segments (${v.segments.length})</h3>
    ${timeline(v.segments, v.length, terms, $("action").value)}
  `;
  $("panel").hidden = false;
  $("panel-body").scrollTop = 0;
  syncUrl();
}

function closePanel() {
  $("panel").hidden = true;
  state.activeId = null;
  for (const tr of $("rows").children) tr.classList.remove("active");
  syncUrl();
}

// ---------------------------------------------------------------------------
// Events

let debounce;
const refresh = () => {
  state.offset = 0;
  load();
};

form.addEventListener("submit", (e) => e.preventDefault());
form.addEventListener("input", (e) => {
  if (e.target.matches("input[type=search], input[type=number]")) {
    clearTimeout(debounce);
    debounce = setTimeout(refresh, 250);
  }
});
form.addEventListener("change", (e) => {
  if (e.target.matches("select, input[type=checkbox]")) refresh();
});
form.addEventListener("reset", () => setTimeout(refresh)); // after the form has cleared
$("sort").addEventListener("change", refresh); // lives outside the <form> element

$("rows").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-id]");
  if (tr) openVideo(tr.dataset.id);
});
$("rows").addEventListener("keydown", (e) => {
  const tr = e.target.closest("tr[data-id]");
  if (tr && e.key === "Enter") openVideo(tr.dataset.id);
});
$("prev").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - PAGE_SIZE);
  load();
});
$("next").addEventListener("click", () => {
  if (state.offset + PAGE_SIZE < state.total) state.offset += PAGE_SIZE;
  load();
});
$("close").addEventListener("click", closePanel);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("panel").hidden) closePanel();
  if (e.key === "/" && !e.target.matches("input, select, textarea")) {
    e.preventDefault();
    $("q").focus();
  }
});

// ---------------------------------------------------------------------------
// Start-up

async function init() {
  let meta;
  try {
    meta = await getJSON("/api/meta");
  } catch (err) {
    $("stats").textContent = `Could not load dataset: ${err.message}`;
    return;
  }
  const s = meta.stats;
  $("stats").textContent =
    `Charades v1 · ${fmt(s.videos)} videos · ${s.classes} action classes · ` +
    `${fmt(s.segments)} labelled action segments · ${s.scenes} scenes · ${s.total_hours} hours`;

  for (const a of meta.actions) state.actionNames[a.code] = a.name;
  fillSelect($("scene"), meta.scenes.map((x) => [x.name, `${x.name} (${fmt(x.count)})`]));
  fillSelect($("action"), meta.actions.map((a) => [a.code, `${a.name} (${fmt(a.count)})`]));
  fillSelect($("object"), meta.objects.map((o) => [o.name, `${o.name} (${fmt(o.count)})`]));
  fillSelect($("split"), meta.splits.map((x) => [x, `${x[0].toUpperCase()}${x.slice(1)} only`]));

  const p = new URLSearchParams(location.search);
  applyParams(p);
  state.offset = Math.max(0, Number(p.get("offset")) || 0);
  await load();
  if (p.get("video")) openVideo(p.get("video"));
}

init();
