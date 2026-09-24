"use strict";

// ---------- helpers ----------
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.setAttribute("style", v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const locale = () => (LANG === "ru" ? "ru-RU" : "en-US");
const fmt = (n, d = 0) => (n === null || n === undefined || Number.isNaN(n)) ? "—"
  : Number(n).toLocaleString(locale(), { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v) => (v > 0 ? "+" : "") + fmt(v, 1) + "%";

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", "X-Poe2lab": "1" },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) { /* not json */ }
    // FastAPI's own 404 for an unknown path: the page is newer than the server that serves it
    if (res.status === 404 && msg === "Not Found") msg = t("serverOutdated");
    throw new Error(msg);
  }
  return res.json();
}

function toast(msg, ok = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (ok ? " ok" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 6000);
}

// English skill / passive name -> icon file, from the installed game (see poe2lab/icons.py)
let ICONS = {};
async function loadIcons() {
  try { ICONS = await (await fetch("/api/icons")).json(); } catch (_) { ICONS = {}; }
}
// Frames like the game's: a skill gem square in its socket colour, a support round, an item in an inventory cell
// coloured by rarity. Gem colours come with the open build (and with levelling suggestions).
let GEM_INFO = {};
const GEM_RGB = { "^xE05030": "#d9573a", "^x70FF70": "#5fcf5f", "^x7070FF": "#6b78f0" };
const icon = (name, cls = "ico") => {
  if (!name || !ICONS[name]) return null;
  const img = h("img", { class: cls, src: `/icons/${ICONS[name]}`, alt: "" });
  const gem = cls === "ico" && GEM_INFO[name];
  if (gem) {
    img.classList.add(gem.support ? "gem-support" : "gem-skill");
    img.style.setProperty("--gem", GEM_RGB[gem.color] || "#b8b8b8");
  }
  return img;
};
// an item's picture: a unique's own art ("Name, Base" -> Name), else its base's
const itemIcon = (name, base, rarity = "") => {
  const img = icon((name || "").split(",")[0].trim(), "item-ico") || icon(base, "item-ico");
  if (img) img.classList.add("r-" + (rarity || "normal").toLowerCase());
  return img;
};

const loading = (text) => h("div", { class: "loading" }, h("div", { class: "spinner" }), text);

const DMG_COLOR = { Physical: "var(--phys)", Fire: "var(--fire)", Cold: "var(--cold)", Lightning: "var(--lightning)", Chaos: "var(--chaos)" };
const METRIC = [["dps", "m_dps"], ["ehp", "m_ehp"], ["phys_hit", "m_phys"], ["fire_hit", "m_fire"], ["cold_hit", "m_cold"],
  ["lightning_hit", "m_lightning"], ["chaos_hit", "m_chaos"], ["recovery", "m_recovery"]];

function deltas(changes, keys = METRIC, min = 0.3) {
  const items = keys.filter(([k]) => Math.abs(changes[k] || 0) >= min)
    .map(([k, label]) => h("span", { class: "delta " + (changes[k] > 0 ? "pos" : "neg") }, `${t(label)} ${pct(changes[k])}`));
  return h("div", { class: "deltas" }, items.length ? items : h("span", { class: "muted small" }, t("noEffect")));
}

function scoreBar(score, max) {
  const w = Math.max(3, Math.min(100, (score / (max || 1)) * 100));
  return h("div", { class: "score" }, h("div", { class: "bar" }, h("span", { style: `width:${w}%` })), fmt(score, 1));
}

const chip = (cls, text) => h("span", { class: "chip " + cls }, text);

// ---------- state ----------
const state = { build: null, mode: "balanced", tab: "overview", cache: {}, chat: [] };
const resetCache = () => { state.cache = {}; };
// the cache belongs to the build open when the request started: a late answer for a previous build cannot land in
// the current build's cache; the same request in flight is shared instead of repeated
async function cached(key, fn) {
  const cache = state.cache;
  if (!(key in cache)) cache[key] = fn();
  try { return await cache[key]; } catch (e) { delete cache[key]; throw e; }
}
// analysis requests name the build they are for; the server refuses them if another build is open by then
const buildQuery = () => `build=${encodeURIComponent(state.build.name)}`;

// ---------- language ----------
function applyStaticTexts() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
    el.onclick = () => toast(el.title, true);  // a hover tooltip is easy to miss: a click shows it too
  });
  document.querySelectorAll("#lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === LANG));
  for (const id of ["foldAll", "unfoldAll"]) {  // icon buttons: the words are their tooltip
    const el = $("#" + id.replace(/[A-Z]/, (c) => "-" + c.toLowerCase()));
    el.title = t(id);
    el.setAttribute("aria-label", t(id));
  }
}

$("#lang").addEventListener("click", async (e) => {
  const l = e.target.dataset.lang;
  if (!l || l === LANG) return;
  LANG = l;
  try { localStorage.setItem("poe2lab.lang", l); } catch (_) { /* storage blocked */ }
  applyStaticTexts();
  await loadGameTexts();
  renderLangBanner();
  if (state.build) setBuildNames(state.build);
  loadStatus();
  loadBuildList();
  if (state.build) { renderHeader(); switchTab(state.tab); } else renderEmpty();
});

function renderEmpty() {
  $("#view").replaceChildren(h("div", { class: "empty" }, h("h2", {}, t("pickBuild")), h("p", { class: "muted" }, t("pickBuildHint"))));
}

// ---------- sidebar ----------
async function loadBuildList() {
  const box = $("#builds");
  try {
    const [builds, hidden] = await Promise.all([api("/api/builds"), api("/api/builds/hidden")]);
    box.replaceChildren();
    if (!builds.length) box.append(h("div", { class: "muted small" }, t("noBuilds")));
    for (const b of builds) {
      // a div, not a button: the star and the cross inside are buttons of their own
      box.append(h("div", {
        class: "build-item" + (state.build && state.build.name === b.name ? " active" : "") + (b.favorite ? " fav" : ""),
        role: "button", tabindex: "0", onclick: () => openBuild(b.name),
        onkeydown: (e) => { if (e.key === "Enter") openBuild(b.name); },
      },
      h("div", { class: "bi-text" },
        h("div", { class: "bi-name" }, b.name),
        h("div", { class: "bi-kind" }, (b.kind === "pob" ? t("savedInPob") : t("pobCode")) + (b.hasProfile ? " · " + t("withProfile") : ""))),
      h("button", { class: "bi-act star" + (b.favorite ? " on" : ""), title: b.favorite ? t("favOff") : t("favOn"),
        onclick: (e) => { e.stopPropagation(); toggleFavorite(b); } }, b.favorite ? "★" : "☆"),
      h("button", { class: "bi-act del", title: t("removeBuild"),
        onclick: (e) => { e.stopPropagation(); removeBuild(b); } }, "×")));
    }
    if (hidden.count) {
      box.append(h("button", { class: "link small", onclick: async () => {
        await api("/api/builds/unhide", { method: "POST" }); loadBuildList();
      } }, t("showHidden", hidden.count)));
    }
  } catch (e) { box.replaceChildren(h("div", { class: "muted small" }, e.message)); }
}

async function toggleFavorite(b) {
  try {
    await api(`/api/builds/${encodeURIComponent(b.name)}/favorite`, { method: "PUT", body: { favorite: !b.favorite } });
    loadBuildList();
  } catch (e) { toast(e.message); }
}

async function removeBuild(b) {
  if (!confirm(b.kind === "pob" ? t("confirmHide", b.name) : t("confirmTrash", b.name))) return;
  try {
    const r = await api(`/api/builds/${encodeURIComponent(b.name)}`, { method: "DELETE" });
    toast(r.result === "hidden" ? t("hiddenOne", b.name) : t("trashed", b.name), true);
    if (state.build && state.build.name === b.name) {
      switchTab.token = Symbol();  // a late answer for the removed build must not render
      state.build = null;
      state.chat = [];
      resetCache();
      $("#build-header").classList.add("hidden");
      $("#tabs").classList.add("hidden");
      renderEmpty();
    }
    loadBuildList();
  } catch (e) { toast(e.message); }
}

function renderAddBuild() {
  const name = h("input", { type: "text", placeholder: t("addName") });
  const code = h("textarea", { rows: 8, placeholder: t("addCode"), spellcheck: "false" });
  const go = h("button", { class: "primary", onclick: async () => {
    if (!code.value.trim()) { code.focus(); return; }
    go.disabled = true;
    go.textContent = t("adding");
    try {
      const r = await api("/api/builds", { method: "POST", body: { name: name.value, code: code.value } });
      toast(t("added", r.name), true);
      await openBuild(r.name);
    } catch (e) {
      toast(e.message);
      go.disabled = false;
      go.textContent = t("addGo");
    }
  } }, t("addGo"));
  hideBuildChrome();
  $("#view").replaceChildren(h("div", { class: "card stack add-build" },
    h("h3", {}, t("addTitle")), h("div", { class: "sub" }, t("addSub")),
    name, code,
    h("div", { class: "row" }, go, state.build
      ? h("button", { class: "ghost", onclick: () => { renderHeader(); switchTab(state.tab); } }, t("cancel")) : null)));
  code.focus();
}

$("#add-build").addEventListener("click", renderAddBuild);

async function loadStatus() {
  const s = await api("/api/status");
  $("#llm-status").textContent = s.llm.configured ? t("aiOn", s.llm.model) : t("aiOff");
  return s;
}

// ---------- build ----------
async function openBuild(name, group, skill) {
  $("#view").replaceChildren(loading(t("opening")));
  try {
    state.build = await api("/api/load", { method: "POST", body: { name, group, skill } });
    state.chat = [];
    if (!state.changes || state.changes.build !== name) state.changes = null;
    resetCache();
    renderHeader();
    loadBuildList();
    switchTab(state.tab);
  } catch (e) {
    $("#view").replaceChildren(h("div", { class: "empty" }, h("h2", {}, t("openFailed")), h("p", { class: "muted" }, e.message)));
  }
}

function renderHeader() {
  const b = state.build;
  GEM_INFO = { ...(b.gemColors || {}) };
  setBuildNames(b);
  $("#build-header").classList.remove("hidden");
  $("#tabs").classList.remove("hidden");
  $("#bh-name").textContent = b.name;
  $("#bh-reload").title = t("reloadHint");
  renderChanges();
  $("#bh-sub").textContent = `${trName(b.info.class)} / ${trName(b.info.ascendancy)} · ${t("level", b.info.level)}`;
  // a picker with skill icons (a <select> cannot show images)
  const picker = $("#main-skill");
  const entries = b.groups.flatMap((g) => g.skills.map((s, i) => ({ group: g.index, skill: i + 1, name: s })));
  const current = entries.find((e) => b.info.mainSocketGroup === e.group && b.mainSkill === e.name) || entries[0];
  const label = (e) => [icon(e.name), h("span", {}, `${e.group}. ${trName(e.name)}`)];
  const list = h("div", { class: "picker-list hidden" }, entries.map((e) => h("div", {
    class: "picker-item" + (e === current ? " active" : ""),
    onclick: () => { list.classList.add("hidden"); if (e !== current) openBuild(b.name, e.group, e.skill); },
  }, label(e))));
  const button = h("button", { class: "picker-button", onclick: (ev) => { ev.stopPropagation(); list.classList.toggle("hidden"); } },
    current ? label(current) : null, h("span", { class: "caret" }, "▾"));
  picker.replaceChildren(button, list);
}

// ---------- build update: the character changed in the game -> a newer PoB file or code -> what changed ----------
async function applyReload(code) {
  const { changes, ...build } = await api("/api/reload", { method: "POST", body: { code } });
  state.build = build;
  state.chat = [];
  state.changes = { ...changes, build: build.name };
  resetCache();
  $("#build-notice").classList.add("hidden");
  renderHeader();
  loadBuildList();
  switchTab(state.tab);
}

async function reloadFromFile() {
  const btn = $("#bh-reload");
  btn.disabled = true;
  btn.textContent = t("reloading");
  try { await applyReload(""); } catch (e) { toast(e.message); }
  btn.disabled = false;
  btn.textContent = t("reload");
}

function renderReloadCode() {
  const b = state.build;
  const code = h("textarea", { rows: 8, placeholder: t("addCode"), spellcheck: "false" });
  const go = h("button", { class: "primary", onclick: async () => {
    if (!code.value.trim()) { code.focus(); return; }
    go.disabled = true;
    go.textContent = t("reloading");
    try { await applyReload(code.value); } catch (e) { toast(e.message); go.disabled = false; go.textContent = t("reloadGo"); }
  } }, t("reloadGo"));
  const opened = h("div", { class: "action hidden" }, t("pobCodeOpened"));
  const openPob = h("button", { class: "ghost", onclick: async () => {
    try {
      const r = await api("/api/pob/open", { method: "POST" });
      if (r.state === "missing") { toast(t("pobMissing")); return; }
      opened.classList.remove("hidden");
      code.focus();
    } catch (e) { toast(e.message); }
  } }, t("pobOpen"));
  hideBuildChrome();
  $("#view").replaceChildren(h("div", { class: "card stack add-build" },
    h("h3", {}, t("reloadTitle", b.name)), h("div", { class: "sub" }, t("reloadSub")), h("div", { class: "row" }, openPob), opened, code,
    h("div", { class: "row" }, go, h("button", { class: "ghost", onclick: () => { renderHeader(); switchTab(state.tab); } }, t("cancel")))));
  code.focus();
}

$("#bh-reload").addEventListener("click", () => (state.build.kind === "pob" ? updateViaPob() : renderReloadCode()));

// A PoB-saved build changes only when PoB saves it: open PoB on that build (or bring it forward), tell the player
// what to do there, and pick the save up by ourselves.
async function updateViaPob() {
  const box = $("#build-notice");
  const name = state.build.name;
  box.replaceChildren(h("span", {}, t("pobOpening")));
  box.classList.remove("hidden");
  let r;
  try { r = await api("/api/pob/open", { method: "POST" }); } catch (e) { toast(e.message); box.classList.add("hidden"); return; }
  if (r.state === "missing") { toast(t("pobMissing")); box.classList.add("hidden"); reloadFromFile(); return; }
  state.pobGuide = name;
  const head = r.state === "running" ? t("pobRunning", name) : r.openedBuild ? t("pobStarted", name) : t("pobStartedPlain", name);
  box.replaceChildren(h("div", { class: "stack", style: "gap:6px;flex:1" },
    h("b", {}, head),
    h("ol", { class: "pob-steps" }, t("pobSteps").map((s) => h("li", {}, s))),
    h("div", { class: "hint" }, t("pobAuth"), r.bundled ? " " + t("pobDevMode") : ""),
    h("div", { class: "row" }, h("span", { class: "muted small" }, h("span", { class: "spinner inline" }), " ", t("pobWaiting")),
      h("button", { class: "ghost small", onclick: () => { state.pobGuide = null; reloadFromFile(); } }, t("pobSavedAlready")),
      h("button", { class: "ghost small", onclick: () => { state.pobGuide = null; box.classList.add("hidden"); } }, t("cancel")))));
}

// PoB saved the build again (the player re-imported the character): offer the update when they come back here
async function checkBuildFile() {
  if (!state.build || (document.hidden && !state.pobGuide)) return;
  try {
    const s = await api("/api/status");
    const box = $("#build-notice");
    if (state.pobGuide) {
      if (state.pobGuide !== state.build.name) { state.pobGuide = null; box.classList.add("hidden"); return; }
      if (s.buildChanged) { state.pobGuide = null; await reloadFromFile(); }
      return;
    }
    if (s.buildChanged && s.build === state.build.name && !$("#tabs").classList.contains("hidden")) {
      box.replaceChildren(h("span", {}, t(state.build.kind === "pob" ? "buildFileChanged" : "buildCodeChanged", state.build.name)),
        h("button", { class: "primary", onclick: reloadFromFile }, t("reload")));
      box.classList.remove("hidden");
    } else {
      box.classList.add("hidden");
    }
  } catch (_) { /* the server is restarting */ }
}
window.addEventListener("focus", checkBuildFile);
document.addEventListener("visibilitychange", checkBuildFile);
setInterval(() => { if (!state.pobGuide) checkBuildFile(); }, 15000);
setInterval(() => { if (state.pobGuide) checkBuildFile(); }, 3000);

function changedEnough(r) {
  if (r.key.startsWith("hit_") && (r.before >= IMMUNE_HIT || r.after >= IMMUNE_HIT)) return (r.before >= IMMUNE_HIT) !== (r.after >= IMMUNE_HIT);
  const d = r.after - r.before;
  return !(Math.abs(d) < 1e-9 || (Math.abs(r.before) > 0 && Math.abs(d / r.before) < 0.005));
}

function renderChanges() {
  const box = $("#changes");
  const c = state.changes;
  if (!c || !state.build) { box.classList.add("hidden"); return; }
  const rows = c.rows.filter(changedEnough);
  const nodes = c.nodesAdded.length + c.nodesRemoved.length;
  const gems = c.gemsAdded.length + c.gemsRemoved.length;
  const nothing = !rows.length && !c.items.length && !nodes && !gems && c.level[0] === c.level[1];
  const close = h("button", { class: "bi-act", title: t("ruHide"), onclick: () => { state.changes = null; box.classList.add("hidden"); } }, "×");
  const notes = [
    c.class[0] !== c.class[1] ? h("div", { class: "action" }, t("classChanged", trName(c.class[0]), trName(c.class[1]))) : null,
    c.planReset ? h("div", { class: "hint" }, t("planWasReset")) : null,
    c.skillKept ? null : h("div", { class: "hint" }, t("skillNotKept", trName(c.skillBefore || ""))),
  ];
  const itemName = (n) => (n ? trItem(n) : t("chEmpty"));
  const lists = h("div", { class: "ch-lists" },
    c.items.length ? h("div", {}, h("b", {}, t("chGear")), h("ul", {}, c.items.map((i) => h("li", {}, `${slotName(i.slot)}: `,
      i.sameItem ? [itemName(i.after), h("span", { class: "muted" }, ` — ${t("chOtherMods")}`)] : `${itemName(i.before)} → ${itemName(i.after)}`)))) : null,
    nodes ? h("div", {}, h("b", {}, t("chTree", c.nodesAdded.length, c.nodesRemoved.length)), h("ul", {},
      c.nodesAdded.map((n) => h("li", { class: "pos" }, "+ ", trName(n))), c.nodesRemoved.map((n) => h("li", { class: "neg" }, "− ", trName(n))))) : null,
    gems ? h("div", {}, h("b", {}, t("chGems")), h("ul", {},
      c.gemsAdded.map((n) => h("li", { class: "pos" }, "+ ", trName(n))), c.gemsRemoved.map((n) => h("li", { class: "neg" }, "− ", trName(n))))) : null);
  box.replaceChildren(h("div", { class: "card" },
    h("div", { class: "ch-head" }, h("h3", {}, t("changesTitle")), close),
    notes,
    nothing ? h("p", { class: "muted" }, state.build.kind === "pob" ? t("noChangesPob") : t("noChangesCode")) : [
      c.level[0] !== c.level[1] ? h("div", {}, t("chLevel", c.level[0], c.level[1])) : null,
      rows.length ? h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("chBefore")),
        h("th", { class: "num" }, t("chAfter")), h("th", { class: "num" }, t("change")))),
      h("tbody", {}, ["offence", "defence", "resist", "hits", "attributes", "other"].map((g) => {
        const list = rows.filter((r) => r.group === g);
        return list.length ? [h("tr", { class: "group" }, h("td", { colspan: 4 }, t("grp_" + g))),
          list.map((r) => h("tr", {}, h("td", {}, t("st_" + r.key)), h("td", { class: "num" }, statText(r.key, r.before)),
            h("td", { class: "num" }, statText(r.key, r.after)), diffCell(r.key, r.after, r.before, r.higherBetter)))] : null;
      })))
        : h("div", { class: "hint" }, t("chStatsSame")),
      lists]));
  box.classList.remove("hidden");
}

// forms that replace the build view (add, update, feedback) hide everything tied to the open build
function hideBuildChrome() {
  for (const id of ["#build-header", "#tabs", "#changes", "#build-notice"]) $(id).classList.add("hidden");
}

document.addEventListener("click", (e) => {
  if (!e.target.closest("#main-skill")) document.querySelectorAll("#main-skill .picker-list").forEach((l) => l.classList.add("hidden"));
});

$("#mode").addEventListener("click", (e) => {
  const m = e.target.dataset.mode;
  if (!m || m === state.mode) return;
  state.mode = m;
  document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
  switchTab(state.tab);
});

$("#tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) switchTab(e.target.dataset.tab); });

// ---------- folding cards ----------
// Every card with a heading folds by a click on it: long tabs become a list of headings to open what is needed.
// What is folded is remembered per tab and heading. Cards drawn later (a crafting panel, a chat) fold too.
const FOLD_KEY = "poe2lab.folded";
let folded = new Set();
try { folded = new Set(JSON.parse(localStorage.getItem(FOLD_KEY) || "[]")); } catch (_) { /* storage blocked */ }
const saveFolded = () => { try { localStorage.setItem(FOLD_KEY, JSON.stringify([...folded].slice(-500))); } catch (_) { /* storage blocked */ } };
const foldKey = (head) => `${state.tab}|${head.textContent.trim().slice(0, 80)}`;

function foldable(card) {
  if (card.classList.contains("kpi") || card.children.length < 2) return null;
  const first = card.firstElementChild;
  return first.tagName === "H3" || first.classList.contains("slot-head") || first.querySelector(":scope > h3") ? first : null;
}

function setFolded(card, head, on, remember = true) {
  card.classList.toggle("collapsed", on);
  head.setAttribute("aria-expanded", String(!on));
  if (!remember) return;
  // a card folded by default remembers being opened instead
  const [key, keep] = card.dataset.foldDefault ? ["!" + foldKey(head), !on] : [foldKey(head), on];
  if (keep) folded.add(key); else folded.delete(key);
  saveFolded();
}

function applyFolding(root) {
  root.querySelectorAll(".card").forEach((card) => {
    if (card.dataset.fold) return;
    const head = foldable(card);
    if (!head) return;
    card.dataset.fold = "1";
    head.classList.add("fold-head");
    head.setAttribute("role", "button");
    head.title = t("foldHint");
    head.addEventListener("click", (e) => {
      if (e.target.closest("button, a, input, select, textarea, label, .info")) return;  // the heading's own controls
      setFolded(card, head, !card.classList.contains("collapsed"));
    });
    setFolded(card, head, card.dataset.foldDefault ? !folded.has("!" + foldKey(head)) : folded.has(foldKey(head)), false);
  });
}
new MutationObserver(() => applyFolding($("#view"))).observe($("#view"), { childList: true, subtree: true });

function foldAll(on) {
  $("#view").querySelectorAll(".card[data-fold]").forEach((card) => setFolded(card, card.querySelector(".fold-head"), on));
}
$("#fold-all").addEventListener("click", () => foldAll(true));
$("#unfold-all").addEventListener("click", () => foldAll(false));
$("#refresh-builds").addEventListener("click", loadBuildList);

const TABS = {};

// the address keeps the open build and tab (#build=…&tab=…): a reload or a shared link lands on the same view
function writeHash() {
  if (!state.build) return;
  const q = new URLSearchParams({ build: state.build.name, tab: state.tab });
  if (state.mode !== "balanced") q.set("mode", state.mode);
  history.replaceState(null, "", "#" + q.toString());
}

function readHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  if (q.get("tab") && TABS[q.get("tab")]) state.tab = q.get("tab");
  if (q.get("mode") && ["damage", "balanced", "defence"].includes(q.get("mode"))) {
    state.mode = q.get("mode");
    document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("active", b.dataset.mode === state.mode));
  }
  if (q.get("ref") && q.get("build")) {
    try { localStorage.setItem(`poe2lab.ref.${q.get("build")}`, q.get("ref")); } catch (_) { /* storage blocked */ }
  }
  return q.get("build");
}

async function switchTab(tab) {
  if (tab !== state.tab) document.querySelector("main").scrollTop = 0;  // a new tab starts at its top
  state.tab = tab;
  writeHash();
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  if (!state.build) return;
  const view = $("#view");
  const token = Symbol();
  switchTab.token = token;
  try {
    const content = await TABS[tab](view);
    if (switchTab.token === token && content) view.replaceChildren(content);
  } catch (e) {
    if (switchTab.token === token) view.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("error")), h("p", { class: "muted" }, e.message)));
  }
}

const report = () => cached(`report:${state.mode}`, () => api(`/api/report?mode=${state.mode}&${buildQuery()}`));
// the "unit" is either the Rage stat or a probe mod line
const unitName = (name) => (LANG === "ru" && name === "Maximum Rage" ? "максимум свирепости" : trMod(name));

// ---------- overview ----------
TABS.overview = async (view) => {
  view.replaceChildren(loading(t("calcReport")));
  const r = await report();
  const b = r.baseline;
  const rng = r.damageRange;
  const hits = Object.entries(b.survivableHit);

  const kpi = h("div", { class: "grid kpi" },
    h("div", { class: "card kpi" }, h("div", { class: "label" }, b.minions ? t("dpsMinions") : t("dps")),
      h("div", { class: "value" }, fmt(rng.low), rng.high > rng.low ? h("span", { class: "to" }, ` … ${fmt(rng.high)}`) : null),
      h("div", { class: "note" }, b.minions ? t("minionsNote", b.minions.count, fmt(b.minions.perMinion))
        : rng.high > rng.low ? t("dpsRangeNote") : trName(r.build.mainSkill))),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, b.es > 0 ? t("lifeAndEs") : t("life")),
      h("div", { class: "value" }, fmt(b.life), b.es > 0 ? h("span", { class: "to" }, ` + ${fmt(b.es)}`) : null),
      b.es > 0 ? h("div", { class: "note" }, t("lifeEsNote")) : null),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("hitChance")), h("div", { class: "value" }, fmt(b.hitChance) + "%")),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("recovery")),
      h("div", { class: "value" }, fmt(b.recoveryPerSecond), h("span", { class: "to" }, t("perSec"))),
      h("div", { class: "note" }, b.recoveryPool === "es" ? t("esRecoveryNote") : t("whileAttacking"))));

  // How much of the pool one typical monster hit takes: grows with difficulty (normal < crit < crit on a hard map),
  // which reads the way players think about danger. The raw "largest hit you survive" stays in the tooltip.
  const ref = b.referenceHit;
  const share = (type, survivable) => (survivable >= IMMUNE_HIT ? 0 : (ref[type] / survivable) * 100);
  const worst = hits.filter(([, v]) => v.normal < IMMUNE_HIT)
    .reduce((w, cur) => (!w || share(cur[0], cur[1].juiced) > share(w[0], w[1].juiced) ? cur : w), null);
  const hitCell = (type, survivable) => {
    if (survivable >= IMMUNE_HIT) return h("td", { class: "num hit-cell" }, h("div", { class: "hit-num pos" }, t("immune")));
    const p = share(type, survivable);
    const cls = p >= 100 ? "deadly" : p >= 50 ? "danger" : "";
    return h("td", { class: "num hit-cell " + cls, title: t("hitTooltip", fmt(survivable), fmt(ref[type])) },
      h("div", { class: "hit-num" }, p >= 100 ? t("oneShot") : `${fmt(p)}%`),
      h("div", { class: "hit-hint" }, p >= 100 ? t("oneShotHint") : t("hitsToDie", Math.max(1, Math.ceil(100 / p - 1e-9)))),
      h("div", { class: "hit-track" }, h("span", { style: `width:${Math.min(100, p)}%;background:${DMG_COLOR[type]}` })));
  };
  const hitCard = h("div", { class: "card" },
    h("h3", {}, t("hitsTitle")), h("div", { class: "sub" }, t("hitsSub", r.profile, fmt(ref.Physical), fmt(ref.Chaos))),
    h("table", { class: "hits-table" },
      h("thead", {}, h("tr", {}, h("th", {}, t("dmgType")), h("th", { class: "num" }, t("hitNormal")),
        h("th", { class: "num" }, t("hitCrit")), h("th", { class: "num" }, t(r.profile.stage === "maps" ? "hitJuiced" : "hitStrong")))),
      h("tbody", {}, hits.map(([type, v]) => h("tr", { class: worst && type === worst[0] ? "weak" : "" },
        h("td", {}, h("span", { class: "dmg-dot", style: `background:${DMG_COLOR[type]}` }), t("dmgFull_" + type),
          worst && type === worst[0] ? h("span", { class: "chip must", style: "margin-left:8px" }, t("weakest")) : null),
        hitCell(type, v.normal), hitCell(type, v.crit), hitCell(type, v.juiced))))),
    h("div", { class: "note small muted", style: "margin-top:8px" }, t("hitsNote")));

  const order = { must: 0, priority: 1, warn: 2 };
  const issues = h("div", { class: "card" }, h("h3", {}, t("issuesTitle")), h("div", { class: "sub" }, t("issuesSub")),
    h("div", { class: "issues" }, [...r.gates].sort((a, c) => order[a.level] - order[c.level]).map((g) =>
      h("div", { class: "issue" }, h("div", {}, chip(g.level, t("lvl_" + g.level))),
        h("div", {}, h("div", { class: "t" }, trFree(g.title)), h("div", { class: "d" }, trFree(g.detail)))))));

  for (const list of Object.values(r.attributes.supportsAtRisk || {})) {
    issues.append(h("div", { class: "sub", style: "margin-top:12px" }, t("supportsAtRisk")),
      h("table", {}, h("tbody", {}, list.map((s) => h("tr", {}, h("td", {}, trName(s.name)), h("td", { class: "muted" }, trName(s.skill)),
        h("td", { class: "num" }, pct(s.skill_dps_pct)))))));
  }

  const path = h("div", { class: "card" }, h("h3", {}, t("pathTitle")), h("div", { class: "sub" }, t("pathSub")),
    h("div", { class: "steps" }, r.path.map((s) => h("div", { class: "step" }, h("div", {},
      h("div", { class: "what mod" }, trMod(s.mod)),
      deltas({ dps: s.dps, phys_hit: s.defence.Physical, chaos_hit: s.defence.Chaos, recovery: s.recovery }))))));

  return h("div", { class: "stack" }, kpi, h("div", { class: "grid two" }, hitCard, issues), path);
};

// ---------- damage ----------
TABS.damage = async (view) => {
  view.replaceChildren(loading(t("calcReport")));
  const r = await report();
  const blocks = [];
  const core = r.core;
  if (core.resources.length || core.exchange.length) {
    const res = core.resources.map((x) => h("p", {},
      t("resourceLine", { name: t("res_" + x.name.replace(/ /g, "")), counted: x.counted, assumed: fmt(x.assumed),
        maximum: fmt(x.maximum), without: fmt(x.dps_without), with: fmt(x.dps_with), mult: fmt(x.dps_with / x.dps_without, 2),
        ehp: x.ehp_without && Math.abs(x.ehp_with / x.ehp_without - 1) >= 0.005 ? `EHP ${fmt(x.ehp_without)} → ${fmt(x.ehp_with)}` : "" }),
      x.name === "Rage" && !x.set_in_build ? h("span", { class: "muted" }, t("rageEmpty")) : null));
    blocks.push(h("div", { class: "card" }, h("h3", {}, t("coreTitle")), res,
      core.unit ? h("div", { class: "sub" }, t("rate", unitName(core.unit.name), pct(core.unit.dps_pct_per_point))) : null,
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("colMod")), h("th", { class: "num" }, "DPS"), h("th", { class: "num" }, t("colUnits")))),
        h("tbody", {}, core.exchange.slice(0, 12).map((x) => h("tr", {}, h("td", { class: "mod", title: x.mod }, trMod(x.mod)), h("td", { class: "num" }, pct(x.dps)), h("td", { class: "num" }, fmt(x.points, 1))))))));
  }

  const rng = r.damageRange;
  const off = r.conditions.filter((c) => !c.checked);
  const on = r.conditions.filter((c) => c.checked);
  const condRow = (c) => h("tr", {}, h("td", { title: c.label }, conditionLabel(c.label)),
    h("td", {}, deltas({ dps: c.dps_pct, phys_hit: c.phys_hit_pct, chaos_hit: c.chaos_hit_pct, recovery: c.recovery_pct }, METRIC, 0.5)));
  const [a, lo, b2, hi, c2] = t("range", fmt(rng.low), fmt(rng.high), fmt(rng.high / rng.low, 2));
  blocks.push(h("div", { class: "card" }, h("h3", {}, t("condTitle")),
    rng.conditions.length ? h("p", {}, a, h("b", {}, lo), b2, h("b", {}, hi), c2) : null,
    off.length ? h("div", { class: "sub" }, t("condOff")) : null,
    off.length ? h("table", {}, h("tbody", {}, off.map(condRow))) : null,
    on.length ? h("div", { class: "sub", style: "margin-top:12px" }, t("condOn")) : null,
    on.length ? h("table", {}, h("tbody", {}, on.map(condRow))) : null));

  const max = Math.max(...r.ranking.map((x) => x.score), 1);
  blocks.push(h("div", { class: "card" }, h("h3", {}, t("investTitle")), h("div", { class: "sub" }, t("investSub")),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("colMod")), h("th", {}, t("colEffect")), h("th", { class: "num" }, t("colScore")))),
      h("tbody", {}, r.ranking.map((x) => h("tr", {}, h("td", { class: "mod", title: x.mod }, trMod(x.mod)),
        h("td", {}, deltas({ dps: x.dps, phys_hit: x.physHit, chaos_hit: x.chaosHit, recovery: x.recovery })),
        h("td", { class: "num" }, scoreBar(x.score, max))))))));

  return h("div", { class: "grid two" }, blocks);
};

// ---------- gear ----------
TABS.gear = async (view) => {
  view.replaceChildren(loading(t("calcGear")));
  const g = await cached(`gear:${state.mode}`, () => api(`/api/gear?mode=${state.mode}&${buildQuery()}`));

  // the item a step is about, as its picture: many slots, so the eye finds the right one at once
  const slotItem = (slot) => (state.build.items || []).find((i) => i.slot === slot);
  const slotIcon = (slot) => { const it = slotItem(slot); return it ? itemIcon(it.name, it.baseName, it.rarity) : null; };
  const path = h("div", { class: "card" }, h("h3", {}, t("craftTitle")), h("div", { class: "sub" }, t("craftSub")),
    g.craftPath.length ? h("div", { class: "steps" }, g.craftPath.map((s) => h("div", { class: "step" }, h("div", { class: "step-body" },
      h("div", { class: "what" }, slotIcon(s.slot), chip("tag", slotName(s.slot)), " ",
        s.removed.length ? h("span", {}, h("span", { class: "mod muted" }, trMod(s.removed.join(" / "))), " → ") : t("craftAdd"),
        h("span", { class: "mod" }, trMod(s.added.join(" / ")))),
      deltas(s.changes),
      howBlock(s.how))))) : h("p", { class: "muted" }, t("nothingToCraft")));

  const socketCard = h("div", { class: "card" }, h("h3", {}, t("socketsTitle")),
    h("div", { class: "sub" }, t("socketsSub") + (g.prices ? t("prices", trName(g.prices.league)) : "")),
    g.sockets.length ? g.sockets.map((s) => h("div", { style: "margin-bottom:12px" },
      h("div", { class: "row sock-row", style: "gap:6px" }, slotIcon(s.slot), chip("tag", slotName(s.slot)), t("socketNow", s.index),
        h("b", { class: "named" }, icon(s.current), trName(s.current)), h("span", { class: "muted" }, t("gives", fmt(s.current_score, 1)))),
      s.best.length ? h("table", {}, h("tbody", {}, s.best.map((o) => h("tr", {},
        h("td", {}, h("div", { class: "named" }, icon(o.name, "ico rune"), trName(o.name)), h("div", { class: "mod muted" }, trMod(o.lines.join(" / ")))),
        h("td", {}, deltas(o.changes)), h("td", { class: "num" }, trFree(o.price || ""))))))
        : h("div", { class: "muted small" }, t("nothingBetter"))))
      : h("p", { class: "muted" }, t("noSockets")));

  const cards = g.slots.map((p) => {
    const max = Math.max(...p.affixes.map((a) => a.score), 1);
    return h("div", { class: "card" },
      h("div", { class: "slot-head" }, h("div", { class: "row", style: "gap:0;flex-wrap:nowrap" }, itemIcon(p.item, p.base, p.rarity),
        h("div", {}, h("div", { class: "slot" }, slotName(p.slot)), h("h3", { title: p.item }, trItem(p.item)))),
        chip(p.corrupted ? "must" : "tag", p.corrupted ? t("corrupted") : t("craftable"))),
      h("div", { class: "sub" }, t("affixCount", { ...p, base: trName(p.base) }) + (p.uncertain ? t("approx") : "")),
      p.affixes.map((a) => h("div", { class: "affix" },
        h("div", { class: "kind" }, a.type === "Prefix" ? t("prefix") : t("suffix")),
        h("div", {}, h("span", { class: "mod", title: a.lines.join(" / ") }, trMod(a.lines.join(" / "))), h("span", { class: "tier" }, `${LANG === "ru" ? "тир " : "T"}${a.tier}/${a.tiers}`),
          a.holds.length ? h("div", {}, chip("hold", t("holds") + a.holds.map(trFree).join(", "))) : null,
          a.utility ? h("div", {}, chip("util", t("utility"))) : null),
        scoreBar(a.score, max))),
      p.actions.length ? h("div", { class: "actions" }, p.actions.map((x) => h("div", { class: "action" }, trFree(x)))) : null,
      craftBlock(p.slot));
  });

  return h("div", { class: "stack" }, craftGuide(), h("div", { class: "grid two" }, path, socketCard),
    h("div", { class: "section-title" }, t("slots")), h("div", { class: "grid cards" }, cards));
};

// ---------- how to craft: the general principles, cheap to expensive ----------
// The same for armour, weapons and jewellery; the currency rules come from the game's own descriptions. Each step
// names its items in English ({0}, {1}...) for icons and translation; prices come live from poe.ninja.
const CRAFT_GUIDE = [
  ["cheap", [["g_bases", []], ["g_transmute", ["Orb of Transmutation", "Orb of Augmentation"]],
    ["g_regal", ["Regal Orb", "Exalted Orb", "Omen of Greater Exaltation"]], ["g_goal", []]]],
  ["essence", [["g_essence", ["Greater Essence of the Body"]], ["g_bone", ["Gnawed Rib", "Omen of Abyssal Echoes"]]]],
  ["fracture", [["g_fracture", ["Fracturing Orb"]], ["g_after_fracture", ["Chaos Orb", "Orb of Annulment"]]]],
  ["expensive", [["g_perfect", ["Perfect Essence of the Body"]], ["g_grades", ["Greater Exalted Orb", "Perfect Exalted Orb"]],
    ["g_annul_side", ["Orb of Annulment", "Omen of Sinistral Annulment", "Omen of Dextral Annulment"]],
    ["g_homog", ["Omen of Homogenising Exaltation"]]]],
];

// "{0} and {1}": the placeholders become the items' pictures and names
const namedItem = (n) => h("span", { class: "named" }, icon(n), trName(n));
const withItems = (text, names) => text.split(/(\{\d\})/).map((part) => {
  const m = part.match(/^\{(\d)\}$/);
  return m ? namedItem(names[Number(m[1])]) : part;
});

function craftGuide() {
  const priceLines = [];  // one per level: filled once the prices come
  const levels = CRAFT_GUIDE.map(([level, steps]) => {
    const names = [...new Set(steps.flatMap(([, n]) => n))];
    const priceLine = h("div", { class: "guide-prices small muted" });
    priceLines.push([priceLine, names]);
    return h("div", { class: "guide-level" }, h("b", {}, t("g_level_" + level)),
      h("ul", {}, steps.map(([k, n]) => h("li", {}, withItems(t(k), n)))), priceLine);
  });
  const card = h("div", { class: "card craft-guide", "data-fold-default": "1" },
    h("h3", {}, t("crGuideTitle")), h("div", { class: "sub" }, t("crGuideSub")), levels,
    h("p", { class: "small" }, withItems(t("g_classes"), ["Gnawed Rib", "Gnawed Jawbone", "Gnawed Collarbone"])));
  cached("craftGuide", () => api("/api/craft/guide")).then((r) => {
    for (const [line, names] of priceLines) {
      const known = names.filter((n) => r.prices[n]);
      if (known.length) line.replaceChildren(t("g_prices"), " ", ...known.map((n) => h("span", { class: "guide-price" }, icon(n), trFree(r.prices[n]))));
    }
    card.querySelector(".sub").append(r.league ? t("prices", trName(r.league)) : "");
  }).catch(() => { /* no prices: the guide still reads */ });
  return card;
}

// ---------- changing a mod on a worn item: the ways, the chance per try, a verdict ----------
const VERDICT_CHIP = { worth: "ok", risky: "priority", lottery: "must" };
const chanceText = (p) => `${fmt(p * 100, p >= 0.1 ? 0 : p >= 0.01 ? 1 : 2)}%`;

function howBlock(how) {
  if (!how) return null;
  return h("div", { class: "src" },
    h("div", { class: "how-verdict" }, chip(VERDICT_CHIP[how.verdict], t("rtVerdict_" + how.verdict)), " ",
      h("span", { class: "muted small" }, t("rtVerdictHint_" + how.verdict))),
    how.routes.length ? h("ul", { class: "src-list how-routes" }, how.routes.map((r) => h("li", {},
      withItems(t("rt_" + r.k, r.mod ? trMod(r.mod) : ""), r.n), " — ", h("b", {}, t("rtChance", chanceText(r.chance))),
      r.echoes ? h("span", { class: "muted" }, " " + t("rtEchoes", chanceText(r.echoes))) : null,
      h("span", { class: "muted" }, " " + t("rtRisk_" + r.risk)),
      h("div", { class: "muted small" }, t("g_prices"), " ", r.n.map((n, i) => r.prices[i]
        ? h("span", { class: "guide-price" }, icon(n), trFree(r.prices[i]), " ") : null))))) : null);
}

// ---------- crafting a slot's item from a white base ----------
const craftState = {};  // per slot: the settings last used, so a re-render keeps them

function craftBlock(slot) {
  const box = h("div", { class: "craft" });
  const btn = h("button", { class: "ghost small", onclick: () => { btn.remove(); openCraft(box, slot); } }, t("crButton"));
  box.append(btn);
  if (craftState[slot]) { btn.remove(); openCraft(box, slot); }
  return box;
}

function openCraft(box, slot) {
  const st = craftState[slot] = craftState[slot] || { need: 3, grade: "", itemLevel: 82, quality: "good" };
  const out = h("div", {});
  const select = (key, options) => h("select", { onchange: (e) => { st[key] = e.target.value; run(); } },
    options.map(([v, label]) => h("option", { value: v, selected: String(st[key]) === String(v) }, label)));
  const ilvl = h("input", { type: "number", min: 1, max: 100, value: st.itemLevel, style: "width:64px",
    onchange: (e) => { st.itemLevel = Math.max(1, Math.min(100, Number(e.target.value) || 82)); run(); } });
  const controls = h("div", { class: "row craft-controls" },
    h("label", {}, t("crNeed"), " ", select("need", [1, 2, 3, 4, 5].map((n) => [n, t("crNeedN", n)]))),
    h("label", {}, t("crQuality"), " ", select("quality", [["good", t("crQualityGood")], ["top", t("crQualityTop")], ["any", t("crQualityAny")]])),
    h("label", {}, t("crGrade"), " ", select("grade", [["", t("crGradeNormal")], ["greater", t("crGradeGreater")], ["perfect", t("crGradePerfect")]])),
    h("label", {}, t("crIlvl"), " ", ilvl));
  box.replaceChildren(h("div", { class: "craft-head" }, h("b", {}, t("crTitle")), h("div", { class: "sub" }, t("crSub"))), controls, out);

  async function run() {
    out.replaceChildren(loading(t("crLoading")));
    const q = `slot=${encodeURIComponent(slot)}&need=${st.need}&grade=${st.grade}&item_level=${st.itemLevel}&quality=${st.quality}&mode=${state.mode}`;
    try {
      const r = await cached(`craft:${q}`, () => api(`/api/craft?${q}&${buildQuery()}`));
      out.replaceChildren(renderCraft(r));
    } catch (e) {
      out.replaceChildren(h("p", { class: "muted" }, e.message));
    }
  }
  run();
}

function renderCraft(r) {
  if (!r.targets.length) return h("p", { class: "muted" }, t("crNoTargets"));
  const named = namedItem;
  // a price in divines, or in exalted orbs when it is under one divine
  const money = (div) => {
    if (div === null || div === undefined) return "—";
    if (div < 1 && r.exaltedPerDivine) return `${fmt(div * r.exaltedPerDivine, div * r.exaltedPerDivine < 10 ? 1 : 0)} ex`;
    return `${fmt(div, div < 10 ? 2 : 0)} div`;
  };
  // "{0} with {1}": the placeholders become the items' pictures and names
  const stepText = (s) => withItems(t("crStep_" + s.k, s.mod ? trMod(s.mod) : ""), s.n);
  const targets = h("div", {}, h("div", { class: "sub" }, t("crTargets", r.need, r.targets.length)),
    h("ul", { class: "craft-targets" }, r.targets.map((x) => h("li", {},
      chip("tag", x.side === "Prefix" ? t("prefix") : t("suffix")), " ", h("span", { class: "mod" }, trMod(x.label)),
      h("span", { class: "muted small" }, " " + t("crFromLevel", x.min_level))))));
  const working = r.strategies.filter((s) => s.per_base > 0);
  const cards = r.strategies.map((s) => {
    const best = working.length && s === working[0];
    if (!s.per_base) {
      return h("div", { class: "sk-item craft-never" }, h("b", {}, t("crStrategy_" + s.key)), h("div", { class: "muted small" }, t("crNever")));
    }
    const uses = Object.entries(s.use).sort((a, b) => b[1] - a[1]);
    return h("div", { class: "sk-item" + (best ? " best" : "") },
      h("div", { class: "row", style: "justify-content:space-between" }, h("b", {}, t("crStrategy_" + s.key)),
        best ? chip("tag", t("crBest")) : null),
      h("div", { class: "craft-nums" },
        h("span", {}, t("crPerBase"), " ", h("b", {}, `${fmt(s.per_base * 100, s.per_base < 0.01 ? 2 : s.per_base < 0.1 ? 1 : 0)}%`),
          s.successes < 10 ? h("span", { class: "muted", title: t("crRoughHint", s.successes, s.attempts) }, " " + t("crRough")) : null),
        h("span", {}, t("crBases"), " ", h("b", {}, fmt(s.bases, s.bases < 10 ? 1 : 0)), h("span", { class: "muted" }, ` / ${t("crBadLuck")} ${s.bases_p90}`)),
        s.cost !== null && s.cost !== undefined ? h("span", {}, t("crCost"), " ", h("b", {}, money(s.cost)),
          h("span", { class: "muted" }, ` / ${t("crBadLuck")} ${money(s.cost_p90)}`), s.priced ? null : h("span", { class: "muted" }, " " + t("crPartPriced"))) : null,
        r.exaltedPerDivine ? h("span", {}, t("crBasesCost"), " ", h("b", {}, `${money(s.bases * 10 / r.exaltedPerDivine)} – ${money(s.bases * 20 / r.exaltedPerDivine)}`)) : null),
      h("ol", { class: "craft-steps" }, s.steps.map((x) => h("li", {}, stepText(x)))),
      h("details", {}, h("summary", {}, t("crUse")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th", {}), h("th", { class: "num" }, t("crColAvg")),
          h("th", { class: "num" }, t("crBadLuck")), h("th", { class: "num" }, t("crColPrice")))),
        h("tbody", {}, uses.map(([n, v]) => h("tr", {}, h("td", {}, named(n)),
          h("td", { class: "num" }, fmt(v, v < 10 ? 1 : 0)), h("td", { class: "num muted" }, fmt(s.p90[n], s.p90[n] < 10 ? 1 : 0)),
          h("td", { class: "num muted small" }, r.prices[n] ? trFree(r.prices[n]) : "—")))))));
  });
  return h("div", { class: "stack", style: "gap:10px" }, targets,
    r.essence ? h("div", { class: "small" }, t("crEssence"), " ", named(r.essence)) : null,
    h("div", { class: "craft-list" }, cards),
    h("div", { class: "note small muted" }, t(r.estimatedWeights ? "crWeightsNote" : "crWeightsReal") +
      (r.league ? " " + t("prices", trName(r.league)) : "")));
}

// ---------- compare ----------
const refKey = () => `poe2lab.ref.${state.build.name}`;
function savedRef() { try { return localStorage.getItem(refKey()) || ""; } catch (_) { return ""; } }
function saveRef(name) { try { localStorage.setItem(refKey(), name); } catch (_) { /* storage blocked */ } }

TABS.compare = async (view) => {
  state.compareMode = state.compareMode || "versus";
  const body = h("div", {});
  const seg = h("div", { class: "segmented" }, [["versus", t("cmpVersus")], ["item", t("cmpItem")]].map(([m, label]) =>
    h("button", { class: state.compareMode === m ? "active" : "", onclick: () => { state.compareMode = m; switchTab("compare"); } }, label)));
  body.append(await (state.compareMode === "versus" ? versusView() : itemView()));
  return h("div", { class: "stack" }, h("div", {}, seg), body);
};

// ---- my build against a reference (a guide with its gear) ----
async function versusView() {
  const builds = (await api("/api/builds")).filter((b) => b.name !== state.build.name);
  const sel = h("select", {}, h("option", { value: "" }, t("pickRef")), builds.map((b) => h("option", { value: b.name }, b.name)));
  sel.value = builds.some((b) => b.name === savedRef()) ? savedRef() : "";
  const out = h("div", { class: "stack" });
  const run = async () => {
    if (!sel.value) { out.replaceChildren(); return; }
    saveRef(sel.value);
    out.replaceChildren(loading(t("refLoading")));
    try {
      const v = await cached("versus:" + sel.value, () => api(`/api/versus?ref=${encodeURIComponent(sel.value)}&${buildQuery()}`));
      out.replaceChildren(...renderVersus(v, sel.value));
    } catch (e) { out.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
  };
  sel.addEventListener("change", run);
  const head = h("div", { class: "card" }, h("h3", {}, t("refTitle")), h("div", { class: "sub" }, t("refSub")),
    h("label", { class: "field", style: "max-width:420px" }, h("span", {}, t("refBuild")), sel),
    builds.length ? null : h("p", { class: "muted small" }, t("refNone")));
  if (sel.value) run();
  return h("div", { class: "stack" }, head, out);
}

const STAT_FMT = {
  dps: (v) => fmt(v), hitChance: (v) => fmt(v) + "%", critChance: (v) => fmt(v, 1) + "%", speed: (v) => fmt(v, 2),
  moveSpeed: (v) => pct((v - 1) * 100),
};
const IMMUNE_HIT = 1e9;  // the engine's value for an infinite survivable hit (immunity)
const statText = (key, v) => (key.startsWith("hit_") && v >= IMMUNE_HIT ? t("immune")
  : STAT_FMT[key] ? STAT_FMT[key](v) : key.startsWith("res_") ? fmt(v) + "%" : fmt(v));

// difference cell: from my side (+ means I have more); green when that is the better direction
function diffCell(key, mine, ref, higherBetter = true) {
  if (key.startsWith("hit_") && (mine >= IMMUNE_HIT || ref >= IMMUNE_HIT)) {
    if (mine >= IMMUNE_HIT && ref >= IMMUNE_HIT) return h("td", { class: "num muted" }, "=");
    return h("td", { class: "num " + ((mine >= IMMUNE_HIT) === higherBetter ? "pos" : "neg") }, mine >= IMMUNE_HIT ? t("immune") : t("notImmune"));
  }
  const d = mine - ref;
  if (Math.abs(d) < 1e-9 || (Math.abs(ref) > 0 && Math.abs(d / ref) < 0.005)) return h("td", { class: "num muted" }, "=");
  const good = (d > 0) === higherBetter;
  const rel = ref ? ` (${pct((d / Math.abs(ref)) * 100)})` : "";
  const digits = key === "speed" ? 2 : key.startsWith("res_") || key === "hitChance" || key === "critChance" ? 1 : 0;
  const abs = `${d > 0 ? "+" : ""}${fmt(d, digits)}`;
  return h("td", { class: "num " + (good ? "pos" : "neg") }, key === "moveSpeed" ? pct(d * 100) : abs + (key.startsWith("res_") ? "" : rel));
}

function renderVersus(v, refName) {
  const groups = ["offence", "defence", "resist", "hits", "attributes", "other"];
  const rows = [];
  for (const g of groups) {
    const list = v.rows.filter((r) => r.group === g && !(r.mine === 0 && r.ref === 0));
    if (!list.length) continue;
    rows.push(h("tr", { class: "group" }, h("td", { colspan: 4 }, t("grp_" + g))));
    for (const r of list) rows.push(h("tr", {}, h("td", {}, t("st_" + r.key)),
      h("td", { class: "num" }, statText(r.key, r.mine)), h("td", { class: "num" }, statText(r.key, r.ref)),
      diffCell(r.key, r.mine, r.ref, r.higherBetter)));
  }
  const sameSkill = v.mineSkill === v.refSkill;
  const stats = h("div", { class: "card" }, h("h3", {}, t("refStats")),
    h("div", { class: "sub" }, t("refStatsSub", trName(v.mineSkill), trName(v.refSkill))),
    sameSkill ? null : h("div", { class: "action" }, t("refSkillDiffers")),
    h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("mine")),
      h("th", { class: "num" }, refName), h("th", { class: "num" }, t("diffMine")))), h("tbody", {}, rows)));

  const swapCell = (s) => {
    if (s.error) return h("td", {}, chip("must", t("cannotEquip")));
    if (!s.swap) return h("td", { class: "muted small" }, t("refEmpty"));
    if (s.swap.dps_pct <= -99) return h("td", {}, chip("must", t("wrongWeapon")));
    const c = s.swap;
    return h("td", {}, deltas({ dps: c.dps_pct, phys_hit: c.hit_pct.Physical, fire_hit: c.hit_pct.Fire, cold_hit: c.hit_pct.Cold,
      lightning_hit: c.hit_pct.Lightning, chaos_hit: c.hit_pct.Chaos, recovery: c.recovery_pct }, METRIC, 0.5),
      Object.entries(c.unmet_requirements).map(([a, [have, need]]) => chip("must", t("reqShort", attrName(a), fmt(have), fmt(need)))));
  };
  const itemName = (it) => (it ? h("span", { title: it.name, class: "named" }, icon(it.name.split(",")[0].trim()), trItem(it.name)) : h("span", { class: "muted" }, "—"));
  const slots = h("div", { class: "card" }, h("h3", {}, t("refItems")), h("div", { class: "sub" }, t("refItemsSub")),
    h("table", { class: "versus-items" }, h("thead", {}, h("tr", {}, h("th", {}, t("slot")), h("th", {}, t("mine")),
      h("th", {}, refName), h("th", {}, t("ifWear")), h("th", {}, ""))),
    h("tbody", {}, v.slots.map((s) => h("tr", {}, h("td", {}, slotName(s.slot)), h("td", {}, itemName(s.mine)),
      h("td", {}, itemName(s.ref)), swapCell(s),
      h("td", {}, s.ref && !s.error ? h("button", { class: "ghost small", onclick: () => openInItemCompare(refName, s.slot) }, t("details")) : null))))));

  let all = null;
  if (v.allGear) {
    const mine = Object.fromEntries(v.rows.map((r) => [r.key, r.mine]));
    const keys = ["dps", "life", "es", "ehp", "hit_Physical", "hit_Chaos", "res_Fire", "res_Cold", "res_Lightning", "res_Chaos", "spiritFree"]
      .filter((k) => mine[k] || v.allGear[k]);
    all = h("div", { class: "card" }, h("h3", {}, t("refAllGear")), h("div", { class: "sub" }, t("refAllGearSub")),
      h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("now")),
        h("th", { class: "num" }, t("withTheirGear")), h("th", { class: "num" }, t("change")))),
      h("tbody", {}, keys.map((k) => h("tr", {}, h("td", {}, t("st_" + k)), h("td", { class: "num" }, statText(k, mine[k])),
        h("td", { class: "num" }, statText(k, v.allGear[k])), diffCell(k, v.allGear[k], mine[k]))))));
  }
  return [stats, slots, all].filter(Boolean);
}

async function openInItemCompare(ref, slot) {
  try {
    const r = await api(`/api/versus/item?ref=${encodeURIComponent(ref)}&slot=${encodeURIComponent(slot)}`);
    state.compareMode = "item";
    state.itemCompare = { slot, text: r.text, from: ref };
    switchTab("compare");
  } catch (e) { toast(e.message); }
}

// ---- one candidate item against the equipped one ----
async function itemView() {
  const pre = state.itemCompare || {};
  state.itemCompare = null;
  const items = state.build.items.filter((i) => !["Flask", "Charm", "Jewel"].includes(i.type));
  const slotSel = h("select", {}, items.map((i) => h("option", { value: i.slot }, slotName(i.slot))));
  if (pre.slot) slotSel.value = pre.slot;
  const current = h("div", { class: "item-card" });
  const showCurrent = () => {
    const it = items.find((i) => i.slot === slotSel.value);
    current.replaceChildren(it ? h("div", {}, h("div", { class: "item-name", title: it.name }, trItem(it.name)),
      h("ul", { class: "item-lines" }, it.explicit.map((l) => h("li", { class: l.desecrated ? "desecrated" : l.crafted ? "crafted" : "" }, trMod(l.line)))))
      : h("p", { class: "muted" }, t("slotEmpty")));
  };
  slotSel.addEventListener("change", showCurrent);
  showCurrent();

  const text = h("textarea", { rows: 14, placeholder: t("candidatePh"), spellcheck: "false" }, pre.text || "");
  const be = h("input", { type: "text", placeholder: t("breakevenPh"), style: "width:100%" });
  const out = h("div", {});
  const ref = savedRef();
  const fillFromRef = ref ? h("button", { class: "ghost small", onclick: async () => {
    try { text.value = (await api(`/api/versus/item?ref=${encodeURIComponent(ref)}&slot=${encodeURIComponent(slotSel.value)}`)).text; }
    catch (e) { toast(e.message); }
  } }, t("fromRef", ref)) : null;
  const fillCurrent = h("button", { class: "ghost small", onclick: async () => {
    text.value = (await api(`/api/item/${encodeURIComponent(slotSel.value)}`)).text;
  } }, t("insertCurrent"));
  const run = h("button", { class: "primary", onclick: async () => {
    if (!text.value.trim()) { text.focus(); return; }
    run.disabled = true;
    out.replaceChildren(loading(t("counting")));
    try {
      const r = await api("/api/compare", { method: "POST", body: { slot: slotSel.value, text: text.value, breakeven: be.value.trim() || null } });
      out.replaceChildren(renderItemResult(r));
    } catch (e) { out.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
    run.disabled = false;
  } }, t("compare"));

  const left = h("div", { class: "card stack" }, h("h3", {}, t("step1")),
    h("label", { class: "field" }, h("span", {}, t("slot")), slotSel), h("div", { class: "sub" }, t("equippedNow")), current);
  const right = h("div", { class: "card stack" }, h("h3", {}, t("step2")),
    pre.from ? h("div", { class: "action" }, t("loadedFromRef", pre.from)) : null,
    h("div", { class: "row" }, fillFromRef, fillCurrent), text,
    h("details", {}, h("summary", {}, t("breakeven")), h("div", { class: "sub" }, t("breakevenHelp")), be),
    h("div", {}, run));
  if (pre.text) setTimeout(() => run.click(), 0);
  return h("div", { class: "stack" }, h("div", { class: "grid two" }, left, right), out);
}

function renderItemResult(r) {
  const hitVals = Object.values(r.hit_pct);
  const minHit = Math.min(...hitVals), maxHit = Math.max(...hitVals);
  let cls, title;
  if (Math.abs(r.dps_pct) <= 0.5 && Math.abs(minHit) <= 0.5 && Math.abs(maxHit) <= 0.5) { cls = "same"; title = t("vSame"); }
  else if (r.dps_pct >= -0.5 && minHit >= -0.5) { cls = "better"; title = t("vBetter"); }
  else if (r.dps_pct <= 0.5 && maxHit <= 0.5) { cls = "worse"; title = t("vWorse"); }
  else { cls = "mixed"; title = t("vMixed", pct(r.dps_pct), pct(minHit)); }
  const b = r.before, a = r.after;
  const keys = ["dps", "life", "es", "ehp", "recovery", "hit_Physical", "hit_Fire", "hit_Cold", "hit_Lightning", "hit_Chaos",
    "res_Fire", "res_Cold", "res_Lightning", "res_Chaos"].filter((k) => b[k] || a[k]);
  return h("div", { class: "card" },
    h("div", { class: "verdict " + cls }, title),
    Object.entries(r.unmet_requirements).map(([at, [have, need]]) => h("p", {}, chip("must", t("reqShort", attrName(at), fmt(have), fmt(need))))),
    h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("now")),
      h("th", { class: "num" }, t("withCandidate")), h("th", { class: "num" }, t("change")))),
    h("tbody", {}, keys.map((k) => h("tr", {}, h("td", {}, t("st_" + k)), h("td", { class: "num" }, statText(k, b[k])),
      h("td", { class: "num" }, statText(k, a[k])), diffCell(k, a[k], b[k]))))),
    r.breakeven !== undefined ? h("p", {}, r.breakeven ? t("beOk", trMod(r.breakeven.line), fmt(r.breakeven.factor * 100)) : t("beBad")) : null);
}

// ---------- passive tree ----------
TABS.tree = async (view) => {
  view.replaceChildren(loading(t("treeLoading")));
  const points = state.treePoints || 6;
  const r = await cached(`tree:${state.mode}:${points}`, () => api(`/api/tree?mode=${state.mode}&points=${points}&${buildQuery()}`));
  const pointsSel = h("select", { onchange: (e) => { state.treePoints = Number(e.target.value); switchTab("tree"); } },
    [3, 4, 5, 6, 8, 10].map((n) => h("option", { value: n, selected: n === points }, t("upToPoints", n))));
  const nodeName = (n) => h("span", { title: n.name, class: "named" }, icon(n.name, "ico passive"), trName(n.name));
  const typeChip = (type) => type === "Keystone" ? chip("tag", t("keystone")) : type === "Notable" ? chip("warn", t("notable")) : null;
  const stats = (lines) => h("ul", { class: "item-lines small" }, lines.map((l) => h("li", { title: l }, trMod(l))));
  const maxValue = Math.max(0.01, ...r.growth.map((g) => g.perPoint));

  const growth = h("div", { class: "card" }, h("h3", {}, t("treeGrowth")),
    h("div", { class: "sub" }, t("treeGrowthSub", t("mode_" + state.mode))),
    h("label", { class: "field", style: "max-width:220px;margin-bottom:10px" }, h("span", {}, t("reach")), pointsSel),
    r.growth.length ? h("table", { class: "versus-items" },
      h("thead", {}, h("tr", {}, h("th", {}, t("node")), h("th", { class: "num" }, t("points")), h("th", {}, t("perPoint")), h("th", {}, t("treeGives")), h("th", {}, ""))),
      h("tbody", {}, r.growth.map((g) => h("tr", {},
        h("td", {}, h("div", {}, nodeName(g), " ", typeChip(g.type)), stats(g.stats),
          g.via.length ? h("div", { class: "hint" }, t("via", [...new Set(g.via.map(trName))].join(", "))) : null),
        h("td", { class: "num" }, g.points),
        h("td", {}, scoreBar(g.perPoint, maxValue)),
        h("td", {}, deltas(g.changes, METRIC, 0.3)),
        h("td", {}, editButton("add", g))))))
      : h("p", { class: "muted" }, t("treeNothing")));

  // the other nodes that go with a branch (only reachable through it): they explain uneven numbers
  const alongWith = (names) => {
    if (!names || !names.length) return null;
    const counts = {};
    names.forEach((n) => { counts[n] = (counts[n] || 0) + 1; });
    return h("div", { class: "hint" }, t("alongWith", Object.entries(counts)
      .map(([n, c]) => (c > 1 ? `${c}× ${trName(n)}` : trName(n))).join(", ")));
  };
  const branchRow = (b) => h("tr", {},
    h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type)), stats(b.stats), alongWith(b.with)),
    h("td", { class: "num" }, b.points), h("td", {}, deltas(b.changes, METRIC, 0.3)), h("td", {}, editButton("remove", b)));
  const respec = h("div", { class: "card" }, h("h3", {}, t("treeRespec")), h("div", { class: "sub" }, t("treeRespecSub")),
    r.respec.length ? h("table", { class: "versus-items" },
      h("thead", {}, h("tr", {}, h("th", {}, t("branch")), h("th", { class: "num" }, t("freed")), h("th", {}, t("youLose")), h("th", {}, ""))),
      h("tbody", {}, r.respec.map(branchRow)))
      : h("p", { class: "muted" }, t("treeNoRespec")));

  const listCard = (title, sub, list) => list.length ? h("div", { class: "card" },
    h("details", {}, h("summary", {}, `${title} (${list.length})`), h("div", { class: "sub", style: "margin-top:8px" }, sub),
      h("table", { class: "versus-items" }, h("tbody", {}, list.map((b) => h("tr", {},
        h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type)), stats(b.stats)), h("td", { class: "num" }, t("pointsN", b.points)),
        h("td", {}, editButton("remove", b)))))))) : null;

  return h("div", { class: "stack" },
    h("div", { class: "sub" }, t("treeIntro", r.allocated)),
    planCard(r.plan), growth, respec,
    listCard(t("treeUnseen"), t("treeUnseenSub"), r.unseen),
    listCard(t("treeAttributes"), t("treeAttributesSub"), r.attributes));
};

// ---- tree plan: edits live in the engine only; every tab computes with them until reset ----
async function treeCall(path, body, busyText) {
  const view = $("#view");
  view.replaceChildren(loading(busyText || t("counting")));
  try {
    const r = await api(path, { method: "POST", body: body || {} });
    resetCache();
    await switchTab("tree");
    return r;
  } catch (e) { toast(e.message); switchTab("tree"); return null; }
}

function editButton(action, node) {
  return h("button", { class: "ghost small nowrap", title: action === "add" ? t("takeHint") : t("dropHint"),
    onclick: () => treeCall(`/api/tree/${action}`, { id: node.id, name: node.name }) }, action === "add" ? t("take") : t("drop"));
}

function planCard(plan) {
  const optimize = h("button", { class: "primary", onclick: async () => {
    const r = await treeCall("/api/tree/optimize", { mode: state.mode, seed: Math.floor(Math.random() * 1e9) }, t("optimizing"));
    if (r) toast(r.found ? t("optimized", r.found) : t("optimizedNone"), !!r.found);
  } }, plan && plan.log.length ? t("optimizeMore") : t("optimize"));
  const reset = plan ? h("button", { class: "ghost", onclick: () => treeCall("/api/tree/reset") }, t("planReset")) : null;
  const save = plan && plan.log.length ? h("button", { class: "ghost", onclick: async () => {
    try {
      const r = await api("/api/tree/save", { method: "POST", body: {} });
      toast(t("planSaved", r.name), true);
      loadBuildList();
    } catch (e) { toast(e.message); }
  } }, t("planSave")) : null;
  const names = (list) => {
    const counts = {};
    (list || []).forEach((n) => { counts[n] = (counts[n] || 0) + 1; });
    return Object.entries(counts).map(([n, c]) => (c > 1 ? `${c}× ${trName(n)}` : trName(n))).join(", ");
  };
  const logLine = (e) => e.action === "swap"
    ? h("li", {}, h("span", { class: "neg" }, `− ${names(e.removed)}`), h("br"), h("span", { class: "pos" }, `+ ${names(e.added)}`))
    : e.action === "add" ? h("li", { class: "pos" }, `+ ${trName(e.target)} (${t("pointsN", e.nodes.length)}): ${names(e.nodes)}`)
      : h("li", { class: "neg" }, `− ${trName(e.target)} (${t("pointsN", e.nodes.length)}): ${names(e.nodes)}`);
  const over = plan && plan.used > plan.budget;
  return h("div", { class: "card plan" },
    h("h3", {}, t("planTitle")), h("div", { class: "sub" }, t("planSub", t("mode_" + state.mode))),
    plan ? h("div", { class: "stack" },
      h("div", {}, h("b", { class: over ? "neg" : "" }, t("planPoints", plan.used, plan.budget)),
        over ? h("span", { class: "neg" }, " " + t("planOver", plan.used - plan.budget)) : null),
      h("div", {}, h("div", { class: "sub", style: "margin:0 0 4px" }, t("planVsBuild")), deltas(plan.changes, METRIC, 0.3)),
      plan.log.length ? h("details", {}, h("summary", {}, t("planLog", plan.log.length)), h("ul", { class: "plan-log" }, plan.log.map(logLine))) : null,
      h("div", { class: "hint" }, t("planNote")))
      : h("p", { class: "muted" }, t("planEmpty")),
    h("div", { class: "row", style: "margin-top:10px" }, optimize, save, reset));
}

// ---------- loot filter ----------
TABS.loot = async (view) => {
  view.replaceChildren(loading(t("lootLoading")));
  const r = await cached(`loot:${state.mode}`, () => api(`/api/lootfilter?mode=${state.mode}&${buildQuery()}`));
  const rows = r.rules.map((x) => h("tr", {},
    h("td", {}, slotName(x.slot)),
    h("td", {}, h("span", { class: "named", title: x.base }, icon(x.base), trName(x.base)),
      x.unique ? h("div", { class: "hint" }, t("lootUnique")) : null),
    h("td", { class: "num" }, x.unique ? "—" : x.item_level),
    h("td", {}, x.unique ? h("span", { class: "muted small" }, t("lootByBase"))
      : x.affixes.length ? h("div", {}, h("ul", { class: "item-lines small" }, x.mods.slice(0, 5).map((m) => h("li", { title: m }, trMod(m)))),
        h("div", { class: "hint" }, t("lootAffixes", x.affixes.length))) : h("span", { class: "muted small" }, t("lootNoMods"))),
    h("td", { class: "small" }, x.leveling.length ? t("lootLevelingCell", x.leveling.length) : h("span", { class: "muted" }, "—"))));
  const what = h("div", { class: "card" }, h("h3", {}, t("lootWhat")), h("div", { class: "sub" }, t("lootWhatSub", t("mode_" + state.mode))),
    h("table", { class: "versus-items" }, h("thead", {}, h("tr", {}, h("th", {}, t("slot")), h("th", {}, t("lootBase")),
      h("th", { class: "num" }, t("lootIlvl")), h("th", {}, t("lootGold")), h("th", {}, t("lootLeveling")))), h("tbody", {}, rows)),
    h("div", { class: "hint", style: "margin-top:8px" }, t("lootLegend")),
    h("div", { class: "hint", style: "margin-top:4px" }, t("lootLevelingLegend")));

  // where the player's filter comes from
  let source = "file";
  // the player's filter: chosen in a Windows dialog opened in the game's filter folder (one filter there: preselected)
  let chosen = r.localFilters.length === 1 ? r.localFilters[0] : "";
  let chosenName = chosen;
  const chosenBox = h("span", { class: "small" });
  const drawChosen = () => chosenBox.replaceChildren(chosen ? h("b", {}, chosenName) : h("span", { class: "muted" }, t("lootNoneChosen")));
  drawChosen();
  const pick = h("button", { class: "ghost", onclick: async () => {
    pick.disabled = true;
    pick.textContent = t("lootPicking");
    try {
      const p = await api("/api/lootfilter/pick", { method: "POST" });
      if (!p.cancelled) { chosen = p.path; chosenName = p.name; drawChosen(); }
    } catch (e) { toast(e.message); }
    pick.disabled = false;
    pick.textContent = t("lootPick");
  } }, t("lootPick"));
  const text = h("textarea", { rows: 6, placeholder: t("lootPastePh"), spellcheck: "false" });
  const name = h("input", { type: "text", placeholder: t("lootNamePh"), style: "width:100%" });
  // the game's copies of online filters (NeverSink, FilterBlade subscriptions), by their names
  const online = (r.onlineFilters || []).length ? h("div", { class: "row small" }, h("span", { class: "muted" }, t("lootOnlineList")),
    r.onlineFilters.map((f) => h("button", { class: "ghost small", title: f.path, onclick: () => { chosen = f.path; chosenName = f.name; drawChosen(); } },
      f.updated ? `${f.name} · ${f.updated}` : f.name))) : null;
  const panes = { file: h("div", { class: "stack", style: "gap:6px" }, h("div", { class: "row" }, pick, chosenBox), online,
    h("div", { class: "hint" }, t("lootPickHint", r.dir))), text, none: h("p", { class: "muted small" }, t("lootOnlyBlock")) };
  const paneBox = h("div", {});
  const seg = h("div", { class: "segmented" }, [["file", t("lootSrcFile")], ["text", t("lootSrcText")], ["none", t("lootSrcNone")]].map(([k, label]) =>
    h("button", { "data-k": k, class: source === k ? "active" : "", onclick: () => { source = k; showPane(); } }, label)));
  const showPane = () => {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.k === source));
    paneBox.replaceChildren(panes[source]);
  };
  showPane();
  const save = h("button", { class: "primary", onclick: async () => {
    if (source === "file" && !chosen) { toast(t("lootPickFirst")); pick.focus(); return; }
    save.disabled = true;
    try {
      const res = await api("/api/lootfilter/save", { method: "POST", body: { mode: state.mode, source,
        file: chosen || null, text: text.value, name: name.value.trim() || null } });
      done.replaceChildren(h("div", { class: "action" }, t("lootSaved", res.name, res.path)));
      toast(t("lootSavedShort", res.name), true);
    } catch (e) { toast(e.message); }
    save.disabled = false;
  } }, t("lootSave"));
  const done = h("div", {});
  const build = h("div", { class: "card stack" }, h("h3", {}, t("lootBuild")), h("div", { class: "sub" }, t("lootBuildSub")),
    seg, paneBox, h("label", { class: "field" }, h("span", {}, t("lootName")), name), h("div", {}, save), done,
    h("div", { class: "hint" }, t("lootOnline")));
  const copy = h("button", { class: "ghost small", onclick: async () => {
    try { await navigator.clipboard.writeText(r.block); toast(t("copied"), true); } catch (e) { toast(e.message); }
  } }, t("copyBlock"));
  const preview = h("div", { class: "card" }, h("details", {}, h("summary", {}, t("lootPreview")),
    h("div", { class: "row", style: "margin:8px 0" }, copy), h("pre", { class: "filter-preview" }, r.block)));
  return h("div", { class: "stack" }, h("div", { class: "sub" }, t("lootIntro")), what, build, preview);
};

// ---------- mechanics ----------
// ---------- skills: each skill with its gems and the links between skills; the gem order while levelling ----------
TABS.skills = async (view) => {
  const mode = state.skillsMode || "build";
  const seg = h("div", { class: "segmented" }, [["build", t("skBuild")], ["leveling", t("skLeveling")], ["uniques", t("skUniquesTab")]].map(([k, label]) =>
    h("button", { class: mode === k ? "active" : "", onclick: () => { state.skillsMode = k; switchTab("skills"); } }, label)));
  const scope = state.uniqueScope || "level";
  const body = h("div", { class: "stack" }, loading(t(mode === "build" ? "skLoading" : mode === "uniques" ? "unLoading" : "skLoadingLevel")));
  view.replaceChildren(h("div", { class: "stack" }, h("div", { class: "row" }, seg), body));
  try {
    const key = mode === "uniques" ? `skills:uniques:${scope}` : `skills:${mode}`;
    const r = await cached(key, () => api(`/api/skills?view=${mode}&scope=${scope}&${buildQuery()}`));
    body.replaceChildren(...(mode === "build" ? renderSkillsBuild(r) : mode === "uniques" ? renderUniqueLinks(r) : renderSkillsLeveling(r)));
  } catch (e) { body.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
};

const gemName = (name) => h("span", { class: "named", title: name }, icon(name), trName(name));
// the game's own description in the player's language (from the installed game), English otherwise
const gameText = (text) => (LANG === "en" ? text : GAME.names[text] || null);
const MECH_NAMES = {};

// The game's own explanations of its terms (its hover popups), in the player's language when unpacked.
let TERMS = {};
const termName = (id) => { const k = TERMS[id]; return k ? (LANG !== "en" && k.nameLocal ? k.nameLocal : k.name) : id; };
// "[Rage|свирепости]" -> a link opening that term when the game explains it, plain text otherwise
function termText(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(/\[([^|\]]+)(?:\|([^\]]+))?\]/g)) {
    out.push(text.slice(last, m.index));
    const shown = m[2] || m[1];
    out.push(TERMS[m[1]] ? h("a", { class: "term-link", href: "#", onclick: (e) => { e.preventDefault(); showTerm(m[1]); } }, shown) : shown);
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}
function showTerm(id) {
  const k = TERMS[id];
  if (!k) return;
  let box = $("#term-pop");
  if (!box) {
    box = h("div", { id: "term-pop", class: "term-pop" });
    document.body.append(box);
  }
  const text = LANG !== "en" && k.textLocal ? k.textLocal : k.text;
  box.replaceChildren(h("div", { class: "row", style: "justify-content:space-between" }, h("b", {}, termName(id)),
    h("button", { class: "bi-act", onclick: () => box.remove() }, "×")),
    h("div", { class: "small" }, termText(text)), h("div", { class: "hint" }, t("termSource")));
}
function termChips(ids) {
  const known = (ids || []).filter((id) => TERMS[id]);
  return known.length ? h("div", { class: "row small", style: "gap:4px" }, h("span", { class: "muted" }, t("termsLabel")),
    known.map((id) => h("button", { class: "chip term", title: t("termOpen"), onclick: () => showTerm(id) }, termName(id)))) : null;
}

// a skill's types as quiet chips coloured by meaning: damage type, kind of skill, how it hits, the rest
const TYPE_GROUP = {
  Physical: "phys", Fire: "fire", Cold: "cold", Lightning: "lightning", Chaos: "chaos",
  Attack: "attack", Spell: "spell", Minion: "minion", CreatesMinion: "minion", Warcry: "warcry",
  Persistent: "buff", Buff: "buff", Aura: "buff", Herald: "buff", AppliesCurse: "curse", Mark: "curse",
  Melee: "delivery", MeleeSingleTarget: "delivery", Strike: "delivery", Slam: "delivery", Projectile: "delivery",
  Area: "delivery", Nova: "delivery", Chains: "delivery", Jumping: "delivery", Barrageable: "delivery",
  Totem: "minion", Trap: "delivery", Shapeshift: "shape", IceCrystal: "cold",
};
function typeChips(tags) {
  return h("div", { class: "row small", style: "gap:4px;margin:2px 0 6px" }, tags.map((x) =>
    h("span", { class: "type-chip t-" + (TYPE_GROUP[x.key] || "other") }, LANG === "en" ? x.key : x.ru)));
}

function mechChips(gem) {
  const out = [];
  for (const k of gem.mechanics.creates) out.push(chip("tag", `${t("skCreates")}: ${MECH_NAMES[k] || k}`));
  for (const k of gem.mechanics.uses) out.push(chip("util", `${t("skUses")}: ${MECH_NAMES[k] || k}`));
  return out.length ? h("div", { class: "row small", style: "gap:4px" }, out) : null;
}

function renderSkillsBuild(r) {
  for (const [k, m] of Object.entries(r.mechanics || {})) MECH_NAMES[k] = m.name;
  TERMS = r.terms || {};
  const ref = (x) => (x.item ? h("span", { class: "named", title: x.gem }, `${trItem(x.gem.split(",")[0])} (${slotName(x.skill)})`)
    : h("span", { class: "named" }, gemName(x.gem), x.support ? h("span", { class: "muted" }, ` → ${trName(x.skill)}`) : null));
  // the game's own explanation of a mechanic when the game data is unpacked, ours otherwise
  const explain = (l) => {
    const official = (l.terms || []).filter((id) => TERMS[id]);
    if (!official.length || LANG === "en" && !TERMS[official[0]].text) return h("div", { class: "hint" }, LANG === "en" ? "" : l.explain);
    return h("div", { class: "hint" }, official.map((id, i) => h("div", {}, i ? h("b", {}, `${termName(id)}: `) : null,
      termText(LANG !== "en" && TERMS[id].textLocal ? TERMS[id].textLocal : TERMS[id].text))));
  };
  const links = h("div", { class: "card" }, h("h3", {}, t("skLinks")), h("div", { class: "sub" }, t("skLinksSub")),
    r.links.length ? r.links.map((l) => h("div", { class: "sk-link" + (l.missing ? " missing" : "") },
      h("div", {}, h("b", {}, l.name), l.missing ? h("span", { class: "chip must", style: "margin-left:8px" }, t("skMissing")) : null),
      explain(l),
      l.creates.length ? h("div", { class: "small" }, h("span", { class: "muted" }, t("skCreatedBy")), " ", l.creates.map((x, i) => [i ? ", " : "", ref(x)])) : null,
      h("div", { class: "small" }, h("span", { class: "muted" }, t("skUsedBy")), " ", l.uses.map((x, i) => [i ? ", " : "", ref(x)]))))
      : h("p", { class: "muted small" }, t("skNoLinks")));
  const gemRow = (gem, g) => {
    const lines = LANG !== "en" && gem.linesLocal && gem.linesLocal.length ? gem.linesLocal : gem.lines.map(trMod);
    const desc = gameText(gem.description);
    if (!gem.support) {
      return h("div", { class: "sk-active" }, h("div", { class: "row" }, h("b", {}, gemName(gem.name)),
        gem.available ? h("span", { class: "muted small" }, t("skFromLevel", gem.available)) : null),
        desc ? h("div", { class: "muted small" }, desc) : null, mechChips(gem), termChips(gem.terms));
    }
    const worth = gem.worth ? deltas(gem.worth, METRIC, 0.5) : null;
    return h("div", { class: "sk-support" + (gem.enabled ? "" : " off") },
      h("div", { class: "row" }, gemName(gem.name), gem.enabled ? null : chip("warn", t("skDisabled")),
        gem.because.length ? h("span", { class: "muted small" }, t("skFits", gem.because.join(", "))) : null),
      lines.length ? h("ul", { class: "item-lines small" }, lines.slice(0, 5).map((l) => h("li", {}, l))) : (desc ? h("div", { class: "small" }, desc) : null),
      worth ? h("div", { class: "small" }, h("span", { class: "muted" }, t(g.measured === "own" ? "skWorthOwn" : "skWorthMain")), " ", worth) : null,
      // raw stat ids ("support_momentum_...") mean nothing to a player; the English view keeps them
      (() => { const shown = gem.unseen.filter((u) => LANG === "en" || !/^[a-z0-9_%+]+$/.test(u));
        return shown.length ? h("div", { class: "hint" }, t("skUnseen"), " ", shown.join("; ")) : null; })(),
      mechChips(gem), termChips(gem.terms));
  };
  const cards = r.groups.filter((g) => g.gems.length).map((g) => h("div", { class: "card sk-group" + (g.enabled ? "" : " off") },
    h("div", { class: "row" }, h("h3", {}, `${g.index}. `, g.actives.map((a, i) => [i ? " + " : "", gemName(a.name)])),
      g.main ? chip("tag", t("skMain")) : null, g.enabled ? null : chip("warn", t("skDisabled")),
      g.slot ? h("span", { class: "muted small" }, slotName(g.slot)) : null),
    g.actives[0] && (g.actives[0].typeTags || []).length ? typeChips(g.actives[0].typeTags) : null,
    g.gems.filter((x) => !x.support).map((x) => gemRow(x, g)),
    g.gems.some((x) => x.support) ? h("div", { class: "sk-supports" }, h("div", { class: "muted small" }, t("skSupports")),
      g.gems.filter((x) => x.support).map((x) => gemRow(x, g))) : null));
  const items = (r.items || []).length ? h("div", { class: "card" }, h("h3", {}, t("skUniques")), h("div", { class: "sub" }, t("skUniquesSub")),
    h("div", { class: "grid two" }, r.items.map((it) => h("div", { class: "sk-item" },
      h("div", { class: "row" }, itemIcon(it.name, it.name.split(",")[1], "unique"), h("b", { title: it.name }, trItem(it.name.split(",")[0])),
        h("span", { class: "muted small" }, slotName(it.slot))),
      h("ul", { class: "item-lines small" }, it.lines.map((l) => h("li", { title: l }, trMod(l)))),
      it.unseen.length ? h("div", { class: "hint" }, t("skUnseen"), " ", it.unseen.map((l, i) => [i ? "; " : "", h("span", { title: l }, trMod(l))])) : null,
      mechChips(it), termChips(it.terms))))) : null;
  return [links, items, h("div", { class: "grid cards" }, cards)].filter(Boolean);
}

// uniques of the whole game that go with the build's skills (mechanics, skill kinds, damage types, shared terms)
const DMG_RU = { cold: "холод", fire: "огонь", lightning: "молния", chaos: "хаос", physical: "физический" };
function renderUniqueLinks(r) {
  TERMS = r.terms || {};
  const mech = (k) => r.mechanics[k] || k;
  const skills = (list) => list.map((n, i) => [i ? ", " : "", gemName(n)]);
  const reason = (x) => {
    if (x.kind === "uses") return [t("unUses", mech(x.mechanic)), " ", skills(x.skills)];
    if (x.kind === "creates") return [t("unCreates", mech(x.mechanic)), " ", skills(x.skills)];
    if (x.kind === "skillKind") return [t("unKind", LANG === "en" ? x.type : x.typeRu), " ", skills(x.skills)];
    if (x.kind === "damage") return t("unDamage", LANG === "en" ? x.type : DMG_RU[x.type]);
    return [t("unTerms"), " ", x.terms.map((id, i) => [i ? ", " : "", termName(id)])];
  };
  const leveling = r.level && r.level < 65;
  const scopeSeg = leveling ? h("div", { class: "segmented small-seg" }, [["level", t("unScopeLevel", r.maxLevel || r.level + 5)], ["all", t("unScopeAll")]].map(([k, label]) =>
    h("button", { class: (state.uniqueScope || "level") === k ? "active" : "", onclick: () => { state.uniqueScope = k; switchTab("skills"); } }, label))) : null;
  const head = h("div", { class: "card" }, h("h3", {}, t("unTitle")), h("div", { class: "sub" }, t("unSub", r.considered)),
    r.outweighed ? h("div", { class: "hint", style: "margin-bottom:8px" }, t("unOutweighed", r.outweighed)) : null, scopeSeg);
  if (!r.suggestions.length) return [head, h("p", { class: "muted" }, t("unNone"))];
  const cards = r.suggestions.map((u) => {
    return h("div", { class: "card sk-item" },
      h("div", { class: "row" }, itemIcon(u.name, u.base, "unique"), h("b", { title: u.name }, trItem(u.name)), h("span", { class: "muted small" }, `${slotName(u.slot)} · ${trName(u.base)}`),
        u.level ? h("span", { class: "muted small" }, t("unLevel", u.level)) : null),
      h("ul", { class: "un-reasons small" }, u.reasons.map((x) => h("li", {}, reason(x)))),
      h("div", { class: "small" }, h("span", { class: "muted" }, t("unWorth", slotName(u.slot))), " ",
        u.outsidePob ? h("span", { class: "chip util" }, t("unPobBlind")) : deltas(u.changes, METRIC, 0.5)),
      h("details", {}, h("summary", { class: "small" }, t("unLines")),
        h("ul", { class: "item-lines small" }, u.lines.map((l) => h("li", { title: l }, trMod(l))))),
      u.unread.length ? h("div", { class: "hint" }, t("skUnseen"), " ", u.unread.map((l, i) => [i ? "; " : "", h("span", { title: l }, trMod(l))])) : null,
      u.source ? h("div", { class: "hint" }, t("unSource"), " ", trFree(u.source)) : null,
      termChips(u.terms));
  });
  return [head, h("div", { class: "grid cards" }, cards), h("div", { class: "hint" }, t("unNote"))];
}

function renderSkillsLeveling(r) {
  for (const p of r.plans) for (const s of p.stages) for (const o of s.options) {
    if (o.color && !GEM_INFO[o.name]) GEM_INFO[o.name] = { color: o.color, support: true };
  }
  const intro = h("div", { class: "card" }, h("h3", {}, t("skLevelTitle")), h("div", { class: "sub" }, t("skLevelSub")),
    h("div", { class: "small" }, t("skUncut",
      Object.entries(r.uncutSkillArea).filter(([lv]) => lv % 2 === 1 && lv <= 13).map(([lv, area]) => `${lv} — ${area}`).join(", "),
      Object.entries(r.uncutSupportArea).map(([tier, lv]) => `${tier} — ${lv}`).join(", "))));
  const timeline = h("div", { class: "card" }, h("h3", {}, t("skTimeline")),
    h("table", { class: "versus-items" }, h("thead", {}, h("tr", {}, h("th", { class: "num" }, t("skLevel")), h("th", {}, t("skSkillsCol")), h("th", {}, t("skSupportsCol")))),
      h("tbody", {}, r.timeline.map((row) => h("tr", {}, h("td", { class: "num" }, `~${row.level}`),
        h("td", {}, row.gems.filter((x) => !x.support).map((x, i) => [i ? ", " : "", gemName(x.name)])),
        h("td", {}, row.gems.filter((x) => x.support).map((x, i) => [i ? ", " : "", h("span", { title: x.skills.map(trName).join(", ") }, gemName(x.name))])))))));
  const plans = r.plans.map((p) => h("div", { class: "card" },
    h("div", { class: "row" }, h("h3", {}, gemName(p.skill)), p.main ? chip("tag", t("skMain")) : null,
      p.skillAvailable ? h("span", { class: "muted small" }, t("skFromLevel", p.skillAvailable)) : h("span", { class: "muted small" }, t("skFromItem"))),
    h("table", { class: "versus-items" }, h("thead", {}, h("tr", {}, h("th", { class: "num" }, t("skLevel")), h("th", {}, t("skFromBuild")), h("th", {}, t("skOptions")))),
      h("tbody", {}, p.stages.map((s) => h("tr", {}, h("td", { class: "num" }, `~${s.level}`),
        h("td", { class: "small" }, s.build.length ? s.build.map((n, i) => [i ? ", " : "", gemName(n)]) : h("span", { class: "muted" }, "—"),
          s.later.length ? h("div", { class: "hint" }, t("skLater", s.later.map(trName).join(", "))) : null),
        h("td", { class: "small" }, s.options.length ? h("ul", { class: "item-lines" }, s.options.map((o) => h("li", {}, gemName(o.name),
          h("span", { class: "delta pos", style: "margin-left:6px" }, `${t("m_dps")} ${pct(o.dps)}`)))) : h("span", { class: "muted" }, "—"))))))));
  return [intro, timeline, h("div", { class: "hint" }, t("skOptionsNote")), ...plans];
}

TABS.mechanics = async (view) => {
  view.replaceChildren(loading(t("collecting")));
  const m = await cached("mechanics", () => api(`/api/mechanics?${buildQuery()}`));
  // "Name, Base (Slot)" / "Skill (группа N)": names through trItem, so a rare's random English name is dropped in
  // Russian (the game builds it from words with several Russian variants — it cannot be recovered exactly)
  const where = (w) => {
    const m = w.match(/^(.*) \(([^()]+)\)$/);
    if (!m) return trFree(w);
    const tail = m[2].replace(/группа (\d+)/, (_, n) => `${t("group")} ${n}`);
    return h("span", { title: w, class: "named" }, icon(m[1]), `${trItem(m[1])} (${SLOT_RU[m[2]] !== undefined ? slotName(m[2]) : trFree(tail)})`);
  };
  // in Russian mode show only what has an official translation; the English original stays in the tooltip
  const line = (text) => h("div", { title: text }, trMod(text));
  // the game's own text in the player's language (from the installed game) beats any translation of ours
  const gapText = (g) => (LANG !== "en" && g.text_local ? h("div", { title: g.text }, g.text_local) : line(g.text));
  const gap = (g) => h("div", { class: "gap" },
    h("button", { class: "gap-add", title: t("addToPob"), onclick: (e) => toggleAddPanel(e.currentTarget.parentElement, g) }, "+"),
    h("div", { class: "where" }, where(g.where)), gapText(g),
    LANG === "en" && g.what !== g.text ? h("div", { class: "stat" }, g.what) : null);
  // raw internal stat ids ("stat_name = 20") mean nothing to a player; the English view keeps them
  const shown = m.gaps.filter((g) => LANG === "en" || g.text_local || !/^[A-Za-z0-9_%+]+ = /.test(g.text));
  const impact = shown.filter((g) => g.likely_impact);
  const rest = shown.filter((g) => !g.likely_impact);
  return h("div", { class: "grid two" },
    h("div", { class: "card" }, h("h3", {}, t("gapsTitle")), h("div", { class: "sub" }, t("gapsSub")),
      impact.map(gap), rest.length ? h("details", {}, h("summary", {}, t("other", rest.length)), rest.map(gap)) : null),
    h("div", { class: "card" }, h("h3", {}, t("skillsTitle")), h("div", { class: "sub" }, t("skillsSub")),
      m.skills.filter((s) => !s.support).map((s) => h("details", {}, h("summary", {}, icon(s.name), `${s.group}. ${trName(s.name)}`),
        s.description && (LANG === "en" || GAME.names[s.description])
          ? h("p", { class: "muted small" }, LANG === "en" ? s.description : GAME.names[s.description]) : null,
        h("ul", {}, LANG !== "en" && s.linesLocal && s.linesLocal.length
          ? s.linesLocal.map((l, i) => h("li", { title: s.lines[i] || "" }, l))
          : s.lines.map((l) => h("li", { title: l }, trMod(l)))))),
      m.uniques.map((u) => h("details", {}, h("summary", {}, trItem(u.name)), h("ul", {}, u.lines.map((l) => h("li", { title: l }, trMod(l))))))));
};

// ---------- profile ----------
TABS.profile = async () => {
  const raw = JSON.parse(JSON.stringify(state.build.profileRaw));
  raw.corrections = raw.corrections || [];
  raw.notes = raw.notes || [];
  // Only ask what this build can answer: a build with no Rage must not show a Rage question.
  const ask = state.build.questions || { rage: true, mana: true };
  const rageMax = h("input", { type: "checkbox", checked: raw.rage === null || raw.rage === undefined });
  const rageVal = h("input", { type: "number", value: raw.rage ?? 0, min: 0, style: "width:90px" });
  const mana = h("input", { type: "checkbox", checked: !!raw.mana_sustained });
  const corrBox = h("div", {});
  const drawCorr = () => corrBox.replaceChildren(...raw.corrections.map((c, i) => h("div", { class: "corr" },
    modEditor(c, drawCorr),
    h("input", { type: "number", value: c.uptime ?? 1, step: 0.05, min: 0, max: 1, oninput: (e) => { c.uptime = Number(e.target.value); } }),
    h("label", { class: "small" }, h("input", { type: "checkbox", checked: !!c.confirmed, onchange: (e) => { c.confirmed = e.target.checked; } }), t("confirmed")),
    h("button", { class: "x", title: t("remove"), onclick: () => { raw.corrections.splice(i, 1); drawCorr(); } }, "×"))));
  drawCorr();
  const notes = h("textarea", { rows: 6 }, raw.notes.join("\n"));
  const save = h("button", { class: "primary", onclick: async () => {
    raw.rage = !ask.rage || rageMax.checked ? null : Number(rageVal.value);
    raw.mana_sustained = ask.mana && mana.checked;
    raw.notes = notes.value.split("\n").map((s) => s.trim()).filter(Boolean);
    raw.main_skill = { group: state.build.info.mainSocketGroup, skill: 1, name: state.build.mainSkill };
    save.disabled = true;
    try {
      state.build = await api("/api/profile", { method: "PUT", body: raw });
      resetCache();
      renderHeader();
      loadBuildList();
      toast(t("saved"), true);
      switchTab("profile");
    } catch (e) { toast(e.message); }
    save.disabled = false;
  } }, t("save"));

  return h("div", { class: "grid two" },
    h("div", { class: "card stack" }, h("h3", {}, `${t("factsTitle")} — ${state.build.name}`),
      h("div", { class: "sub" }, t("factsSub")),
      state.build.hasProfile ? null : h("div", { class: "action" }, t("noProfileYet", state.build.name)),
      ask.rage ? h("div", { class: "row" }, h("label", {}, rageMax, t("rageMax")), h("span", { class: "muted" }, t("otherwise")), rageVal) : null,
      ask.mana ? h("label", {}, mana, t("manaOk")) : null,
      ask.rage || ask.mana ? null : h("div", { class: "muted small" }, t("noQuestions")),
      h("div", { class: "section-title", style: "margin-top:10px" }, t("correctionsTitle")),
      h("div", { class: "corr small muted" }, h("span", {}, t("corrMod")), h("span", {}, t("corrUptime")), h("span", {}), h("span", {})),
      corrBox,
      h("button", { class: "ghost small", onclick: () => { raw.corrections.push({ mod: "", source: "manual", uptime: 1, confirmed: false }); drawCorr(); } }, t("addCorrection")),
      h("div", { class: "section-title" }, t("notes")), notes, h("div", {}, save)),
    h("div", { class: "card" }, h("h3", {}, t("howCounted")),
      state.build.profile.map((l) => h("div", { class: "profile-line" }, trFree(l)))));
};

// "+" on a mechanic PoB ignores: turn it into a correction of the profile. PoB cannot read the game line itself
// (that is why it is listed), so offer the line when it parses after all, the closest mods PoB does read with the
// line's numbers filled in, and a free search.
async function toggleAddPanel(box, g) {
  const open = box.querySelector(".add-panel");
  if (open) { open.remove(); return; }
  const panel = h("div", { class: "add-panel" }, loading(t("searching")));
  box.append(panel);
  const add = async (line) => {
    const raw = JSON.parse(JSON.stringify(state.build.profileRaw));
    raw.corrections = raw.corrections || [];
    raw.notes = raw.notes || [];
    raw.corrections.push({ mod: line, source: `${g.where}: ${g.text}`, uptime: 1, confirmed: false });
    raw.main_skill = { group: state.build.info.mainSocketGroup, skill: 1, name: state.build.mainSkill };
    panel.replaceChildren(loading(t("counting")));
    try {
      state.build = await api("/api/profile", { method: "PUT", body: raw });
      resetCache();
      renderHeader();
      loadBuildList();
      toast(t("corrAdded", trMod(line)), true);
      switchTab("mechanics");
    } catch (e) { toast(e.message); panel.remove(); }
  };
  try {
    const r = await api(`/api/mods/suggest?text=${encodeURIComponent(g.text)}&lang=${LANG}`);
    const pick = (m) => h("div", { class: "suggest-item", title: LANG !== "en" ? m.line : null, onclick: () => add(m.line) }, trMod(m.line));
    panel.replaceChildren(
      r.direct ? h("div", { class: "stack" }, h("div", { class: "sub" }, t("pobReads")),
        h("div", { class: "row" }, h("b", {}, trMod(r.direct)), h("button", { class: "primary small", onclick: () => add(r.direct) }, t("addThis")))) : null,
      r.suggestions.length ? h("div", {}, h("div", { class: "sub" }, r.direct ? t("orSimilar") : t("similarMods")),
        h("div", { class: "pick-list" }, r.suggestions.map(pick))) : null,
      h("div", { class: "sub", style: "margin-top:8px" }, t("orSearch")), modSearch(add),
      h("div", { class: "hint" }, t("addHint")));
  } catch (e) { panel.replaceChildren(h("p", { class: "muted" }, e.message)); }
}

// ---------- mod picker (like the in-game trade filter) ----------
// A chosen mod is shown in the player's language with an input per number; the PoB line is rebuilt from it,
// so the stored text is always one PoB understands.
function modEditor(c, redraw) {
  if (!c.mod) return modSearch((line) => { c.mod = line; redraw(); });
  const tpl = GAME.stats[statKey(c.mod)];
  const shown = tpl || c.mod.replace(TOKEN_RE, "#");
  const tokens = [...c.mod.matchAll(TOKEN_RE)];
  if ((shown.match(/#/g) || []).length !== tokens.length) {
    return h("div", {}, h("input", { type: "text", value: c.mod, style: "width:100%", oninput: (e) => { c.mod = e.target.value; } }));
  }
  const parts = shown.split("#");
  const row = h("div", { class: "mod-edit" });
  parts.forEach((text, k) => {
    row.append(text);
    if (k < tokens.length) {
      const tok = tokens[k][0];
      row.append(h("input", {
        type: "number", class: "mod-num", value: tok.replace(/^\+/, ""), step: "any",
        oninput: (e) => { c.mod = replaceToken(c.mod, k, e.target.value, tok.startsWith("+")); },
      }));
    }
  });
  return h("div", {}, row,
    // the PoB line itself stays in the tooltip: in Russian mode nothing English is shown on the page
    h("div", { class: "hint", title: c.mod }, h("button", { class: "link", onclick: () => { c.mod = ""; redraw(); } }, t("changeMod"))));
}

function replaceToken(line, k, value, plus) {
  let i = 0;
  return line.replace(TOKEN_RE, (m) => {
    if (i++ !== k) return m;
    const v = String(value).trim() || "0";
    return plus && !v.startsWith("-") ? `+${v.replace(/^\+/, "")}` : v;
  });
}

function modSearch(onPick) {
  const input = h("input", { type: "text", placeholder: t("modSearchPh"), style: "width:100%", autocomplete: "off" });
  const list = h("div", { class: "suggest-list hidden" });
  let timer;
  const run = async () => {
    const q = input.value.trim();
    if (q.length < 2) { list.classList.add("hidden"); return; }
    list.replaceChildren(h("div", { class: "suggest-item muted" }, t("modSearching")));
    list.classList.remove("hidden");
    try {
      const r = await api(`/api/mods/search?q=${encodeURIComponent(q)}&lang=${LANG}`);
      list.replaceChildren(...(r.results.length ? r.results.map((m) => h("div", {
        class: "suggest-item", onmousedown: (e) => { e.preventDefault(); onPick(m.line); },
        title: LANG !== "en" ? m.en : null,
      }, h("div", {}, m.text))) : [h("div", { class: "suggest-item muted" }, t("modNothing"))]));
    } catch (e) { list.replaceChildren(h("div", { class: "suggest-item muted" }, e.message)); }
  };
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 200); });
  input.addEventListener("blur", () => setTimeout(() => list.classList.add("hidden"), 150));
  input.addEventListener("focus", () => { if (list.children.length) list.classList.remove("hidden"); });
  return h("div", { class: "suggest" }, input, list);
}

// ---------- craft journal: mods rolled in game -> the hidden mod weights ----------
const HOW_CHIP = { unread: "must", skip: "warn", white: "warn", repeat: "warn", same_mods: "warn", rare_unknown: "warn",
  nothing: "warn" };

// A page of its own (from the sidebar), not a build tab: the journal is about the game, not about one build.
async function renderJournal() {
  hideBuildChrome();
  const view = $("#view");
  try {
    view.replaceChildren(await journalPage(view));
  } catch (e) {
    view.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("error")), h("p", { class: "muted" }, e.message)));
  }
}
$("#journal-open").addEventListener("click", renderJournal);

async function journalPage(view) {
  if (!view.querySelector(".jn-rules")) view.replaceChildren(loading(t("jnLoading")));  // a refresh does not blink
  const j = await api("/api/journal");
  const body = h("div", { class: "stack" });
  if (state.build) {
    body.append(h("div", {}, h("button", { class: "ghost small", onclick: () => { renderHeader(); switchTab(state.tab); } },
      t("jnBack", state.build.name))));
  }
  const recordBtn = h("button", { class: j.recording ? "ghost" : "primary",
    onclick: async () => {
      try { await api("/api/journal/record", { method: "POST", body: { on: !j.recording } }); renderJournal(); }
      catch (e) { toast(e.message); }
    } }, j.recording ? t("jnStop") : t("jnStart"));
  const paste = h("textarea", { rows: 5, placeholder: t("jnPastePh"), style: "width:100%" });
  const addBtn = h("button", { class: "ghost small", onclick: async () => {
    try { await api("/api/journal/add", { method: "POST", body: { text: paste.value } }); renderJournal(); }
    catch (e) { toast(e.message); }
  } }, t("jnAdd"));

  body.append(h("div", { class: "card" }, h("h3", {}, t("jnTitle")), h("div", { class: "sub" }, t("jnSub")),
    h("div", { class: "row", style: "gap:12px;flex-wrap:wrap;margin:6px 0 10px" }, j.available ? recordBtn : h("span", { class: "muted" }, t("jnNoWindows")),
      j.recording ? h("span", { class: "rec-dot" }, t("jnRecording", j.recordedNow)) : h("span", { class: "muted" }, t("jnOff")),
      j.recording && j.hotkey ? chip(j.hotkey === "F2" ? "ok" : "priority", t(j.hotkey === "F2" ? "jnHotkey" : "jnHotkeyBusy")) : null),
    h("ol", { class: "jn-rules" }, [1, 2, 3, 4, 5].map((i) => h("li", {}, t("jnRule" + i)))),
    h("details", {}, h("summary", {}, t("jnPaste")), paste, h("div", { style: "margin-top:6px" }, addBtn))));

  const classes = Object.entries(j.classes || {}).sort((a, b) => b[1].draws - a[1].draws);
  body.append(h("div", { class: "card" }, h("h3", {}, t("jnStatsTitle")),
    h("div", { class: "sub" }, t("jnStats", j.total, j.draws)),
    classes.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("jnClass")), h("th", { class: "num" }, t("jnRecords")), h("th", { class: "num" }, t("jnDraws")))),
      h("tbody", {}, classes.map(([c, x]) => h("tr", {}, h("td", {}, slotName(c)), h("td", { class: "num" }, x.records), h("td", { class: "num" }, x.draws)))))
      : h("p", { class: "muted" }, t("jnNoDraws")),
    h("div", { class: "note small muted", style: "margin-top:8px" }, t("jnHowMany"))));

  // the estimate: how each family's chance moved from the assumption, and applying it to crafting
  const est = j.estimate;
  const estimateBtn = h("button", { class: "primary", onclick: async () => {
    estimateBtn.disabled = true;
    estimateBtn.textContent = t("jnEstimating");
    try { await api("/api/journal/estimate", { method: "POST" }); renderJournal(); }
    catch (e) { toast(e.message); estimateBtn.disabled = false; estimateBtn.textContent = t("jnEstimate"); }
  } }, t("jnEstimate"));
  const applyBtn = est ? h("button", { class: "ghost", onclick: async () => {
    try { await api("/api/journal/apply", { method: j.applied ? "DELETE" : "POST" }); resetCache(); renderJournal(); }
    catch (e) { toast(e.message); }
  } }, j.applied ? t("jnUnapply") : t("jnApply")) : null;
  const seen = est ? est.families.filter((f) => f.seen > 0) : [];
  body.append(h("div", { class: "card" }, h("h3", {}, t("jnWeightsTitle")), h("div", { class: "sub" }, t("jnWeightsSub")),
    h("div", { class: "row", style: "gap:10px;flex-wrap:wrap;margin-bottom:10px" }, estimateBtn, applyBtn,
      j.applied ? chip("ok", t("jnApplied")) : null),
    est ? h("div", {},
      h("p", { class: "small" }, t("jnEstimated", est.draws, new Date(est.time * 1000).toLocaleString(locale())),
        est.kindDraws ? ["weapon", "other"].filter((k) => est.kindDraws[k]).map((k) =>
          " " + t("jnSlope_" + k, est.halfLevel[k] ? fmt(est.halfLevel[k]) : null)).join("") : ""),
      seen.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("colMod")), h("th", { class: "num" }, t("jnSeen")),
        h("th", { class: "num" }, t("jnFactor")), h("th", { class: "num" }, t("jnSpread")))),
        h("tbody", {}, seen.slice(0, 40).map((f) => h("tr", {}, h("td", { class: "mod" }, trMod(f.family)),
          h("td", { class: "num" }, f.seen), h("td", { class: "num" }, `×${fmt(f.factor, 2)}`),
          h("td", { class: "num muted" }, `±${fmt(f.spread * 100)}%`))))) : null) : h("p", { class: "muted" }, t("jnNoEstimate"))));

  // the latest records and how each one counted
  body.append(h("div", { class: "card" }, h("h3", {}, t("jnLatest")),
    h("div", { class: "sub" }, t("jnLatestSub"), " ", h("a", { href: "/api/journal/export" }, t("jnExport"))),
    j.entries.length ? h("div", { class: "jn-list" }, j.entries.map((e) => h("div", { class: "jn-entry" },
      h("div", { class: "row", style: "gap:8px;flex-wrap:wrap;align-items:center" },
        h("span", { class: "muted small" }, new Date(e.t * 1000).toLocaleTimeString(locale())),
        e.base ? h("b", {}, trName(e.base)) : null, e.itemLevel ? h("span", { class: "muted small" }, t("jnIlvl", e.itemLevel)) : null,
        chip(HOW_CHIP[e.how] || "ok", t("jnHow_" + e.how, e.detail)), e.draws ? h("span", { class: "small" }, t("jnDrawsN", e.draws)) : null,
        h("button", { class: "link-btn", title: t("jnDelete"), onclick: async () => {
          try { await api(`/api/journal/entry/${e.id}`, { method: "DELETE" }); renderJournal(); } catch (err) { toast(err.message); }
        } }, "×")),
      e.mods.length ? h("ul", { class: "jn-mods" }, e.mods.map((m) => h("li", {},
        chip("tag", m.side === "Prefix" ? t("prefix") : t("suffix")), " ", h("span", { class: "mod" }, trMod(m.lines.join(" / "))),
        m.tier ? h("span", { class: "tier" }, `${LANG === "ru" ? "тир " : "T"}${m.tier}`) : null,
        m.kind ? h("span", { class: "muted small" }, ` (${m.kind})`) : null))) : null)))
      : h("p", { class: "muted" }, t("jnEmpty"))));

  // while recording, the page follows what comes in - as long as it is the page shown
  clearTimeout(journalPage.timer);
  if (j.recording) {
    journalPage.timer = setTimeout(() => { if (document.querySelector(".jn-rules")) renderJournal(); }, 2500);
  }
  return body;
}

// ---------- assistant ----------
function aiSettingsCard(settings, onSaved) {
  let current = settings.providers.find((p) => p.id === settings.provider) || settings.providers[0];
  const provSel = h("select", {}, settings.providers.map((p) => h("option", { value: p.id }, p.name)));
  provSel.value = current.id;
  const modelInput = h("input", { type: "text", list: "ai-models", placeholder: t("modelPh"), style: "width:100%" });
  const modelList = h("datalist", { id: "ai-models" });
  const urlInput = h("input", { type: "text", placeholder: "https://…/v1", style: "width:100%" });
  const keyInput = h("input", { type: "password", autocomplete: "off", style: "width:100%" });
  const note = h("div", { class: "hint" });
  const urlField = h("label", { class: "field full" }, h("span", {}, t("apiUrl")), urlInput);
  const keyField = h("label", { class: "field full" }, h("span", {}, t("apiKey")), keyInput);
  const modelsInfo = h("span", { class: "hint" });
  const styleSel = h("select", {}, h("option", { value: "short" }, t("styleShort")), h("option", { value: "detailed" }, t("styleDetailed")));
  styleSel.value = settings.style || "short";

  const sync = () => {
    current = settings.providers.find((p) => p.id === provSel.value);
    const same = current.id === settings.provider;
    modelInput.value = same && settings.model ? settings.model : current.defaultModel;
    urlField.classList.toggle("hidden", current.id !== "custom");
    urlInput.value = same && settings.baseUrl ? settings.baseUrl : "";
    keyField.classList.toggle("hidden", !current.needsKey);
    keyInput.value = "";
    keyInput.placeholder = current.keyHint ? t("keySaved", current.keyHint) : t("keyPh");
    note.textContent = current.note || "";
    modelList.replaceChildren();
    modelsInfo.textContent = "";
  };
  provSel.addEventListener("change", sync);
  sync();

  const body = () => ({ provider: provSel.value, model: modelInput.value.trim() || null, base_url: urlInput.value.trim() || null,
    api_key: keyInput.value.trim() || null, style: styleSel.value });
  const save = h("button", { class: "primary", onclick: async () => {
    try { onSaved(await api("/api/llm", { method: "PUT", body: body() })); toast(t("aiSaved"), true); } catch (e) { toast(e.message); }
  } }, t("saveAi"));
  const loadModels = h("button", { class: "ghost", onclick: async () => {
    try {
      await api("/api/llm", { method: "PUT", body: body() });
      const r = await api("/api/llm/models");
      modelList.replaceChildren(...r.models.map((m) => h("option", { value: m })));
      modelsInfo.textContent = t("modelsLoaded", r.models.length);
    } catch (e) { toast(e.message); }
  } }, t("loadModels"));
  const clear = h("button", { class: "ghost", onclick: async () => {
    try { onSaved(await api("/api/llm", { method: "PUT", body: { ...body(), api_key: null, clear_key: true } })); } catch (e) { toast(e.message); }
  } }, t("clearKey"));

  return h("div", { class: "card stack" }, h("h3", {}, t("aiTitle")), h("div", { class: "sub" }, t("aiSub")),
    h("div", { class: "ai-grid" },
      h("label", { class: "field" }, h("span", {}, t("provider")), provSel),
      h("label", { class: "field" }, h("span", {}, t("model")), modelInput, modelList),
      h("div", { class: "full" }, note), urlField, keyField,
      h("label", { class: "field full" }, h("span", {}, t("answerStyle")), styleSel,
        h("span", { class: "hint", style: "text-transform:none;letter-spacing:0" }, t("answerStyleHint"))),
      h("div", { class: "full hint" }, t("modelsHint"), " ", modelsInfo)),
    h("div", { class: "row" }, save, loadModels, current.keyHint ? clear : null),
    h("div", { class: "hint" }, t("keyStorage"), " ", t("dataLeaves")));
}

TABS.assistant = async () => {
  const settings = await api("/api/llm");
  const wrap = h("div", { class: "stack" });
  const redraw = (s) => { wrap.replaceChildren(aiSettingsCard(s, redraw), chatCard(s.active.configured)); loadStatus(); };
  redraw(settings);
  return wrap;
};

function chatCard(configured) {
  if (!configured) return h("div", { class: "card muted" }, t("configureFirst"));
  const log = h("div", { class: "chat-log" });
  const draw = () => {
    log.replaceChildren(...state.chat.map((m) => h("div", { class: "msg " + m.role }, m.text,
      m.tools && m.tools.length ? h("div", { class: "tools" }, t("computed") + m.tools.map((x) => x.tool).join(", ")) : null)));
    log.scrollTop = log.scrollHeight;
  };
  if (!state.chat.length) state.chat.push({ role: "bot", text: t("chatHello") });
  draw();
  const input = h("textarea", { rows: 3, placeholder: t("chatPh") });
  const send = h("button", { class: "primary", onclick: async () => {
    const q = input.value.trim();
    if (!q) return;
    state.chat.push({ role: "user", text: q });
    input.value = "";
    draw();
    send.disabled = true;
    log.append(loading(t("thinking")));
    try {
      const r = await api("/api/chat", { method: "POST", body: { message: q, lang: LANG } });
      state.chat.push({ role: "bot", text: r.answer, tools: r.tools });
      if (r.proposals.length) toast(t("proposal"), true);
    } catch (e) { state.chat.push({ role: "bot", text: `${t("error")}: ${e.message}` }); }
    send.disabled = false;
    draw();
  } }, t("ask"));
  const reset = h("button", { class: "ghost", onclick: async () => { await api("/api/chat/reset", { method: "POST" }); state.chat = []; draw(); } }, t("resetChat"));
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send.click(); });
  return h("div", { class: "card chat" }, log, h("div", { class: "chat-input" }, input, h("div", { class: "stack" }, send, reset)));
}

const ATTR_RU = { Str: "силы", Dex: "ловкости", Int: "интеллекта" };
const attrName = (a) => (LANG === "ru" ? ATTR_RU[a] || a : a);

// ---------- feedback: the player's report with the open build, mailed to the author (poe2lab/feedback.py) ----------
const fbDraft = { message: "", contact: "", images: [] };  // kept while the page is open, so leaving the form loses nothing
const FB_MAX_IMAGE = 2.5 * 1024 * 1024;

function readDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

// a 4K PNG screenshot is too big for mail: large or unusual images become a JPEG at most 2560 px wide
async function screenshotData(file) {
  const url = await readDataUrl(file);
  if (file.size <= FB_MAX_IMAGE && /^image\/(png|jpeg|webp)$/.test(file.type)) return url;
  const img = await new Promise((resolve, reject) => {
    const i = new Image();
    i.onload = () => resolve(i);
    i.onerror = reject;
    i.src = url;
  });
  const scale = Math.min(1, 2560 / img.naturalWidth);
  const c = document.createElement("canvas");
  c.width = Math.round(img.naturalWidth * scale);
  c.height = Math.round(img.naturalHeight * scale);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.85);
}

let fbAddFiles = null;  // set while the form is open; Ctrl+V anywhere on the page goes there
document.addEventListener("paste", (e) => {
  if (!fbAddFiles || !document.querySelector(".fb")) return;
  const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
  if (files.length) { e.preventDefault(); fbAddFiles(files); }
});

async function renderFeedback() {
  const back = state.build ? () => { renderHeader(); switchTab(state.tab); } : renderEmpty;
  hideBuildChrome();
  $("#view").replaceChildren(loading(""));
  let status = { configured: false, maxImages: 3 };
  // a server started before an update serves the new page but has no /api/feedback: it needs a restart
  try { status = await api("/api/feedback"); } catch (_) { status.outdated = true; }

  const message = h("textarea", { class: "fb-text", rows: 7, placeholder: t("fbMessagePh"), maxlength: 5000 });
  message.value = fbDraft.message;
  message.addEventListener("input", () => { fbDraft.message = message.value; });
  const contact = h("input", { type: "text", placeholder: t("fbContactPh"), maxlength: 200, value: fbDraft.contact });
  contact.addEventListener("input", () => { fbDraft.contact = contact.value; });

  const thumbs = h("div", { class: "fb-thumbs" });
  const drawThumbs = () => thumbs.replaceChildren(...fbDraft.images.map((src, i) => h("div", { class: "fb-thumb" },
    h("img", { src, alt: "" }),
    h("button", { class: "bi-act", title: t("fbRemoveShot"), onclick: () => { fbDraft.images.splice(i, 1); drawThumbs(); } }, "×"))));
  fbAddFiles = async (files) => {
    for (const f of files) {
      if (!f.type.startsWith("image/")) continue;
      if (fbDraft.images.length >= status.maxImages) { toast(t("fbTooMany", status.maxImages)); break; }
      try { fbDraft.images.push(await screenshotData(f)); } catch (_) { toast(t("fbBadImage")); }
    }
    drawThumbs();
  };
  const picker = h("input", { type: "file", accept: "image/*", multiple: true, class: "hidden",
    onchange: () => { fbAddFiles([...picker.files]); picker.value = ""; } });
  const drop = h("div", { class: "fb-drop", onclick: () => picker.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); },
    ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); fbAddFiles([...e.dataTransfer.files]); } },
  h("b", {}, t("fbDrop")), h("div", { class: "hint" }, t("fbDropHint", status.maxImages)));

  const blocked = status.outdated ? t("fbRestart") : !state.build ? t("fbNeedBuild") : !status.configured ? t("fbOff") : null;
  const send = h("button", { class: "primary", disabled: Boolean(blocked), onclick: async () => {
    if (fbDraft.message.trim().length < 5) { message.focus(); toast(t("fbEmpty")); return; }
    send.disabled = true;
    send.textContent = t("fbSending");
    try {
      await api("/api/feedback", { method: "POST", body: { message: fbDraft.message, contact: fbDraft.contact,
        images: fbDraft.images, tab: state.tab, mode: state.mode, lang: LANG } });
      fbDraft.message = "";
      fbDraft.images = [];
      fbAddFiles = null;
      toast(t("fbSent"), true);
      back();
    } catch (e) {
      toast(e.message);
      send.disabled = false;
      send.textContent = t("fbSend");
    }
  } }, t("fbSend"));

  $("#view").replaceChildren(h("div", { class: "card stack fb" },
    h("h3", {}, t("fbTitle")), h("div", { class: "sub" }, t("fbSub")),
    blocked ? h("div", { class: "action" }, blocked) : null,
    message, drop, picker, thumbs, contact,
    h("div", { class: "small" }, h("b", {}, t("fbWhat")),
      h("ul", { class: "fb-what" },
        h("li", {}, state.build ? t("fbWhatBuild", state.build.name) : t("fbWhatNoBuild")),
        h("li", {}, t("fbWhatProfile")), h("li", {}, t("fbWhatContext")), h("li", {}, t("fbWhatShots"))),
      h("div", { class: "hint" }, t("fbWhatNot"))),
    h("div", { class: "row" }, send, h("button", { class: "ghost", onclick: () => { fbAddFiles = null; back(); } }, t("cancel")))));
  drawThumbs();
  message.focus();
}

$("#feedback").addEventListener("click", renderFeedback);

// ---------- Russian texts: why names may be English and how to fix it ----------
let GAMEDATA = null;
const bannerKey = "poe2lab.langBanner";

async function loadGameDataStatus() {
  try { GAMEDATA = await api("/api/gamedata"); } catch (_) { GAMEDATA = null; }
  renderLangBanner();
}

function ruReady() { return GAMEDATA && GAMEDATA.unpacked && GAMEDATA.tradeData; }

function renderLangBanner(force = false) {
  const box = $("#lang-banner");
  const indicator = $("#ru-status");
  const st = GAMEDATA;
  indicator.classList.toggle("hidden", LANG !== "ru" || !st);
  if (st) {
    indicator.textContent = ruReady() ? t("ruStatusOk") : t("ruStatusMissing");
    indicator.onclick = () => renderLangBanner(true);
  }
  let dismissed = false;
  try { dismissed = sessionStorage.getItem(bannerKey) === "off"; } catch (_) { /* storage blocked */ }
  if (force) { try { sessionStorage.removeItem(bannerKey); } catch (_) { /* storage blocked */ } dismissed = false; }
  if (LANG !== "ru" || !st || (ruReady() && !force) || dismissed) { box.classList.add("hidden"); return; }

  const reasons = [];
  if (!st.unpacked) {
    if (!st.game) reasons.push(t("ruNoGame"));
    else if (!st.extractor) reasons.push(t("ruNoExtractor", st.game));
    else reasons.push(t("ruNotUnpacked", st.game));
  }
  if (st.error) reasons.push(t("ruError", st.error));
  if (!st.tradeData) reasons.push(t("ruNoTrade"));

  const dir = h("input", { type: "text", value: st.game || "", placeholder: t("ruDirPh"), style: "flex:1;min-width:260px" });
  const run = h("button", { class: "primary", onclick: async () => {
    run.disabled = true;
    run.textContent = t("ruUnpacking");
    try {
      GAMEDATA = await api("/api/gamedata", { method: "POST", body: { game_dir: dir.value.trim() || null } });
      await Promise.all([loadGameTexts(), loadIcons()]);
      toast(t("ruDone"), true);
      renderLangBanner();
      if (state.build) { renderHeader(); resetCache(); switchTab(state.tab); }
    } catch (e) {
      toast(e.message);
      await loadGameDataStatus();
    }
  } }, st.unpacked ? t("ruRebuild") : t("ruUnpack"));
  const close = h("button", { class: "bi-act", title: t("ruHide"), onclick: () => {
    try { sessionStorage.setItem(bannerKey, "off"); } catch (_) { /* storage blocked */ }
    box.classList.add("hidden");
  } }, "×");
  box.replaceChildren(
    h("div", { class: "lb-head" }, h("b", {}, ruReady() ? t("ruTitleOk") : t("ruTitle")), close),
    h("div", { class: "small" }, t("ruWhy")),
    reasons.length ? h("ul", { class: "small" }, reasons.map((r) => h("li", {}, r))) : null,
    h("div", { class: "row", style: "margin-top:8px;flex-wrap:wrap" }, dir, run),
    h("div", { class: "hint" }, t("ruHint")));
  box.classList.remove("hidden");
}

// ---------- start ----------
(async function start() {
  applyStaticTexts();
  renderEmpty();
  await Promise.all([loadGameTexts(), loadIcons()]);
  loadGameDataStatus();
  const s = await loadStatus();
  const wanted = readHash();
  if (wanted && wanted !== s.build) {
    await openBuild(wanted);
  } else if (s.loaded) {
    try { state.build = await api("/api/build"); renderHeader(); switchTab(wanted ? state.tab : "overview"); } catch (_) { /* reopen from the list */ }
  }
  await loadBuildList();
})();
