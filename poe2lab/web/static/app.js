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
    let msg = res.statusText, body = null;
    try { body = await res.json(); msg = body.detail || msg; } catch (_) { /* not json */ }
    // FastAPI's own 404 for an unknown path: the page is newer than the server that serves it
    if ((res.status === 404 && msg === "Not Found") || (res.status === 400 && /^неизвестный (вид|режим)/.test(msg))) msg = t("serverOutdated");
    // an error nothing expected: written to poe2lab's log under this code (see errorCard)
    if (res.status >= 500) msg = t("errInternal", msg);
    const err = new Error(msg);
    err.status = res.status;
    err.errorId = body && body.errorId;
    throw err;
  }
  return res.json();
}

// A question in the page itself: the app's own browser pane answers window.confirm() with "no" at once, so a
// native dialog would silently cancel. Resolves true on the yes button or Enter, false on cancel, Esc or a click
// outside.
function confirmInPage(text, yes) {
  return new Promise((resolve) => {
    const done = (answer) => { back.remove(); document.removeEventListener("keydown", onKey, true); resolve(answer); };
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); done(false); }
      else if (e.key === "Enter") { e.preventDefault(); done(true); }
    };
    const ok = h("button", { class: "primary danger", onclick: () => done(true) }, yes);
    const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) done(false); } },
      h("div", { class: "ask card stack", role: "dialog", "aria-modal": "true" },
        h("div", {}, text),
        h("div", { class: "row" }, ok, h("button", { class: "ghost", onclick: () => done(false) }, t("cancel")))));
    document.body.append(back);
    document.addEventListener("keydown", onKey, true);
    ok.focus();
  });
}

// a card beside an element while the pointer is over it: an item's mods, a rune's lines
let TIP = null;
function hideTip() { if (TIP) TIP.style.display = "none"; }
function hoverTip(el, render) {
  el.addEventListener("mouseenter", () => {
    const body = render();
    if (!body) return;
    if (!TIP) { TIP = h("div", { class: "hover-tip card" }); document.body.append(TIP); }
    TIP.replaceChildren(body);
    TIP.style.display = "block";
    const r = el.getBoundingClientRect(), w = TIP.offsetWidth, ht = TIP.offsetHeight;
    const x = r.right + 10 + w <= innerWidth - 8 ? r.right + 10 : Math.max(8, r.left - w - 10);
    TIP.style.left = `${x}px`;
    TIP.style.top = `${Math.min(Math.max(8, r.top), Math.max(8, innerHeight - ht - 8))}px`;
  });
  el.addEventListener("mouseleave", hideTip);
  el.addEventListener("click", hideTip);
  return el;
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
// an interface icon of the sprite in index.html (one colour: it takes the text's)
function I(id, cls = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ic" + (cls ? " " + cls : ""));
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + id);
  svg.append(use);
  return svg;
}

const DMG_COLOR = { Physical: "var(--phys)", Fire: "var(--fire)", Cold: "var(--cold)", Lightning: "var(--lightning)", Chaos: "var(--chaos)" };
const METRIC = [["dps", "m_dps"], ["ehp", "m_ehp"], ["phys_hit", "m_phys"], ["fire_hit", "m_fire"], ["cold_hit", "m_cold"],
  ["lightning_hit", "m_lightning"], ["chaos_hit", "m_chaos"], ["recovery", "m_recovery"]];

function deltas(changes, keys = METRIC, min = 0.3) {
  const items = keys.filter(([k]) => Math.abs(changes[k] || 0) >= min)
    .map(([k, label]) => h("span", { class: "delta " + (changes[k] > 0 ? "pos" : "neg"), title: t("mh_" + k) }, `${t(label)} ${pct(changes[k])}`));
  return h("div", { class: "deltas" }, items.length ? items : h("span", { class: "muted small" }, t("noEffect")));
}

function scoreBar(score, max) {
  const w = Math.max(3, Math.min(100, (score / (max || 1)) * 100));
  return h("div", { class: "score" }, h("div", { class: "bar" }, h("span", { style: `width:${w}%` })), fmt(score, 1));
}

const chip = (cls, text) => h("span", { class: "chip " + cls }, text);

// ---------- state ----------
const state = { build: null, mode: "balanced", tab: "overview", cache: {}, chat: [] };
const resetCache = () => { state.cache = {}; schedulePreload(); };
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
    // a "?" mark's hover tooltip is easy to miss: a click shows it too (a button's click is its own action)
    if (el.tagName !== "BUTTON") el.onclick = () => toast(el.title, true);
  });
  document.querySelectorAll("#lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === LANG));
  document.querySelectorAll("#tabs button[data-tab]").forEach((b) => { b.title = t("tabHint_" + b.dataset.tab); });
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
  loadLeagues();
  loadBuildList();
  if (state.build) { renderHeader(); switchTab(state.tab); } else renderEmpty();
});

const TAB_ORDER = ["overview", "skills", "gear", "tree", "loot", "profile", "assistant"];
// tabs that were folded into others: an old address still lands where their content is now
const MOVED_TABS = { compare: "gear", mechanics: "profile", damage: "skills" };

// the league for prices and trade searches: the player's choice, or poe.ninja's current league
async function loadLeagues() {
  const sel = $("#league");
  let r;
  try { r = await api("/api/leagues"); } catch (_) { return; }
  sel.replaceChildren(h("option", { value: "" }, r.chosen || !r.current ? t("leagueAuto") : t("leagueAutoNow", trName(r.current))),
    ...r.leagues.map((l) => h("option", { value: l }, trName(l))));
  sel.value = r.chosen || "";
  sel.onchange = async () => {
    try {
      const res = await api("/api/leagues", { method: "PUT", body: { league: sel.value || null } });
      toast(t("leagueChosen", trName(res.current || res.chosen || "")), true);
      resetCache();
      if (state.build) switchTab(state.tab);
      loadLeagues();
    } catch (e) { toast(e.message); }
  };
}

function renderEmpty() {
  $("#view").replaceChildren(h("div", { class: "welcome" },
    h("h2", {}, t("welcomeTitle")), h("p", { class: "muted" }, t("welcomeSub")),
    h("ol", { class: "welcome-steps" }, [1, 2, 3].map((n) => h("li", {}, t("welcomeStep" + n)))),
    h("div", { class: "card" }, h("h3", {}, t("welcomeWhere")),
      h("dl", { class: "welcome-tabs" }, TAB_ORDER.flatMap((tab) => [h("dt", {}, t("tab_" + tab)), h("dd", {}, t("tabHint_" + tab))]))),
    h("p", { class: "muted small" }, t("welcomeGlossary"), " ",
      h("button", { class: "link small", onclick: () => $("#glossary-open").click() }, t("glOpen")))));
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
        class: "bitem" + (state.build && state.build.name === b.name ? " is-on" : "") + (b.favorite ? " is-fav" : ""),
        role: "button", tabindex: "0", title: b.name, onclick: () => openBuild(b.name),
        onkeydown: (e) => { if (e.key === "Enter") openBuild(b.name); },
      },
      h("span", { class: "bitem-n" }, b.name),
      h("span", { class: "bitem-m" },
        b.kind === "pob" ? h("span", { title: t("savedInPob") }, t("savedInPob"))
          : h("span", { title: t("pobCode") }, I("scroll"), "PoB"),
        b.hasProfile ? h("span", { title: t("withProfile") }, I("id")) : null,
        b.hasMain ? h("span", { class: "is-me", title: t("chInList") }, I("person"), t("mainShort")) : null),
      h("span", { class: "bitem-x" },
        h("button", { class: "icon-btn sm star", title: b.favorite ? t("favOff") : t("favOn"),
          onclick: (e) => { e.stopPropagation(); toggleFavorite(b); } }, I(b.favorite ? "star" : "star-o", "ic-s")),
        h("button", { class: "icon-btn sm", title: t("removeBuild"),
          onclick: (e) => { e.stopPropagation(); removeBuild(b); } }, I("x", "ic-s")))));
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
  if (!await confirmInPage(b.kind === "pob" ? t("confirmHide", b.name) : t("confirmTrash", b.name),
    b.kind === "pob" ? t("hideGo") : t("removeGo"))) return;
  try {
    const r = await api(`/api/builds/${encodeURIComponent(b.name)}`, { method: "DELETE" });
    toast(r.result === "hidden" ? t("hiddenOne", b.name) : t("trashed", b.name), true);
    if (state.build && state.build.name === b.name) {
      switchTab.token = Symbol();  // a late answer for the removed build must not render
      state.build = null;
      state.chat = [];
      resetCache();
      $("#build-header").classList.add("hidden");
      $("#bh-controls").classList.add("hidden");
      $("#tabs").classList.add("hidden");
      renderEmpty();
    }
    loadBuildList();
  } catch (e) { toast(e.message); }
}

function renderAddBuild() {
  const name = h("input", { type: "text", placeholder: t("addName") });
  const code = h("textarea", { rows: 8, placeholder: t("addCode"), spellcheck: "false" });
  // a maxroll.gg guide or planner link: its stages ("Early", "Endgame"...) to pick one
  const stage = h("div", { class: "row small" });
  let variant = null, asked = "";
  const MAXROLL = /maxroll\.gg\/poe2\/(planner|build-guides)\//i;
  code.addEventListener("input", async () => {
    const link = code.value.trim();
    if (!MAXROLL.test(link)) { stage.replaceChildren(); variant = null; asked = ""; return; }
    if (link === asked) return;
    asked = link;
    stage.replaceChildren(h("span", { class: "muted" }, t("addMaxrollLoading")));
    try {
      const m = await api(`/api/maxroll?link=${encodeURIComponent(link)}`);
      if (asked !== link) return;
      variant = m.default;
      if (!name.value.trim()) name.placeholder = m.name;
      stage.replaceChildren(h("label", {}, t("addMaxrollStage"), " ",
        h("select", { onchange: (e) => { variant = Number(e.target.value); } },
          m.profiles.map((p, i) => h("option", { value: i, selected: i === m.default }, p)))),
        h("span", { class: "muted" }, t("addMaxrollHint")));
    } catch (e) {
      if (asked === link) stage.replaceChildren(h("span", { class: "bad" }, e.message));
    }
  });
  const go = h("button", { class: "primary", onclick: async () => {
    if (!code.value.trim()) { code.focus(); return; }
    go.disabled = true;
    go.textContent = t("adding");
    try {
      const r = await api("/api/builds", { method: "POST", body: { name: name.value, code: code.value, variant } });
      toast(t("added", r.name), true);
      await openBuild(r.name);
      if (r.report) plannerReport(r.report);
    } catch (e) {
      toast(e.message);
      go.disabled = false;
      go.textContent = t("addGo");
    }
  } }, t("addGo"));
  // the game's build planner file (.build: Mobalytics, PoB's export) read from disk into the box
  const file = h("input", { type: "file", accept: ".build,.json,.txt", style: "display:none", onchange: async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    code.value = await f.text();
    if (!name.value.trim()) name.placeholder = f.name.replace(/\.[^.]+$/, "");
  } });
  hideBuildChrome();
  const fromGame = h("div", { class: "planner-files" });
  api("/api/planner").then((p) => {
    if (!p.files.length) return;
    fromGame.replaceChildren(h("span", { class: "muted", title: p.dir }, t("addFromPlanner")),
      ...p.files.map((f) => h("button", { class: "ghost small", title: `${p.dir}\\${f.file}`,
        onclick: (e) => importFromPlanner(f.file, e.currentTarget) }, f.name)));
  }).catch(() => { /* no planner folder: nothing to offer */ });
  $("#view").replaceChildren(h("div", { class: "card stack add-build" },
    h("h3", {}, t("addTitle")), h("div", { class: "sub" }, t("addSub")),
    name, code, stage,
    h("div", { class: "row small" }, h("button", { class: "ghost small", onclick: () => file.click() }, t("addFile")),
      h("span", { class: "muted" }, t("addFileHint")), file),
    fromGame,
    h("div", { class: "row" }, go, state.build
      ? h("button", { class: "ghost", onclick: () => { renderHeader(); switchTab(state.tab); } }, t("cancel")) : null)));
  code.focus();
}

$("#add-build").addEventListener("click", renderAddBuild);

// ---------- the build constructor: a build from nothing (PLAN.md, "Конструктор билда с нуля") ----------
const ATTR_COLOR = { str: "#c8463a", dex: "#4fae5a", int: "#5467d8" };
const nbState = { asc: null, ascName: "", stage: "endgame", level: 92, name: "" };
const nbLadder = { shares: null, error: "", tops: {} };  // poe.ninja's ladder: kept while the page is open

async function renderNewBuild() {
  hideBuildChrome();
  $("#view").replaceChildren(loading(t("nbLoading")));
  let data;
  try { data = await api("/api/new/classes"); } catch (e) { $("#view").replaceChildren(h("p", { class: "muted" }, e.message)); return; }
  const box = h("div", { class: "card stack nb" });
  // poe.ninja's ladder: the ascendancies' shares come in the background; a pick shows its top characters
  if (!nbLadder.shares && !nbLadder.error) {
    api("/api/ladder/ascendancies").then((l) => { nbLadder.shares = l; draw(); })
      .catch((e) => { nbLadder.error = e.message; draw(); });
  }
  const ladderBox = h("div", { class: "stack" });
  const drawTop = async () => {
    const asc = nbState.ascName;
    if (!asc) { ladderBox.replaceChildren(); return; }
    if (!nbLadder.tops[asc]) {
      ladderBox.replaceChildren(loading(t("nbLadderLoading")));
      try { nbLadder.tops[asc] = await api(`/api/ladder/top?ascendancy=${encodeURIComponent(asc)}`); } catch (e) {
        ladderBox.replaceChildren(h("p", { class: "muted small" }, t("nbLadderFail", e.message)));
        return;
      }
      if (nbState.ascName !== asc) return;
    }
    const top = nbLadder.tops[asc];
    const take = (c) => async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.textContent = t("nbTaking");
      try {
        const b = await api("/api/ladder/take", { method: "POST", body: { account: c.account, name: c.name, skill: c.skill } });
        state.build = b;
        state.chat = [];
        state.changes = null;
        resetCache();
        renderHeader();
        loadBuildList();
        switchTab("overview");
        toast(t("nbTaken", b.name), true);
      } catch (err) { toast(err.message); btn.disabled = false; btn.textContent = t("nbTake"); }
    };
    ladderBox.replaceChildren(h("h3", {}, t("nbLadderTitle", trName(asc))),
      h("div", { class: "sub" }, t("nbLadderSub", top.league, fmt(top.total))),
      top.characters.length ? h("div", { class: "nb-ladder" }, top.characters.map((c) => h("div", { class: "nb-lrow" },
        h("span", { class: "nb-llevel" }, c.level),
        h("span", { class: "named" }, icon(c.skill), h("b", {}, trName(c.skill))),
        h("span", { class: "muted small", title: c.account }, c.name),
        h("span", { class: "small" }, "DPS ", h("b", {}, c.dps)),
        h("span", { class: "small" }, "EHP ", h("b", {}, c.ehp)),
        h("a", { class: "np-link", href: c.url, target: "_blank", rel: "noopener noreferrer", title: t("nbOpenNinjaHint") }, t("nbOpenNinja")),
        h("button", { class: "ghost small", title: t("nbTakeHint"), onclick: take(c) }, t("nbTake")))))
        : h("p", { class: "muted small" }, t("nbLadderEmpty")));
  };
  const levelOf = () => (nbState.stage === "custom" ? nbState.level : data.stages[nbState.stage]);
  const attr = (k, v) => h("span", { class: "nb-attr", title: t("nbAttr_" + k) },
    h("span", { class: "nb-attr-bar", style: `width:${v * 4}px;background:${ATTR_COLOR[k]}` }), t("nbAttrShort_" + k));
  const draw = () => {
    const shares = nbLadder.shares ? nbLadder.shares.shares : null;
    const share = (a) => (shares && shares[a.name] ? shares[a.name].share : 0);
    const classes = h("div", { class: "nb-classes" }, data.classes.map((c) => {
      const best = shares ? c.ascendancies.reduce((m, a) => (share(a) > share(m) ? a : m), c.ascendancies[0]) : null;
      return h("div", { class: "nb-class" + (c.ascendancies.some((a) => a.id === nbState.asc) ? " sel" : "") },
        h("div", { class: "nb-cname" }, trName(c.name)),
        h("div", { class: "nb-attrs" }, attr("str", c.str), attr("dex", c.dex), attr("int", c.int)),
        h("div", { class: "nb-ascs" }, c.ascendancies.map((a) => h("button", { class: "nb-asc" + (nbState.asc === a.id ? " sel" : ""),
          onclick: () => { nbState.asc = a.id; nbState.ascName = a.name; draw(); drawTop(); } },
        h("span", {}, trName(a.name), best === a && share(a) > 0 ? h("span", { class: "nb-best", title: t("nbLadderBest") }, " ★") : null),
        shares ? h("span", { class: "nb-share", title: t("nbShareHint", fmt((shares[a.name] || {}).count || 0), nbLadder.shares.league) },
          h("span", { class: "nb-share-bar", style: `width:${Math.max(2, Math.round(share(a) * 100 * 1.4))}px` }),
          `${fmt(share(a) * 100, 1)}%`) : null))));
    }));
    const custom = h("input", { type: "number", min: 1, max: 100, value: nbState.level, style: "width:64px",
      oninput: () => { nbState.stage = "custom"; nbState.level = Math.max(1, Math.min(100, Number(custom.value) || 1)); drawName(); drawStages(); } });
    const stages = h("div", { class: "segmented" });
    const drawStages = () => stages.replaceChildren(...Object.entries(data.stages).map(([k, lv]) => h("button", {
      class: nbState.stage === k ? "active" : "", onclick: () => { nbState.stage = k; nbState.level = lv; custom.value = lv; draw(); } },
    t("nbStage_" + k), h("span", { class: "muted small" }, ` · ${lv}`))));
    drawStages();
    const name = h("input", { type: "text", value: nbState.name, oninput: () => { nbState.name = name.value; } });
    const drawName = () => { name.placeholder = nbState.asc ? `${trName(nbState.ascName)} ${levelOf()}` : t("nbNamePh"); };
    drawName();
    const go = h("button", { class: "primary big-btn", disabled: !nbState.asc, onclick: async () => {
      go.disabled = true;
      go.textContent = t("nbMaking");
      try {
        const b = await api("/api/builds/new", { method: "POST", body: { ascendancy: nbState.asc, stage: nbState.stage,
          level: nbState.stage === "custom" ? nbState.level : null, name: nbState.name.trim() || name.placeholder } });
        Object.assign(nbState, { asc: null, ascName: "", name: "" });
        state.build = b;
        state.chat = [];
        state.changes = null;
        resetCache();
        renderHeader();
        loadBuildList();
        switchTab("skills");
        toast(t("nbDone", b.name), true);
      } catch (e) { toast(e.message); go.disabled = false; go.textContent = t("nbGo"); }
    } }, t("nbGo"));
    box.replaceChildren(h("h2", {}, t("nbTitle")), h("div", { class: "sub" }, t("nbSub")),
      h("h3", {}, t("nbStep1")),
      nbLadder.shares ? h("div", { class: "muted small" }, t("nbLadderShares", nbLadder.shares.league, fmt(nbLadder.shares.total)))
        : nbLadder.error ? h("div", { class: "muted small" }, t("nbLadderFail", nbLadder.error)) : null,
      classes, ladderBox,
      h("h3", {}, t("nbStep2")), h("div", { class: "row" }, stages, h("label", { class: "muted small" }, t("nbOwnLevel"), " ", custom)),
      h("h3", {}, t("nbStep3")), name,
      h("div", { class: "row" }, go, state.build ? h("button", { class: "ghost", onclick: () => { renderHeader(); switchTab(state.tab); } }, t("cancel")) : null));
  };
  draw();
  drawTop();
  $("#view").replaceChildren(box);
}
$("#new-build").addEventListener("click", renderNewBuild);
$("#author-btn").addEventListener("click", () => authorToggle());

// the constructor's steps above the tabs of a build it made: what is done, what comes next
const CTOR_STEPS = [["class", null], ["skill", "skills"], ["gear", "gear"], ["tree", "tree"], ["mech", "profile"], ["polish", "overview"], ["save", null]];
// the constructor's record of a build it made - the profile's own key only (every object has a `.constructor`)
const ctorOf = (b) => {
  const raw = b && b.profileRaw;
  return raw && Object.prototype.hasOwnProperty.call(raw, "constructor") ? raw.constructor : null;
};
function renderCtorBar() {
  const bar = $("#ctor-bar");
  const b = state.build;
  if (!ctorOf(b)) { bar.classList.add("hidden"); return; }
  const done = { class: true, skill: !!b.mainSkill, gear: (b.items || []).length >= 8 };
  const next = CTOR_STEPS.find(([k]) => !done[k]);
  bar.replaceChildren(h("span", { class: "ctor-title" }, t("ctorTitle")), ...CTOR_STEPS.map(([k, tab], i) => h("button", {
    class: "ctor-step" + (done[k] ? " done" : "") + (next && next[0] === k ? " next" : "") + (tab && state.tab === tab ? " here" : ""),
    title: t("ctorHint_" + k),
    onclick: () => { if (k === "save") saveMenu(); else if (tab) switchTab(tab); } },
  h("span", { class: "ctor-num" }, done[k] ? "✓" : i + 1), t("ctorStep_" + k))));
  bar.classList.remove("hidden");
}

// saving a build: into itself (the plan's edits), the game's planner, a PoB code for pobb.in and PoB
async function copyBuildCode() {
  try {
    const r = await api(`/api/builds/code?${buildQuery()}`);
    toast(t((await copyText(r.code)) ? "svCodeCopied" : "npCopyFail"), true);
  } catch (e) { toast(e.message); }
}
async function saveMenu() {
  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) back.remove(); } });
  const code = copyBuildCode;
  const row = (label, hint, onclick, cls = "ghost") => h("div", { class: "sv-row" }, h("button", { class: cls, onclick }, label), h("span", { class: "muted small" }, hint));
  back.append(h("div", { class: "ask card stack" }, h("h3", {}, t("svTitle")),
    row(t("svCommit"), t("svCommitHint"), async () => { back.remove(); await commitBuild(); }, "primary"),
    row(t("svCode"), t("svCodeHint"), code),
    row(t("toPlanner"), t("svPlannerHint"), () => { back.remove(); exportToPlanner(); }),
    h("div", { class: "row" }, h("a", { class: "np-link", href: "https://pobb.in", target: "_blank", rel: "noopener noreferrer" }, "pobb.in"),
      h("button", { class: "ghost", onclick: () => back.remove() }, t("cancel")))));
  document.body.append(back);
}

async function commitBuild() {
  const view = $("#view");
  view.replaceChildren(loading(t("svSaving")));
  try {
    state.build = await api("/api/builds/commit", { method: "POST", body: {} });
    resetCache();
    renderHeader();
    toast(t("svSaved", state.build.name), true);
  } catch (e) { toast(e.message); }
  switchTab(state.tab);
}


// what a build planner file became: level, what could not be matched, attributes still short
// what the file does not hold and the import assumed, as played: attributes, quality, gem levels, the states the
// build causes itself (charges, a blinded enemy, crit recently) with what each changed
function assumedBlock(a) {
  if (!a) return null;
  const rows = [
    a.attributeNodes ? t("prAssAttributes", a.attributeNodes) : null,
    a.itemQuality ? t("prAssQuality", a.itemQuality) : null,
    a.gemLevels ? t("prAssGemLevels", a.gemLevels, a.gemsLowered, a.gemQuality) : null,
    ...(a.states || []).map((s) => t("prAssState", t("prState_" + s.kind, s.value) + (s.uptime ? ` (${t("prHeld", Math.round(s.uptime * 100))})` : ""),
      s.from.map(trName).join(", "), pct(s.dps), Math.abs(s.ehp) >= 0.5 ? pct(s.ehp) : "")),
  ].filter(Boolean);
  return rows.length ? h("div", { class: "pr-assumed small" }, h("b", {}, t("prAssTitle")),
    h("ul", { class: "pr-list" }, rows.map((x) => h("li", {}, x))), h("div", { class: "hint" }, t("prAssRest"))) : null;
}

function plannerReport(r) {
  const short = Object.entries(r.attributes.short || {}).filter(([, v]) => v > 0);
  const p = r.passives || {};
  const skills = r.skills || [], items = r.items || [];
  const from = (x) => (x.from ? chip("tag", t("prFrom", x.from)) : null);
  const kinds = {};
  items.forEach((i) => { kinds[i.kind] = (kinds[i.kind] || 0) + 1; });
  const passiveLine = [t("prAscendancy", p.ascendancy || 0),
    ...Object.entries(p.weaponSets || {}).map(([ws, n]) => t("prWeaponSet", ws, n)),
    t("prAttributes", p.attributes || 0, p.attributesChosen || 0),
    p.jewelSockets ? t("prJewels", (p.jewels || []).length, p.jewelSockets) : null,
    p.notes ? t("prNotes", p.notes) : null, p.levels ? t("prLevels", p.levels) : null].filter(Boolean).join(" · ");
  const skillRow = (s) => h("li", {}, gemName(s.name), s.level ? h("span", { class: "muted small" }, " " + t("prGemLevel", s.level, s.quality)) : null,
    " ", from(s), s.note ? h("div", { class: "small muted" }, s.note) : null,
    s.supports.length ? h("div", { class: "small" }, s.supports.map((x, i) => [i ? ", " : "", trName(x.name),
      x.from > 1 ? h("span", { class: "muted" }, ` (${t("prFrom", x.from)})`) : null])) : null);
  const itemRow = (i) => h("li", { class: i.kind === "missing" ? "bad" : "" }, h("b", {}, slotName(i.slot)), ": ",
    trItem(i.name), " ", chip(i.kind === "missing" ? "must" : "tag", t("prKind_" + i.kind)), " ", from(i));
  const card = h("div", { class: "card planner-report" }, h("h3", {}, t("plannerTitle", r.name)),
    h("div", { class: "sub" }, t("plannerSub", r.author || "—", r.level)),
    r.link ? h("div", { class: "small" }, h("a", { href: r.link, target: "_blank", rel: "noopener" }, r.link)) : null,
    r.description ? h("p", { class: "small pr-description" }, r.description) : null,
    r.passives ? h("div", { class: "pr-grid" },
      h("div", {}, h("b", {}, t("prPassives", p.total)), h("div", { class: "small muted" }, passiveLine)),
      h("div", {}, h("b", {}, t("prSkills", skills.length, skills.reduce((n, s) => n + s.supports.length, 0))),
        h("div", { class: "small muted" }, t("prSkillLevels", skills.filter((s) => s.from).length, skills.filter((s) => s.level).length))),
      h("div", {}, h("b", {}, t("prItems", items.length)),
        h("div", { class: "small muted" }, Object.entries(kinds).map(([k, n]) => `${t("prKind_" + k)}: ${n}`).join(" · ")))) : null,
    skills.length ? h("details", {}, h("summary", {}, t("prSkillsList")), h("ul", { class: "pr-list" }, skills.map(skillRow))) : null,
    items.length ? h("details", {}, h("summary", {}, t("prItemsList")), h("ul", { class: "pr-list" }, items.map(itemRow))) : null,
    assumedBlock(r.assumed),
    (r.unknown || []).length ? h("p", { class: "small warn" }, t("prUnknown", r.unknown.join(", "))) : null,
    r.passives && (skills.some((s) => s.from) || items.some((i) => i.from)) ? h("p", { class: "small" }, t("prPlanKept")) : null,
    r.missing.length ? h("p", { class: "bad small" }, t("plannerMissing", r.missing.join(", "))) : null,
    short.length ? h("p", { class: "small" }, t("plannerShort", short.map(([a, v]) => `${t("attr_" + a)} −${v}`).join(", "))) : null,
    h("p", { class: "hint" }, t("plannerHint")),
    h("button", { class: "ghost small", onclick: () => card.remove() }, t("plannerOk")));
  $("#view").prepend(card);
}

async function loadStatus() {
  const s = await api("/api/status");
  $("#llm-status").textContent = s.llm.configured ? t("aiOn", s.llm.model) : t("aiOff");
  // the code on disk is newer than the running server (an update): the page is the new one, the server is not
  const outdated = !("version" in s) || (s.current && s.version !== s.current);
  $("#outdated-banner")?.remove();
  if (outdated) document.body.prepend(h("div", { id: "outdated-banner", class: "outdated-banner" }, "⟳ ", t("serverRestart")));
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
    const build = state.build;
    await preload(true);  // every tab worked out first (or the player opens it at once)
    if (state.build === build) switchTab(state.tab);
  } catch (e) {
    $("#view").replaceChildren(h("div", { class: "empty" }, h("h2", {}, t("openFailed")), h("p", { class: "muted" }, e.message)));
  }
}

// class / ascendancy · level, as the header says it
const who = (x) => `${trName(x.class)} / ${x.ascendancy ? trName(x.ascendancy) : t("noAscendancy")} · ${t("level", x.level)}`;

function renderHeader() {
  const b = state.build;
  GEM_INFO = { ...(b.gemColors || {}) };
  GEM_TIPS.clear();  // a gem's lines are at this build's level and quality
  loadAllGems();
  setBuildNames(b);
  $("#build-header").classList.remove("hidden");
  $("#bh-controls").classList.remove("hidden");
  $("#tabs").classList.remove("hidden");
  $("#bh-name").textContent = b.name;
  document.title = `${b.name} · poe2lab`;
  $("#bh-menu").title = t("bhMenu");
  $("#bh-menu").setAttribute("aria-label", t("bhMenu"));
  renderChanges();
  renderCtorBar();
  const way = b.main && b.guide.level ? Math.max(0, Math.min(100, (b.info.level / b.guide.level) * 100)) : 0;
  $("#bh-sub").replaceChildren(...(b.main
    ? [h("span", { class: "who-item", title: t("chMineHint") }, h("span", { class: "av me" }, I("person")), t("chMine"), " ", h("b", {}, who(b.info))),
      h("span", { class: "who-path", title: t("whoPath", b.info.level, b.guide.level) }, h("span", { class: "track", style: `--v:${way}%` }, h("i"))),
      h("span", { class: "who-item", title: t("chGuideHint") }, h("span", { class: "av guide" }, I("scroll")), t("chGuide"), " ", who(b.guide))]
    : [h("span", { class: "who-item" }, h("b", {}, who(b.info)))]));
  // a picker with skill icons (a <select> cannot show images)
  const picker = $("#main-skill");
  const entries = b.groups.flatMap((g) => g.skills.map((s, i) => ({ group: g.index, skill: i + 1, name: s })));
  const current = entries.find((e) => b.info.mainSocketGroup === e.group && b.mainSkill === e.name) || entries[0];
  const label = (e) => [icon(e.name), h("span", {}, `${e.group}. ${trName(e.name)}`)];
  const list = h("div", { class: "picker-list hidden" }, entries.map((e) => h("div", {
    class: "picker-item" + (e === current ? " active" : ""),
    onclick: () => { list.classList.add("hidden"); if (e !== current) openBuild(b.name, e.group, e.skill); },
  }, label(e))));
  const button = h("button", { class: "picker-button select", onclick: (ev) => { ev.stopPropagation(); list.classList.toggle("hidden"); } },
    current ? label(current) : null, I("chev"));
  picker.replaceChildren(button, list);
}

// ---------- the character and the build brought up to date: one dialog, a PoB code pasted at once ----------
// With the player's character in the build the code updates it; without one it is either the player's character
// (the build becomes the guide) or the build's own newer code. A build saved in PoB is updated in PoB.
function characterDialog() {
  const b = state.build;
  let kind = "main";  // what the pasted code is when the build has no character yet: "main" or "build"
  const code = h("textarea", { rows: 7, placeholder: t("chCodePh"), spellcheck: "false" });
  const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } };
  const close = () => { back.remove(); document.removeEventListener("keydown", onKey, true); };
  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) close(); } });
  // PoB opened on this build (or brought forward) to copy the code from it
  const pobNote = h("div", { class: "action hidden" }, t("pobCodeOpened"));
  const openPob = h("button", { class: "ghost", onclick: async () => {
    try {
      const r = await api("/api/pob/open", { method: "POST" });
      if (r.state === "missing") { toast(t("pobMissing")); return; }
      pobNote.classList.remove("hidden");
      code.focus();
    } catch (e) { toast(e.message); }
  } }, t("pobOpen"));
  const opened = (nb, msg) => {
    state.build = nb;
    state.chat = [];
    state.changes = null;
    resetCache();
    renderHeader();
    loadBuildList();
    switchTab(state.tab);
    toast(msg, true);
  };
  const label = () => (b.main ? t("chGoUpdate") : kind === "main" ? t("chPut") : t("chGoBuild"));
  const put = h("button", { class: "primary", onclick: async () => {
    if (!code.value.trim()) { code.focus(); return; }
    put.disabled = true;
    put.textContent = t("chLoading");
    try {
      if (!b.main && kind === "main") {  // the first time: the character goes into the build
        const nb = await api("/api/character", { method: "POST", body: { code: code.value } });
        close();
        opened(nb, t("chLoaded", t("level", nb.main.level)));
      } else {  // a newer code of the character (or of the build): what changed is shown over the tabs
        await applyReload(code.value);
        close();
      }
    } catch (e) { toast(e.message); put.disabled = false; put.textContent = label(); }
  } }, label());
  // no character yet: what the code is - the player's character or the build's own newer version
  const pobBuild = h("div", { class: "stack hidden" }, h("div", { class: "sub" }, t("chPobBuild")),
    h("div", { class: "row" }, h("button", { class: "primary", onclick: () => { close(); updateViaPob(); } }, t("chPobUpdate"))));
  const pasteBox = h("div", { class: "stack" }, h("div", { class: "row" }, openPob), pobNote, code);
  const kindSeg = b.main ? null : h("div", { class: "segmented ch-kind" }, [["main", t("chKindMain")], ["build", t("chKindBuild")]].map(([k, text]) =>
    h("button", { class: k === kind ? "active" : "", onclick: (e) => {
      kind = k;
      kindSeg.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === e.currentTarget));
      const viaPob = kind === "build" && b.kind === "pob";  // a build saved in PoB changes only in PoB
      pobBuild.classList.toggle("hidden", !viaPob);
      pasteBox.classList.toggle("hidden", viaPob);
      put.classList.toggle("hidden", viaPob);
      put.textContent = label();
    } }, text)));
  const drop = b.main ? h("button", { class: "ghost", onclick: async () => {
    if (!(await confirmInPage(t("chDropAsk", b.name), t("chDrop")))) return;
    try {
      const nb = await api("/api/character", { method: "DELETE" });
      close();
      opened(nb, t("chDropped"));
    } catch (e) { toast(e.message); }
  } }, t("chDrop")) : null;
  back.append(h("div", { class: "ask card stack ch-dialog", role: "dialog", "aria-modal": "true" },
    h("h3", {}, b.main ? t("chTitleHas") : t("chTitle")),
    h("div", { class: "sub" }, b.main ? t("chSubHas", b.name) : t("chSub", b.name)),
    b.main ? h("div", { class: "small" }, "👤 ", t("chNow", `${trName(b.main.ascendancy || b.main.class)} · ${t("level", b.main.level)}`)) : null,
    kindSeg, pasteBox, pobBuild,
    h("div", { class: "row" }, put, drop, h("button", { class: "ghost", onclick: close }, t("cancel")))));
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
  code.focus();
}

// The build's own actions in one menu: bring it up to date (or put the player's character in), write it into the
// game's planner, copy its PoB code. Saving the plan's edits is on the edits' strip.
function openBuildMenu(on) {
  const list = $("#bh-menu-list");
  $("#bh-menu").setAttribute("aria-expanded", String(on));
  if (!on) { list.classList.add("hidden"); return; }
  const b = state.build;
  const item = (label, hint, title, fn) => h("button", { class: "bh-menu-item", role: "menuitem", title,
    onclick: () => { openBuildMenu(false); fn(); } }, h("b", {}, label), h("span", { class: "muted small" }, hint));
  list.replaceChildren(
    item(b.main ? t("chButtonHas") : t("chButton"), t("bhCharShort"), t("chButtonHint"), characterDialog),
    item(t("toPlanner"), t("bhPlannerShort"), t("toPlannerHint"), () => exportToPlanner()),
    item(t("svCode"), t("svCodeHint"), "", copyBuildCode));
  list.classList.remove("hidden");
}
$("#bh-menu").addEventListener("click", (e) => { e.stopPropagation(); openBuildMenu($("#bh-menu-list").classList.contains("hidden")); });
document.addEventListener("click", (e) => { if (!e.target.closest(".bh-menu-wrap")) openBuildMenu(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#bh-menu-list").classList.contains("hidden")) openBuildMenu(false); });

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
  const btn = $("#bh-menu"), label = $("#bh-menu-label");
  btn.disabled = true;
  label.textContent = t("reloading");
  try { await applyReload(""); } catch (e) { toast(e.message); }
  label.textContent = "";
  btn.disabled = false;
}

// the open build into the game's build planner folder (the game picks the file up at once)
async function exportToPlanner(overwrite = false) {
  const btn = $("#bh-menu");
  btn.disabled = true;
  try {
    const r = await api(`/api/planner/export?${buildQuery()}`,
      { method: "POST", body: { overwrite, lang: LANG, who: who(state.build.info) } });
    toast(t(r.overwritten ? "plannerReplaced" : "plannerWritten", r.file), true);
  } catch (e) {
    if (e.status !== 409) toast(e.message);
    else if (!overwrite && await confirmInPage(t("plannerExists", e.message), t("plannerReplace"))) {
      btn.disabled = false;
      return exportToPlanner(true);
    }
  } finally { btn.disabled = false; }
}

async function importFromPlanner(file, btn) {
  btn.disabled = true;
  try {
    const r = await api("/api/planner/import", { method: "POST", body: { file } });
    toast(t("added", r.name), true);
    await openBuild(r.name);
    if (r.report) plannerReport(r.report);
  } catch (e) { toast(e.message); btn.disabled = false; }
}

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
  for (const id of ["#build-header", "#bh-controls", "#tabs", "#changes", "#build-notice", "#ctor-bar", "#plan-strip"]) $(id).classList.add("hidden");
  if (AU.edit) authorToggle(false, false);  // no build: nothing to write about
}

document.addEventListener("click", (e) => {
  if (!e.target.closest("#main-skill")) document.querySelectorAll("#main-skill .picker-list").forEach((l) => l.classList.add("hidden"));
});

$("#mode").addEventListener("click", (e) => {
  const m = e.target.closest("button")?.dataset.mode;
  if (!m || m === state.mode) return;
  state.mode = m;
  document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
  switchTab(state.tab);
  schedulePreload();
});

$("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-tab]"); if (b) switchTab(b.dataset.tab); });

// ---------- folding cards ----------
// Every card with a heading folds by a click on it: long tabs become a list of headings to open what is needed.
// What is folded is remembered per tab and heading. Cards drawn later (a crafting panel, a chat) fold too.
const FOLD_KEY = "poe2lab.folded";
let folded = new Set();
try { folded = new Set(JSON.parse(localStorage.getItem(FOLD_KEY) || "[]")); } catch (_) { /* storage blocked */ }
const saveFolded = () => { try { localStorage.setItem(FOLD_KEY, JSON.stringify([...folded].slice(-500))); } catch (_) { /* storage blocked */ } };
// per page: a build tab, or a page of its own (journal, glossary, feedback)
const foldKey = (head) => `${state.page || state.tab}|${(head.dataset.foldName || head.textContent).trim().slice(0, 80)}`;
// a card folded until opened, its heading saying the main thing (a number, the best option) - the tab a list of lines
function foldedCard(card, name, summary) {
  const head = card && foldable(card);
  if (!head) return card;
  card.dataset.foldDefault = "1";
  head.dataset.foldName = name;
  if (summary) head.append(h("span", { class: "fold-sum" }, summary));
  return card;
}

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
// ---------- long explanations on demand ----------
// A card's long sub-heading (how a number is counted, what a list means) becomes a "?" by its title: the card reads
// as its heading and numbers, the explanation is one hover away (a click shows it too, for a touch screen). Short
// sub-headings and ones with controls or links in them stay as they are.
const SUB_LONG = 90;
function explainSubs(root) {
  root.querySelectorAll(".card > .sub").forEach((sub) => {
    const head = sub.previousElementSibling;
    const title = head && (head.tagName === "H3" || head.classList.contains("section-title") ? head : head.querySelector(":scope > h3"));
    if (!title || sub.children.length || sub.textContent.length < SUB_LONG) return;
    sub.remove();  // kept by the mark: a text added to it later still shows
    const mark = h("span", { class: "info sub-info", role: "note", "aria-label": sub.textContent }, "?");
    hoverTip(mark, () => h("div", { class: "small sub-tip" }, sub.textContent));
    mark.addEventListener("click", () => toast(sub.textContent, true));
    title.insertBefore(mark, title.querySelector(".fold-sum"));
  });
}
new MutationObserver(() => { explainSubs($("#view")); applyFolding($("#view")); }).observe($("#view"), { childList: true, subtree: true });

function foldAll(on) {
  $("#view").querySelectorAll(".card[data-fold]").forEach((card) => setFolded(card, card.querySelector(".fold-head"), on));
}
$("#fold-all").addEventListener("click", () => foldAll(true));
$("#unfold-all").addEventListener("click", () => foldAll(false));
$("#refresh-builds").addEventListener("click", loadBuildList);
$("#settings-open").addEventListener("click", (e) => {
  const on = $("#settings-box").classList.toggle("hidden") === false;
  e.currentTarget.setAttribute("aria-expanded", String(on));
  e.currentTarget.classList.toggle("active", on);
});
// the server runs with no window of its own (start.bat): stopping it is here
$("#stop-app").addEventListener("click", async () => {
  if (!(await confirmInPage(t("stopAsk"), t("stopApp")))) return;
  try {
    await api("/api/shutdown", { method: "POST" });
    document.body.replaceChildren(h("div", { class: "stopped-page" },
      h("h2", {}, t("stoppedTitle")), h("p", {}, t("stoppedText")), h("p", { class: "muted small" }, t("stoppedAgain"))));
  } catch (e) { toast(e.message); }
});

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
  const tab = MOVED_TABS[q.get("tab")] || q.get("tab");
  if (tab && TABS[tab]) state.tab = tab;
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
  state.page = null;
  if (tab !== state.tab) window.scrollTo(0, 0);  // a new tab starts at its top
  state.tab = tab;
  writeHash();
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  if (!state.build) return;
  renderCtorBar();
  await authorLoad();
  auButton();
  const view = $("#view");
  const token = Symbol();
  switchTab.token = token;
  try {
    // a build with the player's character: the tab on the character (Мейн) or the build it follows (Билд)
    const sided = state.build.main && SIDE_VIEWS[tab];
    const host = sided ? h("div", {}) : view;
    $("#scope").replaceChildren(...(sided ? [sideSwitch(tab)] : []));
    if (sided) view.replaceChildren(...[state.side === "build" ? guideRibbon() : null, host].filter(Boolean));
    const content = await (sided && state.side === "build" ? SIDE_VIEWS[tab] : TABS[tab])(host);
    if (switchTab.token === token && content) host.replaceChildren(content);
    if (switchTab.token === token) renderPlanStrip();
  } catch (e) {
    if (switchTab.token === token) view.replaceChildren(errorCard(e));
  }
}

// What went wrong, in the page: the message, the code it is logged under, and a report with the log in one click
function errorCard(e) {
  return h("div", { class: "card stack" }, h("h3", {}, "⚠ ", t("error")), h("p", { class: "muted" }, e.message),
    e.errorId ? h("div", { class: "small muted" }, t("errLogged", e.errorId)) : null,
    h("div", { class: "row" }, h("button", { class: "primary small", onclick: () => reportError(e) }, "📨 ", t("errReport"))));
}

// What each skill does for the build (poe2lab.analysis.skills.roles): the main damage; what the main skill loses
// without it (a buff), what the effective life loses (a defence), its own damage, the charges it makes for the main
// skill - or nothing PoB counts; the same skill in two groups: how each copy is used and the supports only it has.
// Put into each group's card in `box` (by data-group) once they come.
function fillRoles(box, rr) {
  if (!rr || !rr.main) return;
  const mainName = trName(rr.skill || "");
  const pct = (v) => `${v > 0 ? "+" : ""}${fmt(v, 1)}%`;
  const how = (x) => (x.meta ? t("rlHowMeta", trName(x.meta)) : x.slot ? t("rlHowItem", slotName(x.slot)) : t("rlHowSelf"));
  for (const r of rr.groups) {
    const card = box.querySelector(`[data-group="${r.group}"]`);
    if (!card) continue;
    const chips = [];
    if (r.main) chips.push(chip("ok", t("rlMain")));
    else {
      if (r.dps <= -1) chips.push(chip("tag", t("rlLoses", mainName, pct(r.dps))));
      if (r.ehp <= -1) chips.push(chip("tag", t("rlLosesEhp", pct(r.ehp))));
      for (const m of r.gives) chips.push(chip("tag", t("rlGives", (LANG === "en" && MECH_EN[m.key]) || m.name, mainName)));
      if (r.own >= 1) chips.push(chip("util", t("rlOwn", fmt(r.own, r.own < 10 ? 1 : 0), mainName)));
      if (!chips.length) chips.push(h("span", { class: "chip", title: t("rlNothing", mainName) }, t("rlNothingShort")));
    }
    const copies = r.copies.map((c) => h("div", { class: "small" }, "🔁 ", t("rlCopy", trName(c.skill), c.group), " ",
      h("span", { class: "muted" }, t("rlHere"), " ", how(r), "; ", t("rlThere"), " ", how(c)),
      r.only.length ? [" · ", t("rlOnly", r.only.map(trName).join(", "))] : null));
    // in a skills card's head (seen folded too): the role chips before the numbers; the copies under the head
    const sk = card.querySelector(".sk-head");
    if (sk) {
      const roleBox = h("span", { class: "sk-role-chips", title: t("rlHint") }, ...chips);
      sk.insertBefore(roleBox, sk.querySelector(".sk-head-nums, .fold-sum"));
      if (copies.length) sk.parentNode.insertBefore(h("div", { class: "sk-role" }, ...copies), sk.nextSibling);
      continue;
    }
    const line = h("div", { class: "sk-role", title: t("rlHint") }, h("div", { class: "row" }, ...chips), ...copies);
    const head = card.querySelector(".row, h3");
    (head ? head.parentNode : card).insertBefore(line, head ? head.nextSibling : card.firstChild);
  }
}

// a weapon tried on: each skill's damage now and with it, in a few lines
function skillsWith(rows) {
  return h("div", { class: "sk-quick" }, h("b", {}, "⚔ ", t("mkSkillsTitle")),
    h("table", { class: "ex-table" }, h("tbody", {}, rows.map((x) => {
      const change = x.now ? (x.with / x.now - 1) * 100 : 0;
      return h("tr", {}, h("td", {}, gemName(x.name)), h("td", { class: "num muted" }, fmt(x.now)), h("td", { class: "num" }, "→ ", h("b", {}, fmt(x.with))),
        h("td", { class: "num " + (x.with < 1 ? "neg" : change >= 0.5 ? "pos" : change <= -0.5 ? "neg" : "muted") },
          x.with < 1 ? t("mkSkillNo") : pct(change)));
    }))));
}

// the feedback form opened with the error written in and the log ticked
function reportError(e) {
  const where = t("tab_" + state.tab) !== "tab_" + state.tab ? t("tab_" + state.tab) : state.tab;
  const line = t("errReportText", where, e.message) + (e.errorId ? ` [${e.errorId}]` : "");
  if (!fbDraft.message.includes(line)) fbDraft.message = (fbDraft.message ? fbDraft.message + "\n" : "") + line;
  fbDraft.attachLog = true;
  renderFeedback();
}

// the page's own errors go into poe2lab's log too (each once, a few per page at most)
const loggedPageErrors = new Set();
function logPageError(message, stack) {
  if (!message || loggedPageErrors.has(message) || loggedPageErrors.size >= 20) return;
  loggedPageErrors.add(message);
  api("/api/log", { method: "POST", body: { message: String(message).slice(0, 2000), stack: String(stack || "").slice(0, 4000),
    tab: state.tab || "" } }).catch(() => {});
}
window.addEventListener("error", (ev) => logPageError(ev.message, ev.error && ev.error.stack));
window.addEventListener("unhandledrejection", (ev) => {
  const r = ev.reason;
  if (r && r.status) return;  // the server's own answer: already in the log when it is an error there
  logPageError(r && r.message ? r.message : String(r), r && r.stack);
});

const report = () => cached(`report:${state.mode}`, () => api(`/api/report?mode=${state.mode}&${buildQuery()}`));
// The tabs' data, a fetcher each: a tab and the preloader ask through these, so both land in one cache entry
const DATA = {
  gear: () => cached(`gear:${state.mode}`, () => api(`/api/gear?mode=${state.mode}&${buildQuery()}`)),
  tree: () => {
    const points = state.treePoints || 6;
    return cached(`tree:${state.mode}:${points}`, () => api(`/api/tree?mode=${state.mode}&points=${points}&${buildQuery()}`));
  },
  jewels: () => cached("jewels", () => api(`/api/jewels?${buildQuery()}`)),
  packages: () => cached(`packages:${state.mode}`, () => api(`/api/tree/packages?mode=${state.mode}&${buildQuery()}`)),
  leveling: () => cached("leveling", () => api(`/api/leveling?${buildQuery()}`)),
  skills: (view) => cached(`skills:${view}`, () => api(`/api/skills?view=${view}&${buildQuery()}`)),
  // levelling follows the build's target (the guide the player plays by) unless the player asks for the build
  skillsLeveling: () => {
    const of = (state.build.profileRaw || {}).target && state.levelOf !== "build" ? "target" : "";
    return cached(`skills:leveling${of ? ":target" : ""}`, () => api(`/api/skills?view=leveling${of ? "&of=target" : ""}&${buildQuery()}`));
  },
  uniques: () => {
    const scope = state.uniqueScope || "level";
    return cached(`skills:uniques:${scope}`, () => api(`/api/skills?view=uniques&scope=${scope}&${buildQuery()}`));
  },
  unmodeled: () => cached("unmodeled", () => api(`/api/unmodeled?${buildQuery()}`)),
};

// ---------- every tab worked out when a build opens: switching tabs is then instant until something changes ----------
// Each step is one request a tab makes (through DATA, the same cache entry); the server answers them one by one
// anyway, the open tab's first. How long each took the last time is remembered per build: the bar moves by time
// and says how long it is going to take.
function preloadSteps() {
  const steps = [
    ["overview", () => report()], ["overview", () => questsData()], ["overview", () => DATA.leveling()],
    ["skills", () => DATA.skills("build")], ["skills", () => DATA.skills("explain")], ["skills", () => DATA.skills("supports")],
    ["skills", () => DATA.skills("roles")], ["skills", () => DATA.skillsLeveling()],
    ["gear", () => DATA.gear()], ["gear", () => DATA.uniques()],
    ["tree", () => DATA.tree()], ["tree", () => treeGraph()], ["tree", () => ascData()], ["tree", () => DATA.jewels()],
    ["tree", () => DATA.packages()], ["overview", () => DATA.unmodeled()], ["profile", () => questsData()]];
  // the guide's side of a build with the player's character
  if (state.build.main) steps.push(["overview", () => guideVersus()], ["gear", () => guideGear()]);
  // the open tab first
  return [...steps.filter(([tab]) => tab === state.tab), ...steps.filter(([tab]) => tab !== state.tab)];
}
const PRELOAD_TABS = ["overview", "skills", "gear", "tree", "profile"];
const PRELOAD_ICON = { overview: "compass", skills: "gem", gear: "helm", tree: "tree", profile: "id" };
const preloadKey = () => `poe2lab.preload.${state.build.name}.${state.mode}`;

function schedulePreload() {
  clearTimeout(schedulePreload.timer);
  schedulePreload.timer = setTimeout(() => { if (state.build) preload(false); }, 400);
}

// Runs the steps; with `blocking`, a card in the page shows the progress until everything is done or the player
// opens the build at once (the promise returned settles then); the strip under the tabs shows it in any case.
function preload(blocking) {
  clearTimeout(schedulePreload.timer);
  const b = state.build, token = Symbol();
  preload.token = token;
  const steps = preloadSteps();
  let last = null;
  try { last = JSON.parse(localStorage.getItem(preloadKey()) || "null"); } catch (_) { /* storage blocked */ }
  const known = last && last.steps ? last.steps : {};
  // each step's share of the bar: its time the last time (a request worked out already is quick)
  const weight = steps.map(([tab], i) => Math.max(150, known[`${tab}:${i}`] || 1500));
  const sum = weight.reduce((a, x) => a + x, 0);
  const estimate = last ? Math.round(last.total / 1000) : null;
  let release;
  const gate = new Promise((r) => { release = r; });

  const strip = $("#preload-strip");
  const fill = (cls) => h("div", { class: "pl-bar " + cls }, h("i"));
  const stripBar = fill("thin");
  const stripText = h("span", { class: "muted small" });
  strip.replaceChildren(I("hourglass"), stripBar, stripText);
  strip.classList.toggle("hidden", blocking);
  const chips = Object.fromEntries(PRELOAD_TABS.map((tab) => [tab, h("span", { class: "pl-tab wait" }, I(PRELOAD_ICON[tab]), t("tab_" + tab))]));
  const cardBar = fill("big");
  const timeText = h("span", {});
  const card = blocking ? h("div", { class: "card stack pl-card" }, h("h3", {}, t("plTitle", b.name)), h("div", { class: "sub" }, t("plSub")),
    cardBar, h("div", { class: "row pl-time" }, timeText, h("span", { class: "muted small" }, estimate ? t("plLast", estimate) : t("plFirst"))),
    h("div", { class: "pl-tabs" }, PRELOAD_TABS.map((tab) => chips[tab])),
    h("div", { class: "row" }, h("button", { class: "ghost", onclick: () => release() }, t("plOpenNow")), h("span", { class: "muted small" }, t("plOpenNowHint")))) : null;
  if (card) $("#view").replaceChildren(card);

  const t0 = performance.now();
  // the bar runs toward the end of the step it is in, over the time that step took the last time
  const move = (done, i) => {
    for (const bar of [cardBar, stripBar]) {
      const bit = bar.firstChild;
      bit.style.transition = "none";
      bit.style.width = `${(done / sum) * 100}%`;
      void bit.offsetWidth;
      bit.style.transition = `width ${weight[i]}ms linear`;
      bit.style.width = `${((done + weight[i] * 0.95) / sum) * 100}%`;
    }
  };
  const clock = setInterval(() => {
    const sec = Math.round((performance.now() - t0) / 1000);
    timeText.textContent = t("plTime", sec);
  }, 500);
  const finish = () => { clearInterval(clock); release(); };

  (async () => {
    const took = {};
    let done = 0;
    for (let i = 0; i < steps.length; i++) {
      if (preload.token !== token || state.build !== b) { finish(); return; }  // another build, or a newer run
      const [tab, run] = steps[i];
      chips[tab].className = "pl-tab work";
      stripText.textContent = t("plStrip", t("tab_" + tab), i + 1, steps.length);
      strip.classList.toggle("hidden", !!card && card.isConnected);  // the card says it while it is there
      move(done, i);
      const s0 = performance.now();
      let failed = false;
      try { await run(); } catch (_) { failed = true; }  // the tab shows the error itself (and asks again)
      took[`${tab}:${i}`] = Math.round(performance.now() - s0);
      done += weight[i];
      if (failed) chips[tab].classList.add("fail");
      if (!steps.slice(i + 1).some(([x]) => x === tab)) chips[tab].className = "pl-tab " + (chips[tab].classList.contains("fail") ? "fail" : "done");
    }
    if (preload.token !== token) { finish(); return; }
    try { localStorage.setItem(preloadKey(), JSON.stringify({ total: performance.now() - t0, steps: took })); } catch (_) { /* storage blocked */ }
    strip.classList.add("hidden");
    finish();
  })();
  return gate;
}

// ---------- a build with the player's character: its tabs as the build (the guide) has them, against the character ----------
function sideSwitch(tab) {
  const side = state.side || "main";
  return h("div", { class: "seg scope", title: t("sideHint") },
    [["main", "me", "person", t("sideMainShort")], ["build", "guide", "scroll", t("sideBuildShort")]].map(([k, who_, ic, label]) => h("button", {
      class: side === k ? `is-on ${who_}` : "", onclick: () => { state.side = k; switchTab(tab); } },
    h("span", { class: "av " + who_ }, I(ic)), label)));
}
// the view is the guide's: a ribbon over it says so
const guideRibbon = () => h("div", { class: "ribbon" }, h("span", { class: "av guide" }, I("scroll")),
  h("span", {}, h("b", {}, t("ribbonGuide")), " · ", t("ribbonVs", who(state.build.guide), state.build.info.level)));
const guideGear = () => cached("refgear:" + RECORDED_REF, () => api(`/api/versus/gear?ref=${RECORDED_REF}&${buildQuery()}`));
const guideVersus = () => cached("versus:" + RECORDED_REF, () => api(`/api/versus?ref=${RECORDED_REF}&${buildQuery()}`));
const guideHead = (g) => h("div", { class: "sub" }, t("sideGuideIs", `${trName(g.ascendancy || g.class)} · ${t("level", g.level)}`, trName(g.skill)));
const SIDE_VIEWS = {
  // the two characters' numbers side by side
  overview: async (view) => {
    view.replaceChildren(loading(t("refLoading")));
    const [g, v] = await Promise.all([guideGear(), guideVersus()]);
    return h("div", { class: "card stack" }, h("h3", {}, t("sideOverviewTitle")), guideHead(g), ...versusStats(v, t("sideBuildCol")));
  },
  // the build's gem groups: which gems the character has, lower, or lacks
  skills: async (view) => {
    view.replaceChildren(loading(t("refLoading")));
    const s = await cached("versus-skills", () => api(`/api/versus/skills?ref=${RECORDED_REF}&${buildQuery()}`));
    const have = new Map();
    for (const g of s.mine) if (g.enabled) for (const gem of g.gems) if (gem.enabled && (!have.has(gem.name) || have.get(gem.name).level < gem.level)) have.set(gem.name, gem);
    const theirs = new Set(s.ref.flatMap((g) => g.gems.map((x) => x.name)));
    let missing = 0, lower = 0;
    const row = (gem) => {
      const m = have.get(gem.name);
      const status = !m ? "missing" : m.level < gem.level ? "lower" : "ok";
      if (status === "missing") missing++;
      if (status === "lower") lower++;
      return h("div", { class: "vs-gem " + status }, gemName(gem.name),
        h("span", { class: "muted small" }, t("vsGemLevel", gem.level, gem.quality)),
        status === "missing" ? chip("warn", t("vsGemMissing")) : status === "lower" ? chip("tag", t("vsGemLower", m.level)) : chip("ok", "✓"));
    };
    const cards = s.ref.filter((g) => g.gems.length).map((g) => {
      const [m0, l0] = [missing, lower];
      const card = h("div", { class: "card vs-group" + (g.main ? " main" : ""), "data-group": g.index },
        h("h3", {}, g.actives.map((a) => trName(a.name)).join(" + ") || g.label || t("vsGroup", g.index), g.main ? " " : null, g.main ? chip("ok", t("vsMainGroup")) : null),
        h("div", { class: "vs-gems" }, g.gems.map(row)));
      const [m, l] = [missing - m0, lower - l0];
      return m || l || g.main ? card : foldedCard(card, "vs" + g.index, "✓");
    });
    const grid = h("div", { class: "grid two masonry" }, cards);
    cached("skills:roles:guide", () => api(`/api/skills?view=roles&of=guide&${buildQuery()}`))
      .then((rr) => fillRoles(grid, rr)).catch(() => {});
    const extra = [...have.keys()].filter((n) => !theirs.has(n));
    // how the guide works: its crit, mana and meta gems (the character's are on the Main side)
    const explained = h("div", { class: "grid two masonry" }, loading(t("exLoading")));
    cached("skills:explain:guide", () => api(`/api/skills?view=explain&of=guide&${buildQuery()}`))
      .then((d) => explained.replaceChildren(...explainCards(d, null)))
      .catch((e) => explained.replaceChildren(errorCard(e)));
    return h("div", { class: "stack" }, h("div", { class: "card" }, h("h3", {}, t("vsSkillsTitle")), h("div", { class: "sub" }, t("vsSkillsSum", missing, lower))),
      h("div", { class: "section-title" }, "🔍 ", t("exTitleGuide")), explained,
      grid,
      extra.length ? h("div", { class: "card" }, h("h3", {}, t("vsSkillsExtra")), h("div", { class: "vs-gems" }, extra.map((n) => h("div", { class: "vs-gem" }, gemName(n))))) : null);
  },
  // the build's gear on the dolls next to the character's
  gear: () => compareView(),
  // the build's passives the character has not taken, and the character's the build does not have
  tree: async (view) => {
    view.replaceChildren(loading(t("refLoading")));
    const [d, graph] = await Promise.all([cached("versus-tree", () => api(`/api/versus/tree?ref=${RECORDED_REF}&${buildQuery()}`)), treeGraph()]);
    const big = (list) => list.filter((n) => n.type !== "Normal" || n.ascendancy);
    // a node's name; the pointer over it shows its kind and lines
    const kind = (n) => (n.type === "Keystone" ? t("keystone") : n.type === "Notable" ? t("notable") : n.type === "Socket" ? t("vsNodeSocket") : t("vsNodeSmall"));
    const name = (n) => hoverTip(h("span", { class: "named pk-node" }, icon(n.name, "ico passive"), trName(n.name),
      n.ascendancy ? h("span", { class: "muted small" }, ` (${trName(n.ascendancy)})`) : null),
    () => h("div", { class: "stack" },
      h("div", { class: "row", style: "gap:8px;align-items:center" }, icon(n.name, "ico passive"), h("b", {}, trName(n.name))),
      h("div", { class: "muted small" }, kind(n), n.ascendancy ? ` · ${trName(n.ascendancy)}` : ""),
      (n.stats || []).length ? stats(n.stats) : null,
      // a socket: the jewel that sits in it
      n.jewel ? h("div", { class: "stack", style: "gap:4px" },
        h("div", { class: "row", style: "gap:6px;align-items:center" }, itemIcon(n.jewel.name, n.jewel.base, (n.jewel.rarity || "").toLowerCase()),
          h("b", { class: "r-" + (n.jewel.rarity || "normal").toLowerCase() }, itemTitle({ name: n.jewel.name, baseName: n.jewel.base }))),
        h("ul", { class: "item-lines small" }, n.jewel.lines.map((l) => h("li", {}, trMod(l))))) : null));
    // the tree itself, right away: the build's nodes the character lacks in blue, the character's extra ones ringed;
    // after an edit on it the lists below are from before - recount on demand
    const stale = h("div", { class: "action hidden tv-stale" }, t("tvEditedNote"), " ",
      h("button", { class: "primary small", onclick: () => { resetCache(); switchTab("tree"); } }, t("tvRecount")));
    const mapBox = h("div", { class: "tree-embed-box" });
    try {
      openTreeViewer(graph, { growth: [], respec: d.extra.map((n) => ({ id: n.id })) }, null, {
        embed: mapBox, onEdit: () => stale.classList.remove("hidden"),
        focus: { mechanic: "guide", label: t("vsTreeFocus"), take: false, points: d.missing.length,
          notables: big(d.missing).map((n) => ({ id: n.id, name: n.name, points: 1 })), path: d.missing.map((n) => n.id) } });
    } catch (e) { mapBox.append(h("p", { class: "muted" }, e.message)); }
    return h("div", { class: "stack" },
      h("div", { class: "row vs-tree-sum" }, h("b", {}, t("vsTreeSum", d.missing.length, d.extra.length)),
        h("span", { class: "muted small" }, t("vsTreePoints", d.refPoints.used, d.points.used)),
        h("span", { class: "muted small" }, t("vsTreeShowHint"))),
      mapBox, stale,
      big(d.missing).length ? h("div", { class: "card" }, h("h3", {}, t("vsTreeMissing", big(d.missing).length)),
        h("div", { class: "vs-nodes" }, big(d.missing).map(name))) : null,
      big(d.extra).length ? h("div", { class: "card" }, h("h3", {}, t("vsTreeExtra", big(d.extra).length)),
        h("div", { class: "vs-nodes" }, big(d.extra).map(name))) : null);
  },
};
// the "unit" is either the Rage stat or a probe mod line
// a passive node's lines, translated (several PoB lines may be one game text), the original on hover
const stats = (lines) => h("ul", { class: "item-lines small" }, trLines(lines).map(([src, text]) => h("li", { title: LANG === "en" ? null : src }, text)));
const unitName = (name) => (LANG === "ru" && name === "Maximum Rage" ? "максимум свирепости" : trMod(name));

// ---------- overview ----------
// the damage where the build's own ailments put it: each for the share of the fight it holds (analysis/combat.py)
const expectedShown = (rng) => rng.uptimes && rng.uptimes.length && Math.abs(rng.expected / rng.low - 1) >= 0.005;
function expectedLine(rng) {
  if (!expectedShown(rng)) return null;
  const shares = rng.uptimes.map((u) => `${conditionLabel(u.label).replace(/\?\s*$/, "")} ${Math.round(u.uptime * 100)}%`).join(", ");
  return h("p", { title: t("expectedHint") }, t("expectedIs"), h("b", {}, fmt(rng.expected)), " ", h("span", { class: "muted small" }, t("expectedShares", shares)));
}

TABS.overview = async (view) => {
  view.replaceChildren(loading(t("calcReport")));
  const r = await report();
  const b = r.baseline;
  const rng = r.damageRange;
  const hits = Object.entries(b.survivableHit);

  // the build's numbers: one tile each, an icon and the number big
  const tile = (ic, label, value, ...notes) => h("div", { class: "card kpi stat" },
    h("div", { class: "stat-l" }, I(ic), label), h("div", { class: "stat-n" }, ...value),
    ...notes.filter(Boolean).map((n) => h("div", { class: "stat-s" }, n)));
  const kpi = [
    tile("sword", b.minions ? t("dpsMinions") : t("dps"), [fmt(rng.low), rng.high > rng.low ? h("small", {}, ` … ${fmt(rng.high)}`) : null],
      b.minions ? t("minionsNote", b.minions.count, fmt(b.minions.perMinion)) : rng.high > rng.low ? t("dpsRangeNote") : trName(r.build.mainSkill),
      expectedShown(rng) ? h("span", { title: t("expectedHint") }, t("expectedShort", fmt(rng.expected))) : null),
    tile("heart", b.es > 0 ? t("lifeAndEs") : t("life"),
      [fmt(b.life), ...(b.es > 0 ? [h("span", { class: "plus" }, "+"), h("span", { class: "es" }, fmt(b.es))] : [])],
      b.es > 0 ? t("lifeEsNote") : null),
    tile("target", t("hitChance"), [fmt(b.hitChance) + "%"]),
    tile("drop", t("recovery"), [fmt(b.recoveryPerSecond), h("small", {}, " " + t("perSec").trim())],
      b.recoveryPool === "es" ? t("esRecoveryNote") : t("whileAttacking"))];

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

  const worstShare = worst && share(worst[0], worst[1].juiced);
  // a part of the report that failed: the rest shows, and the player can send it
  const failed = (r.failed || []).length ? h("div", { class: "action" }, t("ovFailed", r.failed.join(", ")), " ",
    h("button", { class: "ghost small", onclick: () => reportError({ message: t("ovFailed", r.failed.join(", ")) }) }, "📨 ", t("errReport"))) : null;
  // what to do next beside the numbers; the way to the build under them, across the page
  return h("div", { class: "stack" }, failed, auCard("ov:about", t("auAbout"), t("auAboutPh")),
    h("div", { class: "ov" }, nextCard(r), h("div", { class: "ov-stats" }, ...kpi,
      foldedCard(hitCard, "hits", worst ? t("hitsSum", t("dmgFull_" + worst[0]), worstShare >= 100 ? t("oneShot") : `${fmt(worstShare)}%`) : null))),
    unmodeledCard(), levelingCard(), questMapCard());
};

// The first things to do, in order: what is broken in game, the biggest weakness, the most rewarding next mod; each
// with the tab where it is dealt with.
const GATE_TAB = [[/резист/i, "gear"], [/не хватает (силы|ловкости|интеллекта)|на грани|держатся требования/i, "tree"],
  [/spirit|маны/i, "gear"], [/слабость/i, "gear"], [/регенерации|жизнь в бою|похищение|энергощите/i, "gear"],
  [/попадания/i, "gear"]];
// What to do next, in one place: what is broken in game and the biggest weakness (the report), then the best step
// of each part of the build - a passive, a craft in a slot, a rune in a socket - most worth first (the same goal
// score everywhere), and the main skill's support that gives almost nothing. Each with a button to where it is done.
// The parts' steps come from the tabs' own analyses (their cache), loaded after the page is shown.
function nextCard(r) {
  const gateText = (g) => LANG === "en" && g.title_en ? g.title_en : trFree(g.title);
  const detailText = (g) => LANG === "en" && g.detail_en ? g.detail_en : trFree(g.detail);
  const goBtn = (fn) => h("button", { class: "go next-go", onclick: fn }, t("nextGo"));
  const tabOf = (g) => (GATE_TAB.find(([re]) => re.test(g.title)) || [null, null])[1];
  const goSlot = (slot) => () => {
    state.gear = { build: state.build.name, slot, set: /Swap/.test(slot) ? 2 : 1 };
    switchTab("gear");
  };
  // a step: its kind's picture, what it is, its gain in damage and defence big on the right, the hits under it
  const BIG = METRIC.filter(([k]) => k === "dps" || k === "ehp");
  const rest = METRIC.filter(([k]) => k !== "dps" && k !== "ehp");
  const gains = (changes) => h("div", { class: "step-v" }, BIG.filter(([k]) => Math.abs(changes[k] || 0) >= 0.3).map(([k, label]) =>
    h("span", { class: "metric", title: t("mh_" + k) }, h("span", { class: "metric-l" }, t(label)),
      h("span", { class: "step-n " + (changes[k] > 0 ? "up" : "down") }, pct(changes[k])))));
  const hitsOf = (changes) => (rest.some(([k]) => Math.abs(changes[k] || 0) >= 0.3) ? deltas(changes, rest, 0.3) : null);
  const row = (icon, label, what, extra, go, changes) => h("li", { class: "next-row next-step" },
    h("span", { class: "next-ico" }, icon),
    h("div", { class: "next-body" }, h("div", { class: "step-k" }, label), h("div", { class: "step-t" }, what), extra, changes ? hitsOf(changes) : null),
    changes ? gains(changes) : h("span"),
    go ? goBtn(go) : h("span"));
  // what is broken and where the holes are: one line each, the explanation opens on a click
  const ICON = { must: "broken", priority: "warn", warn: "info" };
  const order = { must: 0, priority: 1, warn: 2 };
  const gateRow = (g) => h("li", { class: "next-row next-gate " + g.level },
    h("span", { class: "next-ico" }, I(ICON[g.level])),
    h("details", { class: "next-body" }, h("summary", {}, h("span", { class: "al-k" }, t("lvl_" + g.level)), h("span", { class: "al-t" }, gateText(g))),
      h("div", { class: "small muted" }, detailText(g))),
    h("span"), tabOf(g) ? goBtn(() => switchTab(tabOf(g))) : h("span"));
  const list = h("ol", { class: "start-steps next-steps" });
  const gates = [...r.gates].sort((a, c) => order[a.level] - order[c.level]);
  list.append(...gates.filter((g) => g.level !== "warn").map(gateRow));
  // the smaller things to keep in mind: one line that opens into them
  const minor = [...gates.filter((g) => g.level === "warn").map((g) => h("div", { class: "next-minor" },
    h("details", {}, h("summary", {}, gateText(g)), h("div", { class: "small muted" }, detailText(g))),
    tabOf(g) ? goBtn(() => switchTab(tabOf(g))) : null)),
    ...Object.values(r.attributes.supportsAtRisk || {}).map((risk) => h("div", { class: "next-minor small" },
      h("span", { class: "muted" }, t("supportsAtRisk"), " "), risk.map((x) => `${trName(x.name)} ${pct(x.skill_dps_pct)}`).join(" · ")))];
  if (minor.length) {
    list.append(h("li", { class: "next-row next-gate warn" }, h("span", { class: "next-ico" }, I("info")),
      h("details", { class: "next-body" }, h("summary", {}, h("span", { class: "al-t" }, t("nextMinor", minor.length))), ...minor)));
  }
  const pending = h("li", { class: "next-wait muted small" }, loading(t("nextLoading")));
  list.append(pending);

  (async () => {
    const [tree, gear, skills, quest] = await Promise.allSettled([
      DATA.tree(), DATA.gear(), DATA.skills("build"), questStep()]);
    const steps = [];  // [score, row]
    if (quest.status === "fulfilled" && quest.value) {
      const [q, o] = quest.value;
      steps.push([o.score, row(I("chest", "c-gold"), t("nextQuest", questName(q)), optionTitle(q, q.options.indexOf(o)) || optionText(o),
        h("div", { class: "small muted" }, t("nextQuestNote", questWhere(q)).replace(/\s*·\s*$/, "")), () => switchTab("profile"), o.changes)]);
    }
    const g = tree.status === "fulfilled" && tree.value.growth[0];
    if (g) {
      steps.push([g.value, row(I("tree", "c-tree"), h("span", {}, h("b", {}, t("tab_tree")), " · ", t("nextTreeNote", g.points).replace(/\s*·\s*$/, "")),
        trName(g.name), null, () => switchTab("tree"), g.changes)]);
    }
    if (gear.status === "fulfilled") {
      const c = gear.value.craftPath[0];
      if (c) {
        steps.push([c.score, row(I("anvil", "c-gold"), t("nextCraft", slotName(c.slot)),
          (c.removed.length ? trMod(c.removed.join(" / ")) + " → " : t("craftAdd") + " ") + trMod(c.added.join(" / ")),
          null, goSlot(c.slot), c.changes)]);
      }
      // the socket where a rune gains most over what sits there now
      const runes = gear.value.sockets.filter((s) => s.best.length).map((s) => [s.best[0].score - s.current_score, s]);
      const [gain, s] = runes.sort((a, b) => b[0] - a[0])[0] || [0, null];
      if (s && gain > 0) {
        steps.push([gain, row(icon(s.best[0].name) || I("jewel", "c-gold"), t("nextRune", slotName(s.slot)), trName(s.best[0].name),
          s.current && s.current !== "None" ? h("div", { class: "small muted" }, t("nextRuneInstead", trName(s.current)).replace(/\s*·\s*$/, "")) : null,
          goSlot(s.slot), s.best[0].changes)]);
      }
    }
    steps.sort((a, b) => b[0] - a[0]);
    // the main skill's support that gives it least: a place for a better one (not a gain of its own - last)
    if (skills.status === "fulfilled") {
      const main = skills.value.groups.find((x) => x.main);
      const key = state.mode === "defence" ? "ehp" : "dps";
      // a support that waits for a Configuration box is not a weak one; one hit of a triggered skill has no EHP
      const measured = main ? main.gems.filter((x) => x.support && x.enabled && x.worth && !x.worthIf && key in x.worth) : [];
      const weakest = measured.sort((a, b) => (a.worth[key] || 0) - (b.worth[key] || 0))[0];
      if (weakest && (weakest.worth[key] || 0) < 1) {
        steps.push([0, row(I("gem", "c-mana"), t("nextGem"), gemName(weakest.name),
          h("div", { class: "small muted" }, t("nextGemNote", pct(weakest.worth[key] || 0))), () => switchTab("skills"))]);
      }
    }
    pending.replaceWith(...(steps.length ? steps.map((x) => x[1]) : [h("li", { class: "next-wait muted small" }, t("nextNone"))]));
  })();

  // the upgrade path: mod after mod, each counted with the ones before it - folded to its first step
  const path = r.path.length ? h("details", { class: "next-path" },
    h("summary", {}, I("chart", "c-gold"), " ", h("b", {}, t("pathTitle")), " ", h("span", { class: "muted small" }, t("firstStep", trMod(r.path[0].mod)))),
    h("div", { class: "small muted" }, t("pathSub")),
    h("ol", { class: "path-compact" }, r.path.map((x) => h("li", {}, h("span", { class: "mod" }, trMod(x.mod)), " ",
      deltas({ dps: x.dps, phys_hit: x.defence.Physical, chaos_hit: x.defence.Chaos, recovery: x.recovery }))))) : null;
  return h("div", { class: "card start-card ornate ov-next" }, h("h3", {}, I("compass", "ic-l c-gold"), " ", t("nextTitle")),
    h("div", { class: "sub" }, t("nextSub", t("mode_" + state.mode))), list, path);
}

// ---------- damage ----------
// what the main skill's damage is made of: its core (charges, rage), the combat conditions, where to invest - the
// Skills tab's "Damage" mode
function renderDamage(r) {
  const blocks = [];
  const core = r.core;
  if (core.resources.length || core.exchange.length) {
    const res = core.resources.map((x) => h("p", {},
      t("resourceLine", { name: t("res_" + x.name.replace(/ /g, "")), counted: x.counted, assumed: fmt(x.assumed),
        maximum: fmt(x.maximum), without: fmt(x.dps_without), with: fmt(x.dps_with), mult: fmt(x.dps_with / x.dps_without, 2),
        ehp: x.ehp_without && Math.abs(x.ehp_with / x.ehp_without - 1) >= 0.005 ? `EHP ${fmt(x.ehp_without)} → ${fmt(x.ehp_with)}` : "" }),
      x.name === "Rage" && !x.set_in_build ? h("span", { class: "muted" }, t("rageEmpty")) : null));
    const coreSum = core.resources.map((x) => `${t("res_" + x.name.replace(/ /g, ""))} ×${fmt(x.dps_with / x.dps_without, 2)}`).join(" · ");
    blocks.push(foldedCard(h("div", { class: "card" }, h("h3", {}, t("coreTitle")), res,
      core.unit ? h("div", { class: "sub" }, t("rate", unitName(core.unit.name), pct(core.unit.dps_pct_per_point))) : null,
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("colMod")), h("th", { class: "num" }, "DPS"), h("th", { class: "num" }, t("colUnits")))),
        h("tbody", {}, core.exchange.slice(0, 12).map((x) => h("tr", {}, h("td", { class: "mod", title: x.mod }, trMod(x.mod)), h("td", { class: "num" }, pct(x.dps)), h("td", { class: "num" }, fmt(x.points, 1))))))),
    "core", coreSum || null));
  }

  const rng = r.damageRange;
  const off = r.conditions.filter((c) => !c.checked);
  const on = r.conditions.filter((c) => c.checked);
  const condRow = (c) => h("tr", {}, h("td", { title: c.label }, conditionLabel(c.label)),
    h("td", {}, deltas({ dps: c.dps_pct, phys_hit: c.phys_hit_pct, chaos_hit: c.chaos_hit_pct, recovery: c.recovery_pct }, METRIC, 0.5)));
  const [a, lo, b2, hi, c2] = t("range", fmt(rng.low), fmt(rng.high), fmt(rng.high / rng.low, 2));
  blocks.push(foldedCard(h("div", { class: "card" }, h("h3", {}, t("condTitle")),
    rng.conditions.length ? h("p", {}, a, h("b", {}, lo), b2, h("b", {}, hi), c2) : null,
    expectedLine(rng),
    off.length ? h("div", { class: "sub" }, t("condOff")) : null,
    off.length ? h("table", {}, h("tbody", {}, off.map(condRow))) : null,
    on.length ? h("div", { class: "sub", style: "margin-top:12px" }, t("condOn")) : null,
    on.length ? h("table", {}, h("tbody", {}, on.map(condRow))) : null),
  "conditions", rng.high > rng.low ? `DPS ${fmt(rng.low)} … ${fmt(rng.high)}` : null));

  const max = Math.max(...r.ranking.map((x) => x.score), 1);
  blocks.push(foldedCard(h("div", { class: "card" }, h("h3", {}, t("investTitle")), h("div", { class: "sub" }, t("investSub")),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, t("colMod")), h("th", {}, t("colEffect")), h("th", { class: "num" }, t("colScore")))),
      h("tbody", {}, r.ranking.map((x) => h("tr", {}, h("td", { class: "mod", title: x.mod }, trMod(x.mod)),
        h("td", {}, deltas({ dps: x.dps, phys_hit: x.physHit, chaos_hit: x.chaosHit, recovery: x.recovery })),
        h("td", { class: "num" }, scoreBar(x.score, max))))))),
  "invest", r.ranking.length ? t("bestIs", trMod(r.ranking[0].mod)) : null));

  return [h("div", { class: "grid two" }, blocks)];
}

// ---------- gear ----------
TABS.gear = async (view) => {
  view.replaceChildren(loading(t("calcGear")));
  hideTip();
  const g = await DATA.gear();
  const items = gearMap(state.build.items);
  if (!state.gear || state.gear.build !== state.build.name) state.gear = { build: state.build.name, slot: null, set: 1 };
  const gs = state.gear;
  if (!gs.slot || !items[gs.slot]) gs.slot = ["Body Armour", "Weapon 1", "Helmet"].find((s) => items[s]) || Object.keys(items)[0] || null;

  // the item a step is about, as its picture: many slots, so the eye finds the right one at once
  const slotIcon = (slot) => { const it = items[slot]; return it ? itemIcon(it.name, it.baseName, it.rarity) : null; };
  const stepMax = Math.max(0.01, ...g.craftPath.map((s) => s.score));
  const path = foldedCard(h("div", { class: "card" }, h("h3", {}, t("craftTitle")), h("div", { class: "sub" }, t("craftSub")),
    g.craftPath.length ? h("div", { class: "steps" }, g.craftPath.map((s) => h("div", { class: "step" }, h("div", { class: "step-body" },
      h("div", { class: "what" }, slotIcon(s.slot), chip("tag", slotName(s.slot)), " ",
        s.removed.length ? h("span", {}, h("span", { class: "mod muted" }, trMod(s.removed.join(" / "))), " → ") : t("craftAdd"),
        h("span", { class: "mod" }, trMod(s.added.join(" / ")))),
      h("div", { class: "row step-worth" }, deltas(s.changes), scoreBar(s.score, stepMax)),
      howBlock(s.how))))) : h("p", { class: "muted" }, t("nothingToCraft"))),
  "craft", g.craftPath.length ? t("craftSum", g.craftPath.length, slotName(g.craftPath[0].slot)) : null);

  // a slot with something to improve: a better rune for one of its sockets or a step of the craft path
  const badges = {};
  for (const s of [...g.sockets.filter((x) => x.best.length), ...g.craftPath]) {
    badges[s.slot] = { cls: "better", sym: "▲", title: t("gearBadge") };
  }
  for (const id of Object.keys(AU.blocks)) {  // the author wrote about the slot
    const slot = id.startsWith("gear:") && id.slice(5);
    if (slot && !badges[slot]) badges[slot] = { cls: "author", sym: "✎", title: t("auHasNote") };
  }
  const dollBox = h("div", { class: "stack" }), side = h("div", { class: "stack" });
  const pick = (slot) => { gs.slot = slot; draw(); };
  const draw = () => {
    const swap = hasSwapSet(items);
    if (!swap && gs.set === 2) gs.set = 1;
    dollBox.replaceChildren(...[
      swap ? h("div", { class: "segmented", title: t("cmpWeapons") }, [1, 2].map((n) => h("button", { class: gs.set === n ? "active" : "",
        onclick: () => {
          gs.set = n;
          const pos = Object.keys(SWAP_SLOT).find((p) => p === gs.slot || SWAP_SLOT[p] === gs.slot);  // the picked weapon follows the set
          if (pos) gs.slot = n === 2 ? SWAP_SLOT[pos] : pos;
          draw();
        } }, n === 1 ? "⚔ I" : "⚔ II"))) : null,
      doll(items, { set: gs.set, selected: gs.slot, onPick: pick, badges, tip: modsTip }),
      h("div", { class: "muted small cmp-legend" }, t("gearPick")),
      gs.slot ? h("button", { class: "primary mk-btn", title: t("mkOpenHint"), onclick: () => itemEditor(gs.slot) },
        h("span", { class: "mk-ico" }, "✎"),
        h("span", {}, h("b", {}, t("mkBig")), h("span", { class: "mk-sub" }, t("mkBigSub", slotName(gs.slot))))) : null].filter(Boolean));
    drawSide();
  };

  let seq = 0;
  async function drawSide() {
    const slot = gs.slot, my = ++seq;
    const p = g.slots.find((x) => x.slot === slot);
    if (!slot) return;
    const note = auCard("gear:" + slot, t("auGearTitle", slotName(slot)), t("auGearPh"));
    if (!items[slot]) {
      side.replaceChildren(...[note].filter(Boolean), h("div", { class: "card stack" }, h("div", { class: "muted small" }, slotName(slot)), h("p", { class: "muted" }, t("slotEmpty")),
        h("button", { class: "primary mk-btn", onclick: () => itemEditor(slot) }, h("span", { class: "mk-ico" }, "✎"),
          h("span", {}, h("b", {}, t("mkBig")), h("span", { class: "mk-sub" }, t("mkBigSub", slotName(slot)))))));
      return;
    }
    const edit = h("div", { class: "card" }, loading(t("counting")));
    side.replaceChildren(...[note, edit, p ? slotCard(p) : null, adviceCard(slot)].filter(Boolean));
    try {
      const info = await api(`/api/gear/item?slot=${encodeURIComponent(slot)}&${buildQuery()}`);
      if (my === seq) gearEdit(edit, info, g);
    } catch (e) { if (my === seq) edit.replaceChildren(h("p", { class: "muted" }, e.message)); }
  }

  draw();
  return h("div", { class: "stack" }, h("div", { class: "gear-top" }, h("div", { class: "card" }, dollBox), side),
    path, uniquesCard(), craftGuide());
};

// The uniques linked to the build's skills, with their prices: for a levelling character the ones it can wear soon
// (the cheap ones for the start marked), on maps every one. Counted when the card is opened.
function uniquesCard() {
  const inner = h("div", { class: "stack" });
  const card = foldedCard(h("div", { class: "card" }, h("h3", {}, "💍 ", t("unTitle")), inner), "uniques", t("unFoldSum"));
  let loaded = false;
  const load = async (again) => {
    if (loaded && again !== true) return;
    loaded = true;
    inner.replaceChildren(loading(t("unLoading")));
    try {
      const r = await DATA.uniques();
      inner.replaceChildren(...renderUniqueLinks(r, () => load(true)));
    } catch (e) { inner.replaceChildren(h("p", { class: "muted" }, e.message)); }
  };
  whenOpen(card, load);
  return card;
}

// an item's mods when the pointer is over it: its lines only, as the game lists them
function modsTip(it) {
  const lines = [...it.enchant.map((l) => [l, "enchant"]), ...it.implicit.map((l) => [l, "implicit"]), ...it.runes.map((l) => [l, "rune"]),
    ...it.explicit.map((l) => [l, ""])];
  return h("div", { class: "stack" }, h("div", { class: "item-name tip-name r-" + (it.rarity || "normal").toLowerCase() }, itemTitle(it)),
    lines.length ? h("ul", { class: "item-lines small" }, lines.map(([l, cls]) => h("li", {
      class: [cls, l.crafted ? "crafted" : "", l.desecrated ? "desecrated" : "", l.fractured ? "fractured" : ""].filter(Boolean).join(" ") }, trMod(l.line))),
    it.corrupted ? h("li", { class: "corrupted" }, t("corrupted")) : null) : h("div", { class: "muted small" }, t("gearNoMods")));
}

// the analysis of one item: its mods by worth for the build, what to change, how to craft it, a replacement to buy
function slotCard(p) {
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
    craftBlock(p.slot), tradeBlock(p.slot));
}

// ---- an item of one's own choosing for a slot: made on a base as the game makes it, a unique or text copied from the
// game; tried on against the slot's item (the Compare tab's verdict), then worn as an edit of the plan ----
const MK_KIND = { Armour: "mkKind_ar", Evasion: "mkKind_ev", "Energy Shield": "mkKind_es", "Armour/Evasion": "mkKind_arev",
  "Armour/Energy Shield": "mkKind_ares", "Evasion/Energy Shield": "mkKind_eves", "Armour/Evasion/Energy Shield": "mkKind_all" };
const mkKind = (k) => (MK_KIND[k] ? t(MK_KIND[k]) : trName(k));

// What matters in a slot for this build (poe2lab.analysis.slotadvice): why (what the build is made of and what the
// slot pays for), each mod priced in a good item, the best items made of them against the worn one - each can be
// tried in the item window, crafted (the craft simulator) or looked up on the market - and what the build does not
// need there.
function adviceCard(slot) {
  const inner = h("div", { class: "stack" });
  const card = foldedCard(h("div", { class: "card" }, h("h3", {}, "🎯 ", t("saTitle", slotName(slot))), inner), "advice:" + slot,
    t("saSum"));
  const load = async () => {
    if (inner.dataset.loaded) return;
    inner.dataset.loaded = "1";
    inner.replaceChildren(loading(t("saLoading")));
    try {
      const a = await cached(`advice:${slot}`, () => api(`/api/gear/advice?slot=${encodeURIComponent(slot)}&${buildQuery()}`));
      inner.replaceChildren(...renderAdvice(a, slot));
    } catch (e) { inner.replaceChildren(errorCard(e)); }
  };
  whenOpen(card, load);
  return card;
}

const ELEMENTS = ["Fire", "Cold", "Lightning"];
// a stat a link starts or ends at: a damage type, a defence; PoB's own name otherwise
const linkStat = (k) => (["Physical", "Fire", "Cold", "Lightning", "Chaos"].includes(k) ? t("st_hit_" + k)
  : ["All", "Elemental", "Evasion", "Armour", "Deflection", "Life", "EnergyShield", "Mana", "Random"].includes(k) ? t("saStat_" + k)
  : k.includes("Or") ? k.split("Or").map(linkStat).join(t("saOr")) : k);
const sourceName = (x) => (x.kind === "item" || x.kind === "jewel" ? trItem(x.name.split(",")[0]) : trName(x.name));
const linkSource = (x) => `${sourceName(x)}${x.count > 1 ? ` ×${x.count}` : ""} ${fmt(x.value, 0)}%`;

// why, from the build itself: what the main skill's hit is made of, the links between stats (damage gained as
// another type, evasion granting deflection) and where each comes from, the defences; then what the slot pays for
// most, each with its reason - "the hit is mostly cold, and its cold comes from the staff's physical"
function adviceWhy(a, slot) {
  const f = a.facts;
  if (!f) return null;
  const hit = Object.entries(f.hit || {}).filter(([, v]) => v >= 1).sort((x, y) => y[1] - x[1]);
  const rows = [];
  if (hit.length) {
    rows.push(h("div", {}, "⚔ ", f.skill ? gemName(f.skill) : null, " ", t("saHits"), " ",
      hit.map(([k, v]) => h("span", { class: "chip tag", style: `border-color:${DMG_COLOR[k]}` }, `${t("st_hit_" + k)} ${fmt(v, 0)}%`))));
    // where each type comes from: a skill's description may not name it - the weapon, what items add, what is
    // gained as it, how much it is scaled
    const from = f.hitFrom || {};
    const range = (lo, hi) => `${fmt(lo, 0)}–${fmt(hi, 0)}`;
    const lines = hit.filter(([k]) => from[k]).map(([k, v]) => {
      const x = from[k];
      const parts = [];
      if (x.weapon) parts.push(`${t("saHitWeapon")} ${range(x.weapon.min, x.weapon.max)}`);
      for (const s of x.added) parts.push(`${sourceName(s)} ${range(s.min, s.max)}`);
      for (const l of (f.links || []).filter((l) => l.to === k || l.to.split("Or").includes(k))) {
        parts.push(`${l.how === "gain" ? t("saLinkGain", linkStat(l.from), fmt(l.value, 0), linkStat(k))
          : t("saLinkConvert", linkStat(l.from), fmt(l.value, 0), linkStat(k))} (${l.sources.map(linkSource).join(", ")})`);
      }
      parts.push(t("saHitScale", fmt(x.inc, 0), x.more > 1.005 ? fmt(x.more, 2) : null));
      return h("li", {}, h("b", { style: `color:${DMG_COLOR[k]}` }, `${t("st_hit_" + k)} ${fmt(v, 0)}%`), ": ", parts.join(" · "));
    });
    if (lines.length) rows.push(h("details", { class: "small" }, h("summary", {}, t("saHitFrom")), h("ul", { class: "sa-hit-from" }, lines)));
  }
  // links of one source and size together: "elemental → fire / cold / lightning 33%" (Painter's Servant)
  const links = {};
  for (const l of f.links || []) {
    const key = [l.from, l.how, Math.round(l.value), l.sources.map((x) => x.name).join("|")].join("/");
    (links[key] = links[key] || { ...l, tos: [] }).tos.push(l.to);
  }
  for (const l of Object.values(links).slice(0, 4)) {
    const to = l.tos.map(linkStat).join(" / ");
    rows.push(h("div", {}, "🔗 ", h("b", {}, l.how === "gain" ? t("saLinkGain", linkStat(l.from), fmt(l.value, 0), to)
      : t("saLinkConvert", linkStat(l.from), fmt(l.value, 0), to)), " ",
      h("span", { class: "muted small" }, "(", l.sources.map(linkSource).join(" · "), ")")));
  }
  const defs = Object.entries(f.defences || {}).sort((x, y) => y[1] - x[1]);
  if (defs.length) {
    rows.push(h("div", {}, "🛡 ", t("saDefence"), " ", defs.map(([k, v]) => `${t("exDefTitle_" + k)} ${fmt(v, 0)}`).join(" · "),
      f.deflection >= 1 ? ` · ${t("saStat_Deflection")} ${fmt(f.deflection, 0)}%` : ""));
  }
  // the reason of each kind of mod the slot pays for, from the facts above
  const share = (types) => types.reduce((s, k) => s + ((f.hit || {})[k] || 0), 0);
  const fromPhys = (f.links || []).filter((l) => ["All", "Physical"].includes(l.from) && ELEMENTS.includes(l.to))
    .reduce((s, l) => s + l.value, 0);
  const defLink = (stat) => (f.links || []).find((l) => l.from === stat);
  const biggest = defs.length ? defs[0][0] : null;
  const reason = (k) => {
    if (k === "phys") return fromPhys && share(["Physical"]) < 60 ? t("saWhy_physBase", fmt(fromPhys, 0)) : t("saWhy_share", t("st_hit_Physical"), fmt(share(["Physical"]), 0));
    if (k === "elemental") return t("saWhy_share", t("saStat_Elemental"), fmt(share(ELEMENTS), 0));
    if (k === "chaos") return t("saWhy_share", t("st_hit_Chaos"), fmt(share(["Chaos"]), 0));
    if (k === "crit") return t("saWhy_crit", fmt(f.crit, 0));
    if (k === "deflect") return f.deflection >= 1 ? t("saWhy_deflect", fmt(f.deflection, 0)) : "";
    if (k === "gems" || k === "speed") return t("saWhy_" + k);
    const stat = { evasion: "Evasion", armour: "Armour", es: "EnergyShield", life: "Life" }[k];
    if (stat && defLink(stat)) return t("saWhy_defLink", linkStat(defLink(stat).to), fmt(defLink(stat).value, 0));
    if (stat && stat === biggest) return t("saWhy_main");
    return "";
  };
  if (a.why && a.why.length) {
    rows.push(h("div", { class: "sa-why-slot" }, h("b", {}, "→ ", t("saConclusion", slotName(slot))),
      h("ul", {}, a.why.map((w) => h("li", {}, h("b", {}, t("saKind_" + w.kind)), " ", deltas({ dps: w.dps, ehp: w.ehp }, METRIC, 0.1),
        reason(w.kind) ? h("span", { class: "muted small" }, " — ", reason(w.kind)) : null)))));
  }
  return rows.length ? h("div", { class: "hint sa-why" }, h("div", { class: "small" }, h("b", {}, t(a.you ? "saWhyTitleGuide" : "saWhyTitle"))), ...rows) : null;
}

function renderAdvice(a, slot) {
  if (!a.base) return [h("p", { class: "muted" }, t("saNone"))];
  const metric = (x) => deltas({ dps: x.dps, ehp: x.ehp }, METRIC, 0.1);
  const out = [adviceWhy(a, slot)].filter(Boolean);
  out.push(h("div", { class: "small muted" }, t(a.inItem ? "saSubInItem" : "saSub", trName(a.base), a.itemLevel),
    a.forLevel ? " " + t(a.you ? "saForLevelGuide" : "saForLevel", a.forLevel) : ""));
  out.push(h("table", { class: "ex-table" }, h("tbody", {}, a.mods.slice(0, 10).map((m) => h("tr", {},
    h("td", { class: "mod" }, m.lines.map(trMod).join(" / "), " ", h("span", { class: "muted small" }, m.type === "Prefix" ? t("saPrefix") : t("saSuffix"))),
    h("td", { title: m.aloneDps !== undefined ? t("saAloneHint", fmt(m.aloneDps, 1), fmt(m.aloneEhp, 1)) : null }, metric(m)))))));
  for (const [mode, b] of Object.entries(a.best || {})) {
    const extra = h("div", {});
    const open = (btn, fill) => async () => {
      btn.disabled = true;
      extra.replaceChildren(loading(t(btn.dataset.wait)));
      try { extra.replaceChildren(await fill()); } catch (e) { extra.replaceChildren(h("p", { class: "bad small" }, e.message)); }
      finally { btn.disabled = false; }
    };
    const craftBtn = h("button", { class: "ghost small", "data-wait": "crLoading" }, t("saCraft"));
    craftBtn.onclick = open(craftBtn, async () => renderCraft(await cached(`advice-craft:${slot}:${mode}`,
      () => api(`/api/gear/advice/craft?slot=${encodeURIComponent(slot)}&mode=${mode}&${buildQuery()}`))));
    const marketBtn = h("button", { class: "ghost small", "data-wait": "saMarketSearching" }, t("saMarket"));
    marketBtn.onclick = open(marketBtn, async () => adviceMarket(await api("/api/gear/advice/market",
      { method: "POST", body: { slot, mode, status: tradeStatus() } })));
    // a character going toward its build: the item against what the character wears; a build alone: against its own
    const against = a.you ? h("span", {}, h("span", { class: "small muted" }, a.you.uniqueWorn ? t("saYouVsUnique") : t("saYouVsWorn")), " ", metric(b.you))
      : h("span", {}, h("span", { class: "small muted" }, a.uniqueWorn ? t("saVsUnique") : t("saVsWorn")), " ", metric(b));
    // the best a character of its level can make is weaker than what it wears: no swap to offer
    if (b.wornBetter) {
      out.push(h("div", { class: "sk-better worn-better" },
        h("div", {}, h("b", {}, mode === "damage" ? "⚔ " + t("saBestDamage") : "⚖ " + t("saBestBalanced")), " ", chip("ok", t("saWornBetter")), " ", against),
        h("div", { class: "small muted" }, t("saWornBetterHint", a.itemLevel))));
      continue;
    }
    out.push(h("div", { class: "sk-better" },
      h("div", {}, h("b", {}, mode === "damage" ? "⚔ " + t("saBestDamage") : "⚖ " + t("saBestBalanced")), " ", against),
      h("ul", { class: "item-lines small" }, b.lines.map((l) => h("li", {}, trMod(l)))),
      h("div", { class: "row" }, h("button", { class: "ghost small", onclick: () => itemEditor(slot, b.text) }, t("saTry")), craftBtn, marketBtn),
      extra));
  }
  if (a.play && a.play.length) out.push(h("div", { class: "hint" }, t("saPlay", a.play.map(trMod).join("; "))));
  if (a.useless && a.useless.length) out.push(h("details", {}, h("summary", { class: "small" }, t("saUseless", a.useless.length)),
    h("div", { class: "small muted" }, a.useless.map(trMod).join("; "))));
  return out;
}

// the market for an item like the best one: what the search asked for, the price of the cheapest finds, and each
// find put on the build by PoB (the ones better than the worn item first)
function adviceMarket(r) {
  const s = r.searches[0];
  if (!s) return h("p", { class: "muted small" }, t("saMarketNone"));
  const head = h("div", { class: "trade-head" }, h("span", { class: "muted small" }, t("trLeague", trName(r.league))), " ",
    s.url ? h("a", { href: s.url, target: "_blank", rel: "noopener" }, t("trOpen", s.total)) : null);
  const mods = h("div", { class: "trade-mods" }, s.mods.map((m) => h("span", { class: "chip tag", title: m.line }, tradeMin(m))));
  if (s.error) return h("div", { class: "trade-search" }, head, mods, h("p", { class: "bad small" }, s.error));
  if (!s.items.length) return h("div", { class: "trade-search" }, head, mods, h("p", { class: "muted small" }, t("saMarketNone")));
  const ex = s.items.map((it) => (it.price || {}).ex).filter((v) => v > 0).sort((x, y) => x - y);
  const good = s.items.filter((it) => it.better);
  const rest = s.items.filter((it) => !it.better);
  return h("div", { class: "trade-search" }, head, mods,
    s.relaxed ? h("div", { class: "muted small" }, t("trRelaxed", s.relaxed, s.mods.length)) : null,
    ex.length ? h("div", {}, "💰 ", h("b", {}, t("saMarketPrice", fmt(ex[0], 0), fmt(ex[ex.length - 1], 0))),
      h("span", { class: "muted small" }, " ", t("saMarketFound", s.items.length, s.total))) : null,
    good.length ? tradeList(good, true) : h("p", { class: "muted small" }, t("saMarketNoneBetter")),
    rest.length ? h("details", {}, h("summary", { class: "muted small" }, t("trRest", rest.length)), tradeList(rest, false)) : null);
}

async function itemEditor(slot, prefill = "") {
  let cat;
  try { cat = await api(`/api/gear/create?slot=${encodeURIComponent(slot)}&${buildQuery()}`); } catch (e) { toast(e.message); return; }
  if (!cat.bases.length && !cat.uniques.length) { toast(t("mkNothingFits", slotName(slot))); return; }
  const now = gearMap(state.build.items)[slot] || null;
  const ed = { tab: prefill ? "paste" : cat.bases.length ? "create" : "unique", base: null, fams: null, rarity: "rare", ilvl: cat.itemLevel,
    quality: 20, iroll: 0.5, slots: { Prefix: [], Suffix: [] }, unique: null, roll: 0.5, text: prefill, q: "", kind: "all", breakeven: "" };

  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) close(); } });
  const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } };
  // an item copied in the game (Ctrl+C on it, or "copy" at the trade market; Russian or English): Ctrl+V anywhere
  // in the window puts it into "paste text"
  const onPaste = (e) => {
    const text = (e.clipboardData && e.clipboardData.getData("text")) || "";
    if (!/^\s*(Item Class|Класс предмета|Rarity|Редкость):/m.test(text) || e.target.tagName === "TEXTAREA") return;
    e.preventDefault();
    ed.tab = "paste";
    ed.text = text;
    draw();
    refresh();
  };
  const close = () => { clearTimeout(timer); hideTip(); back.remove(); document.removeEventListener("keydown", onKey, true);
    document.removeEventListener("paste", onPaste, true); };
  document.addEventListener("paste", onPaste, true);
  const body = h("div", { class: "stack" }), preview = h("div", { class: "stack" });
  const put = h("button", { class: "primary", disabled: true, onclick: () => {
    const s = spec();
    close();
    planCall("/api/gear/equip", { slot, ...s }, { tab: "gear", rebuild: true });
  } }, t("mkWear"));

  const spec = () => {
    if (ed.tab === "unique") return ed.unique ? { unique: ed.unique.name, base: ed.unique.base, roll: ed.roll } : null;
    if (ed.tab === "paste") return ed.text.trim() ? { text: ed.text, breakeven: ed.breakeven.trim() || null } : null;
    if (!ed.base) return null;
    return { base: ed.base.name, rarity: ed.rarity, item_level: ed.ilvl, quality: ed.base.quality ? ed.quality : null,
      implicit_roll: ed.iroll, mods: [...ed.slots.Prefix, ...ed.slots.Suffix].filter(Boolean).map((m) => ({ id: m.id, roll: m.roll })) };
  };
  let seq = 0, timer = null;
  const refresh = () => { clearTimeout(timer); timer = setTimeout(runPreview, 300); };
  async function runPreview() {
    const s = spec(), my = ++seq;
    put.disabled = true;
    if (!s) { preview.replaceChildren(h("p", { class: "muted" }, t("mkPick"))); return; }
    preview.replaceChildren(loading(t("counting")));
    try {
      const r = await api("/api/gear/try", { method: "POST", body: { slot, ...s } });
      if (my !== seq) return;
      preview.replaceChildren(itemCard(r.item, now, t("mkResult"), "theirs"), verdictBlock(r, t(now ? "mkVsNow" : "mkVsEmpty")),
        r.skills && r.skills.length ? skillsWith(r.skills) : null);
      put.disabled = false;
    } catch (e) { if (my === seq) preview.replaceChildren(h("p", { class: "neg" }, e.message)); }
  }

  const slider = (value, on) => h("div", { class: "jw-roll", title: t("jwRollHint") }, t("jwRollLow"),
    h("input", { type: "range", min: 0, max: 100, value: Math.round(value * 100), oninput: (e) => on(Number(e.target.value) / 100) }),
    t("jwRollHigh"));
  const famKey = (f) => `${f.set}|${f.group}|${f.tiers[0].id}`;
  const rangeText = (lines) => lines.map(trMod).join(" / ");

  async function loadMods() {
    ed.fams = null;
    draw();
    try {
      const r = await api(`/api/gear/mods?slot=${encodeURIComponent(slot)}&base=${encodeURIComponent(ed.base.name)}&item_level=${ed.ilvl}`);
      ed.fams = r.families;
      // a pick whose tier the new item level does not roll moves to the best tier it does
      for (const side of ["Prefix", "Suffix"]) {
        ed.slots[side] = ed.slots[side].map((m) => {
          const f = m && ed.fams.find((x) => famKey(x) === m.key);
          if (!f) return null;
          const tier = f.tiers.find((x) => x.id === m.id);
          return tier && tier.open ? m : { ...m, id: (f.tiers.find((x) => x.open) || f.tiers[f.tiers.length - 1]).id };
        });
      }
    } catch (e) { toast(e.message); }
    draw(); refresh();
  }

  const basePicker = () => {
    const kinds = [...new Set(cat.bases.map((b) => b.subType || b.type))];
    const match = (b) => (ed.kind === "all" || (b.subType || b.type) === ed.kind)
      && (!ed.q || [b.name, trName(b.name)].join(" ").toLowerCase().includes(ed.q.toLowerCase()));
    const tile = (b) => hoverTip(h("button", { class: "rune-opt", onclick: () => { ed.base = b; ed.slots = { Prefix: [], Suffix: [] }; loadMods(); } },
      itemIcon(null, b.name, "normal") || h("span", { class: "rune-dot" }),
      h("span", { class: "rune-name" }, trName(b.name), b.level ? h("span", { class: "muted small" }, ` · ${t("mkLevel", b.level)}`) : null)),
    () => h("div", { class: "stack" }, h("b", {}, trName(b.name)), h("div", { class: "muted small" }, mkKind(b.subType || b.type)),
      b.implicit ? h("ul", { class: "item-lines small" }, b.implicit.split("\n").map((l) => h("li", { class: "implicit" }, trMod(l)))) : null));
    const grid = h("div", { class: "rune-grid" }, cat.bases.filter(match).map(tile));
    const q = h("input", { type: "search", placeholder: t("mkSearch"), value: ed.q,
      oninput: () => { ed.q = q.value; grid.replaceChildren(...cat.bases.filter(match).map(tile)); } });
    const seg = kinds.length > 1 ? h("select", { onchange: (e) => { ed.kind = e.target.value; draw(); } },
      h("option", { value: "all" }, t("mkAll")), kinds.map((k) => h("option", { value: k, selected: ed.kind === k }, mkKind(k)))) : null;
    return [h("b", {}, t("mkPickBase")), h("div", { class: "row" }, seg, q), grid];
  };

  const modSlot = (side, i) => {
    const cur = ed.slots[side][i] || null;
    const used = new Set([...ed.slots.Prefix, ...ed.slots.Suffix].filter((x) => x && x !== cur).map((x) => x.group));
    const fams = ed.fams.filter((f) => f.type === side && !used.has(f.group));
    const option = (f) => h("option", { value: famKey(f), selected: !!cur && cur.key === famKey(f) }, rangeText(f.tiers[0].lines));
    const desecrated = fams.filter((f) => f.set === "Desecrated");
    const famSel = h("select", { class: cur ? "" : "muted", onchange: () => {
      const f = fams.find((x) => famKey(x) === famSel.value);
      ed.slots[side][i] = f ? { key: famKey(f), group: f.group, id: (f.tiers.find((x) => x.open) || f.tiers[f.tiers.length - 1]).id,
        roll: cur ? cur.roll : 0.5 } : null;
      draw(); refresh();
    } }, h("option", { value: "" }, t("jwNoMod")),
    h("optgroup", { label: t("jwModsNormal") }, fams.filter((f) => f.set !== "Desecrated").map(option)),
    desecrated.length ? h("optgroup", { label: t("jwModsDesecrated") }, desecrated.map(option)) : null);
    if (!cur) return h("div", { class: "jw-slot" }, famSel);
    const fam = ed.fams.find((x) => famKey(x) === cur.key);
    const tierSel = h("select", { onchange: () => { cur.id = tierSel.value; draw(); refresh(); } },
      fam.tiers.map((x) => h("option", { value: x.id, selected: x.id === cur.id, disabled: !x.open },
        `T${x.tier} · ${rangeText(x.lines)} · ${t("mkFromLevel", x.level)}`)));
    return h("div", { class: "jw-slot" + (fam.set === "Desecrated" ? " desecrated" : "") }, famSel, tierSel,
      slider(cur.roll, (v) => { cur.roll = v; refresh(); }));
  };

  const drawCreate = () => {
    if (!ed.base) return basePicker();
    const b = ed.base;
    const head = h("div", { class: "cmp-item-head" }, itemIcon(null, b.name, "normal"),
      h("div", {}, h("div", { class: "item-name" }, trName(b.name)), h("div", { class: "muted small" }, mkKind(b.subType || b.type))),
      h("button", { class: "ghost small", style: "margin-left:auto", onclick: () => { ed.base = null; draw(); refresh(); } }, t("mkChangeBase")));
    const rarity = h("div", { class: "segmented" }, ["magic", "rare"].map((k) => h("button", { class: ed.rarity === k ? "active" : "",
      onclick: () => {
        ed.rarity = k;
        for (const side of ["Prefix", "Suffix"]) ed.slots[side] = ed.slots[side].slice(0, cat.limits[k][side === "Prefix" ? 0 : 1]);
        draw(); refresh();
      } }, t("jwRarity_" + k))));
    // an end-game item: 65-82 (every best tier rolls from 82, jewellery's too); a tier the level does not roll is shut
    const [lo, hi] = cat.itemLevels || [65, 82];
    const ilvlVal = h("span", { class: "q-val" }, String(ed.ilvl));
    const ilvl = h("input", { type: "range", min: lo, max: hi, value: ed.ilvl, title: t("mkItemLevelHint"),
      oninput: (e) => { ilvlVal.textContent = e.target.value; },
      onchange: (e) => { ed.ilvl = Number(e.target.value); loadMods(); } });
    const parts = [head, rarity, h("div", { class: "q-row", title: t("mkItemLevelHint") }, h("b", {}, t("mkItemLevel")), ilvlVal, ilvl)];
    if (b.quality) {
      const val = h("span", { class: "q-val" }, `${ed.quality}%`);
      parts.push(h("div", { class: "q-row" }, h("b", {}, t("gearQuality")), val,
        h("input", { type: "range", min: 0, max: cat.maxQuality, value: ed.quality,
          oninput: (e) => { ed.quality = Number(e.target.value); val.textContent = `${ed.quality}%`; refresh(); } })));
    }
    if (b.implicit) {
      parts.push(h("div", { class: "jw-slot" }, h("div", { class: "jw-side" }, t("mkImplicit")),
        h("ul", { class: "item-lines small" }, b.implicit.split("\n").map((l) => h("li", { class: "implicit" }, trMod(l)))),
        /\(/.test(b.implicit) ? slider(ed.iroll, (v) => { ed.iroll = v; refresh(); }) : null));
    }
    if (!ed.fams) return [...parts, loading(t("counting"))];
    const [np, ns] = cat.limits[ed.rarity];
    return [...parts,
      h("div", { class: "jw-side" }, t("jwPrefixes")), ...Array.from({ length: np }, (_, i) => modSlot("Prefix", i)),
      h("div", { class: "jw-side" }, t("jwSuffixes")), ...Array.from({ length: ns }, (_, i) => modSlot("Suffix", i))];
  };

  const drawUnique = () => {
    const match = (u) => !ed.q || [u.name, trName(u.name), trName(u.base)].join(" ").toLowerCase().includes(ed.q.toLowerCase());
    const cards = () => cat.uniques.filter(match).map((u) => hoverTip(h("button", {
      class: "jw-unique" + (ed.unique === u ? " sel" : ""), onclick: () => { ed.unique = u; draw(); refresh(); } },
    itemIcon(u.name, u.base, "unique"), h("div", {}, h("div", { class: "jw-uname" }, trItem(u.name)), h("div", { class: "muted small" }, trName(u.base)))),
    () => h("div", { class: "stack" }, h("b", { class: "jw-uname" }, trItem(u.name)),
      h("ul", { class: "item-lines small" }, u.lines.map((l) => h("li", {}, trMod(l)))))));
    const list = h("div", { class: "jw-uniques" }, cards());
    const q = h("input", { type: "search", placeholder: t("mkSearch"), value: ed.q, oninput: () => { ed.q = q.value; list.replaceChildren(...cards()); } });
    return [q, list, ed.unique && ed.unique.ranged ? slider(ed.roll, (v) => { ed.roll = v; refresh(); }) : null];
  };

  // an item copied from the game - or the worn one, to change its mods and see; how low a mod may roll and the
  // item still not lose (worth knowing when buying)
  const drawPaste = () => {
    const ta = h("textarea", { rows: 12, placeholder: t("mkPastePh"), spellcheck: "false", oninput: () => { ed.text = ta.value; refresh(); } }, ed.text);
    const current = now ? h("button", { class: "ghost small", title: t("cmpCurrentHint"), onclick: async () => {
      try { ed.text = ta.value = (await api(`/api/item/${encodeURIComponent(slot)}`)).text; refresh(); } catch (e) { toast(e.message); }
    } }, t("insertCurrent")) : null;
    const be = h("input", { type: "text", placeholder: t("breakevenPh"), value: ed.breakeven, style: "width:100%",
      oninput: () => { ed.breakeven = be.value; refresh(); } });
    return [ta, current ? h("div", { class: "row" }, current) : null,
      h("details", { open: !!ed.breakeven }, h("summary", {}, t("breakeven")), h("div", { class: "sub" }, t("breakevenHelp")), be)];
  };

  const tabs = () => h("div", { class: "segmented" }, [["create", t("jwCreate")], ["unique", t("jwUniques")], ["paste", t("jwPaste")]]
    .filter(([k]) => k !== "create" || cat.bases.length)
    .map(([k, label]) => h("button", { class: ed.tab === k ? "active" : "", onclick: () => { ed.tab = k; ed.q = ""; draw(); refresh(); } }, label)));
  const draw = () => body.replaceChildren(tabs(), ...(ed.tab === "create" ? drawCreate() : ed.tab === "unique" ? drawUnique() : drawPaste()).filter(Boolean));

  back.append(h("div", { class: "ask card stack jw-editor", role: "dialog", "aria-modal": "true" },
    h("div", { class: "jw-head" }, h("h3", {}, t("mkTitle", slotName(slot))),
      h("button", { class: "ghost small", title: t("cancel"), onclick: close }, "✕")),
    h("div", { class: "jw-main" }, body, h("div", { class: "jw-out stack" }, preview, h("div", { class: "row" }, put)))));
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
  draw();
  runPreview();
}

// the item's quality, rune sockets and runes, changed as the game allows (the server checks: /api/gear/preview):
// a draft previewed against the item as it is, applied as an edit of the plan
function gearEdit(box, info, g) {
  const d = { quality: info.quality, sockets: info.sockets, runes: [...info.runes], catalyst: info.catalyst, cq: info.catalystQuality,
    socket: null, kind: "all", q: "" };
  const best = {};  // socket -> the runes the build gains most from there (the Gear analysis), with what they give
  for (const s of g.sockets) if (s.slot === info.slot) best[s.index - 1] = Object.fromEntries(s.best.map((o) => [o.name, o]));
  const byName = Object.fromEntries(info.options.map((o) => [o.name, o]));
  const was = (i) => info.runes[i] || "None";
  const changed = () => d.quality !== info.quality || d.sockets !== info.sockets || d.runes.some((r, i) => r !== was(i))
    || d.catalyst !== info.catalyst || d.cq !== info.catalystQuality;
  const body = () => ({ slot: info.slot, quality: d.quality, sockets: d.sockets, runes: d.runes, catalyst: d.catalyst, catalyst_quality: d.cq });
  const controls = h("div", { class: "stack" }), out = h("div", { class: "stack" });
  let seq = 0, timer = null;
  const refresh = () => { clearTimeout(timer); timer = setTimeout(preview, 250); };
  const undo = () => {
    Object.assign(d, { quality: info.quality, sockets: info.sockets, runes: [...info.runes], catalyst: info.catalyst, cq: info.catalystQuality, socket: null });
    drawControls(); preview();
  };

  async function preview() {
    const my = ++seq;
    if (!changed()) { out.replaceChildren(); return; }
    out.replaceChildren(loading(t("counting")));
    try {
      const r = await api("/api/gear/preview", { method: "POST", body: body() });
      if (my !== seq) return;
      out.replaceChildren(h("div", {}, h("div", { class: "sub", style: "margin:0 0 4px" }, t("gearVsNow")), deltas(r.change, METRIC, 0.3)),
        h("details", {}, h("summary", { class: "small" }, t("gearNewMods")), modsTip(r.item)),
        h("div", { class: "row" }, h("button", { class: "primary", onclick: () => planCall("/api/gear/set", body(), { tab: "gear", rebuild: true }) }, t("gearApply")),
        h("button", { class: "ghost", onclick: undo }, t("gearUndo"))));
    } catch (e) {
      if (my === seq) out.replaceChildren(h("p", { class: "neg" }, e.message), h("button", { class: "ghost small", onclick: undo }, t("gearUndo")));
    }
  }

  const runeTip = (o, why, gain) => h("div", { class: "stack" },
    h("div", { class: "named" }, icon(o.name, "ico rune"), h("b", {}, trName(o.name))),
    o.lines.length ? h("ul", { class: "item-lines small" }, o.lines.map((l) => h("li", {}, trMod(l)))) : null,
    o.levelReq > 1 ? h("div", { class: "muted small" }, t("gearRuneLevel", o.levelReq)) : null,
    gain ? h("div", {}, h("div", { class: "muted small" }, t("gearRuneGives")), deltas(gain.changes, METRIC, 0.3),
      gain.price ? h("div", { class: "muted small" }, trFree(gain.price)) : null) : null,
    why ? h("div", { class: "neg small" }, t("gearRefused_" + why.code, why.class ? trName(why.class) : why.level)) : null);

  function runePicker() {
    const i = d.socket, rec = best[i] || {};
    const kindOf = (o) => (o.type === "Rune" || o.type === "SoulCore" ? o.type : "other");
    const others = d.runes.filter((_, j) => j !== i);
    const refused = (o) => o.refused || (o.limit === 1 && others.includes(o.name) ? { code: "limit" } : null);
    const match = (o) => (d.kind === "all" || kindOf(o) === d.kind)
      && (!d.q || [o.name, trName(o.name)].join(" ").toLowerCase().includes(d.q.toLowerCase()));
    const tile = (o) => {
      const why = refused(o);
      const el = h("button", { class: "rune-opt" + (why ? " refused" : "") + (d.runes[i] === o.name ? " sel" : ""), "aria-disabled": why ? "true" : null,
        onclick: () => {
          if (why) return;
          d.runes = d.runes.map((r, j) => (j === i ? o.name : r));
          drawControls(); refresh();
        } },
      icon(o.name, "ico rune"), h("span", { class: "rune-name" }, trName(o.name)), rec[o.name] ? h("span", { class: "star" }, "★") : null);
      return hoverTip(el, () => runeTip(o, why, rec[o.name]));
    };
    const list = () => info.options.filter(match)
      .sort((a, b) => (!!rec[b.name] - !!rec[a.name]) || (!!refused(a) - !!refused(b)) || trName(a.name).localeCompare(trName(b.name)))
      .map(tile);
    const grid = h("div", { class: "rune-grid" }, list());
    const q = h("input", { type: "search", placeholder: t("gearRuneSearch"), value: d.q, oninput: () => { d.q = q.value; grid.replaceChildren(...list()); } });
    const seg = h("div", { class: "segmented" }, [["all", t("gearKind_all")], ["Rune", t("gearKind_rune")], ["SoulCore", t("gearKind_core")],
      ["other", t("gearKind_other")]].map(([k, label]) => h("button", { class: d.kind === k ? "active" : "", onclick: () => { d.kind = k; drawControls(); } }, label)));
    return h("div", { class: "rune-picker stack" }, h("div", { class: "row" }, h("b", {}, t("gearRunesFor", i + 1)), seg, q), grid,
      Object.keys(rec).length ? h("div", { class: "muted small" }, t("gearBest")) : null);
  }

  // quality as buttons and a slider up to the item's maximum (40% on a Breach ring, 200% on some uniques)
  const qualityRow = (label, value, max, disabled, onSet) => {
    const val = h("span", { class: "q-val" }, `${value}%`);
    const qbtns = h("div", { class: "segmented" });
    const drawQ = (cur) => qbtns.replaceChildren(...[...new Set([0, 10, 20, 30, max])].filter((q) => q <= max).sort((a, b) => a - b)
      .map((q) => h("button", { class: cur === q ? "active" : "", disabled, onclick: () => set(q) }, `${q}%`)));
    const range = h("input", { type: "range", min: 0, max, value, disabled, oninput: (e) => set(Number(e.target.value)) });
    const set = (q) => { val.textContent = `${q}%`; range.value = q; drawQ(q); onSet(q); };
    drawQ(value);
    return h("div", { class: "q-row" }, h("b", {}, label), val, range, qbtns);
  };

  // a ring's or amulet's catalyst: the kind of mods it raises, by its quality
  const catalystBlock = () => {
    const tile = (c) => {
      const name = `${c.name} Catalyst`;
      const el = h("button", { class: "rune-opt" + (d.catalyst === c.name ? " sel" : "") + (info.corrupted ? " refused" : ""),
        "aria-disabled": info.corrupted ? "true" : null,
        onclick: () => {
          if (info.corrupted) return;
          d.catalyst = d.catalyst === c.name ? "" : c.name;
          d.cq = d.catalyst ? d.cq || Math.min(20, info.maxCatalystQuality) : 0;
          drawControls(); refresh();
        } },
      icon(name, "ico rune") || h("span", { class: "rune-dot" }), h("span", { class: "rune-name" }, trName(name)));
      return hoverTip(el, () => h("div", { class: "stack" }, h("b", {}, trName(name)), h("div", { class: "small" }, t("gearCatTip", t("gearCatKind_" + c.kind)))));
    };
    return [h("div", { class: "stack" }, h("div", { class: "row" }, h("b", {}, t("gearCatalyst")),
      h("span", { class: "muted small" }, d.catalyst ? t("gearCatNow", t("gearCatKind_" + info.catalysts.find((c) => c.name === d.catalyst).kind)) : t("gearNoCatalyst"))),
    h("div", { class: "rune-grid cat-grid" }, info.catalysts.map(tile))),
    d.catalyst ? qualityRow(t("gearCatalystQ"), d.cq, info.maxCatalystQuality, info.corrupted, (q) => { d.cq = q; refresh(); }) : null];
  };

  function drawControls() {
    const parts = [];
    if (info.hasQuality) parts.push(qualityRow(t("gearQuality"), d.quality, info.maxQuality, info.corrupted, (q) => { d.quality = q; refresh(); }));
    if (info.takesCatalyst) parts.push(...catalystBlock().filter(Boolean));
    if (info.socketLimit > 0) {
      const sock = (i) => {
        const name = d.runes[i] || "None";
        const el = h("button", { class: "rune-sock" + (d.socket === i ? " sel" : "") + (name !== was(i) ? " new" : ""),
          title: name === "None" ? t("gearSocketEmpty") : null, onclick: () => { d.socket = d.socket === i ? null : i; drawControls(); } },
        name !== "None" ? icon(name, "ico rune") || h("span", { class: "rune-dot" }) : null);
        return name === "None" ? el : hoverTip(el, () => runeTip(byName[name] || { name, lines: [] }, null, null));
      };
      const add = d.sockets < info.socketLimit && !info.corrupted ? h("button", { class: "rune-sock add", title: t("gearAddSocket"),
        onclick: () => { d.sockets += 1; d.runes = [...d.runes, "None"]; d.socket = d.sockets - 1; drawControls(); refresh(); } }, "+") : null;
      parts.push(h("div", { class: "q-row" }, h("b", {}, t("gearSockets", d.sockets, info.socketLimit)),
        h("div", { class: "rune-socks" }, ...Array.from({ length: d.sockets }, (_, i) => sock(i)), ...(add ? [add] : [])),
        d.socket === null && d.sockets ? h("span", { class: "muted small" }, t("gearSocketHint")) : null));
      if (d.socket !== null) parts.push(runePicker());
    } else {
      parts.push(h("div", { class: "muted small" }, t("gearNoSockets")));
    }
    if (info.corrupted) parts.push(h("div", {}, chip("must", t("gearCorrupted"))));
    controls.replaceChildren(...parts);
  }

  drawControls();
  box.replaceChildren(...[
    h("div", { class: "cmp-item-head" }, itemIcon(info.item.name, info.item.baseName, info.item.rarity),
      h("div", {}, h("div", { class: "muted small" }, slotName(info.slot)), h("div", { class: "item-name" }, itemTitle(info.item)))),
    controls, out].filter(Boolean));
}

// ---------- a replacement from the trade site: the key mods, then an item made for the build ----------
const tradeState = {};  // slot -> the last answer, kept while the build is open
const TRADE_CURRENCY = { exalted: "Exalted Orb", divine: "Divine Orb", chaos: "Chaos Orb", alch: "Orb of Alchemy",
  annul: "Orb of Annulment", regal: "Regal Orb", vaal: "Vaal Orb", aug: "Orb of Augmentation",
  transmute: "Orb of Transmutation", mirror: "Mirror of Kalandra" };
const tradeThreshold = () => {
  try { return Number(localStorage.getItem("poe2lab.tradeThreshold")) || 15; } catch (_) { return 15; }
};
// sellers: online now only (the player's choice), or also instant buyout listings
const tradeStatus = () => {
  try { return localStorage.getItem("poe2lab.tradeStatus") === "available" ? "available" : "online"; } catch (_) { return "online"; }
};

function tradeBlock(slot) {
  const box = h("div", { class: "trade" });
  const btn = h("button", { class: "ghost small", onclick: () => { btn.remove(); openTrade(box, slot); } }, t("trButton"));
  box.append(btn);
  if (tradeState[slot]) { btn.remove(); openTrade(box, slot); }
  return box;
}

function openTrade(box, slot) {
  const out = h("div", {});
  const threshold = h("input", { type: "number", min: 1, max: 200, value: tradeThreshold(), style: "width:56px",
    onchange: (e) => {
      const v = Math.max(1, Math.min(200, Number(e.target.value) || 15));
      try { localStorage.setItem("poe2lab.tradeThreshold", String(v)); } catch (_) { /* storage blocked */ }
      if (tradeState[slot]) show(tradeState[slot]);  // the verdicts move with the threshold, no new search
    } });
  const go = h("button", { class: "primary small", onclick: () => run() }, t("trSearch"));
  const note = h("div", { class: "muted small", style: "margin:-2px 0 8px" });
  const drawNote = () => note.replaceChildren(t(tradeStatus() === "online" ? "trNoteOnline" : "trNoteAvailable"), " ", t("trNote"));
  const status = h("select", { onchange: (e) => {
    try { localStorage.setItem("poe2lab.tradeStatus", e.target.value); } catch (_) { /* storage blocked */ }
    drawNote();
  } }, [["online", t("trStatusOnline")], ["available", t("trStatusAvailable")]].map(([v, label]) =>
    h("option", { value: v, selected: tradeStatus() === v }, label)));
  drawNote();
  box.replaceChildren(h("div", { class: "craft-head" }, h("b", {}, t("trTitle")), h("div", { class: "sub" }, t("trSub"))),
    h("div", { class: "row craft-controls" }, h("label", {}, t("trThreshold"), " ", threshold, " %"),
      h("label", {}, t("trSellers"), " ", status), go), note, out);

  async function run() {
    go.disabled = true;
    out.replaceChildren(loading(t("trSearching")));
    try {
      tradeState[slot] = await api("/api/trade/search", { method: "POST", body: { slot, mode: state.mode, threshold: 0, status: tradeStatus() } });
      show(tradeState[slot]);
    } catch (e) {
      out.replaceChildren(h("p", { class: "bad" }, e.message));
    } finally { go.disabled = false; }
  }

  function show(r) {
    const thr = tradeThreshold();
    const better = (it) => it.score !== null && it.score >= thr && !it.unmet.length;
    out.replaceChildren(h("div", { class: "muted small" }, t("trLeague", trName(r.league))),
      ...r.searches.map((s) => {
        const need = s.kind === "key" ? (s.relaxed || s.mods.length) : Math.min(s.mods.length, 5);
        const head = h("div", { class: "trade-head" },
          h("b", {}, s.kind === "key" ? t("trKey", s.mods.length) : t("trIdeal", need, s.mods.length)), " ",
          s.url ? h("a", { href: s.url, target: "_blank", rel: "noopener" }, t("trOpen", s.total)) : null);
        const mods = h("div", { class: "trade-mods" }, s.mods.map((m) => h("span", { class: "chip " + (m.must ? "hold" : "tag"),
          title: m.line }, tradeMin(m))));
        if (s.error) return h("div", { class: "trade-search" }, head, mods, h("p", { class: "bad small" }, s.error));
        if (!s.items.length) return h("div", { class: "trade-search" }, head, mods, h("p", { class: "muted small" }, t("trNothing")));
        const good = s.items.filter(better).sort((a, b) => ((a.price || {}).ex ?? 1e12) - ((b.price || {}).ex ?? 1e12));
        const rest = s.items.filter((it) => !better(it)).sort((a, b) => (b.score ?? -1e9) - (a.score ?? -1e9));
        return h("div", { class: "trade-search" }, head, mods, s.relaxed ? h("div", { class: "muted small" }, t("trRelaxed", s.relaxed, s.mods.length)) : null,
          good.length ? tradeList(good, true) : h("p", { class: "muted small" }, t("trNoneBetter", thr, s.items.length)),
          rest.length ? h("details", {}, h("summary", { class: "muted small" }, t("trRest", rest.length)), tradeList(rest, false)) : null);
      }));
  }
}

// "+40% to Chaos Resistance or more": the line with the least the search asks for (a "# to #" pair: its mean)
function tradeMin(m) {
  const min = String(Math.round(m.min * 10) / 10);
  const one = (m.line.match(/\d+(?:\.\d+)?/g) || []).length === 1;
  return one ? `${trMod(m.line.replace(/\d+(?:\.\d+)?/, min))} ${t("trAtLeast")}` : `${trMod(m.line)} (${t("trMean", min)})`;
}

// each find as a small block: what it is, how much better on the build, its mods, the price
function tradeList(items, good) {
  const priceCell = (p) => {
    if (!p) return h("span", { class: "muted" }, t("trNoPrice"));
    const name = TRADE_CURRENCY[p.currency];
    return h("span", { class: "trade-price" }, icon(name), h("b", {}, fmt(p.amount, p.amount % 1 ? 1 : 0)),
      h("span", {}, name ? trName(name) : p.currency),
      p.currency !== "exalted" && p.ex ? h("span", { class: "muted small" }, t("trAboutEx", fmt(p.ex, 0))) : null);
  };
  const copy = (text) => async () => {
    try { await navigator.clipboard.writeText(text); toast(t("trWhisperDone"), true); } catch (_) { toast(t("trWhisperFail")); }
  };
  return h("div", { class: "trade-list" }, items.map((it) => h("div", { class: "trade-item" + (good ? " good" : "") },
    h("div", { class: "trade-item-head" }, itemIcon(it.name, it.base, it.rarity),
      h("div", {}, hoverTip(h("b", { class: "pk-node" }, trName(it.base)), () => linesTip(itemIcon(it.name, it.base, it.rarity), trName(it.base),
        it.explicit.map((l) => h("li", { title: l }, trMod(l))))),
      h("div", { class: "muted small" }, t("trIlvl", it.ilvl), it.corrupted ? [" · ", t("corrupted")] : null)),
      it.error ? null : h("div", { class: "trade-score" }, h("b", { class: it.score > 0 ? "pos" : "neg" }, pct(it.score)),
        good ? h("div", {}, chip("ok", t("trBetter"))) : null,
        it.unmet.length ? h("div", {}, chip("must", t("trUnmet", it.unmet.join(", ")))) : null)),
    it.error ? h("div", { class: "bad small" }, it.error) : deltas(it.changes),
    h("div", { class: "trade-item-foot" }, priceCell(it.price),
      it.whisper ? h("button", { class: "ghost small", title: it.whisper, onclick: copy(it.whisper) }, t("trWhisper")) : null))));
}

// ---------- how to craft: the general principles, cheap to expensive ----------
// The same for armour, weapons and jewellery; the currency rules come from the game's own descriptions. Each step
// names its items in English ({0}, {1}...) for icons and translation; prices come live from poe.ninja.
const CRAFT_GUIDE = [
  ["cheap", [["g_bases", []], ["g_transmute", ["Orb of Transmutation", "Orb of Augmentation"]],
    ["g_regal", ["Regal Orb", "Exalted Orb", "Omen of Greater Exaltation"]], ["g_goal", []]]],
  ["essence", [["g_essence", ["Greater Essence of the Body"]], ["g_bone", ["Ancient Rib", "Omen of Abyssal Echoes"]]]],
  ["fracture", [["g_fracture", ["Fracturing Orb", "Ancient Rib"]], ["g_after_fracture", ["Chaos Orb", "Orb of Annulment"]],
    ["g_light", ["Orb of Annulment", "Omen of Light"]]]],
  ["expensive", [["g_perfect", ["Perfect Essence of the Body"]], ["g_grades", ["Greater Exalted Orb", "Perfect Exalted Orb"]],
    ["g_annul_side", ["Orb of Annulment", "Omen of Sinistral Annulment", "Omen of Dextral Annulment"]],
    ["g_homog", ["Omen of Homogenising Exaltation"]]]],
];

// "{0} and {1}": the placeholders become the items' pictures and names
const namedItem = (n) => hoverTip(h("span", { class: "named" }, icon(n), trName(n)), () => currencyTip(n));
// a currency's own description and directions (the game's), on hover over its name
let CURRENCY = {};
async function loadCurrency() {
  try { CURRENCY = await (await fetch("/api/currency")).json(); } catch (_) { CURRENCY = {}; }
}
function currencyTip(name) {
  const c = CURRENCY[name];
  if (!c) return null;
  const local = LANG !== "en";
  const how = (local && c.howLocal) || c.how;
  return h("div", { class: "currency-tip" }, h("b", {}, icon(name), " ", trName(name)),
    h("div", {}, (local && c.textLocal) || c.text), how ? h("div", { class: "muted small" }, how) : null);
}
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
  const sub = h("div", { class: "sub" }, t("crGuideSub"));
  const card = h("div", { class: "card craft-guide", "data-fold-default": "1" },
    h("h3", {}, t("crGuideTitle")), sub, levels,
    h("p", { class: "small" }, withItems(t("g_classes"), ["Gnawed Rib", "Gnawed Jawbone", "Gnawed Collarbone"])));
  cached("craftGuide", () => api("/api/craft/guide")).then((r) => {
    for (const [line, names] of priceLines) {
      const known = names.filter((n) => r.prices[n]);
      if (known.length) line.replaceChildren(t("g_prices"), " ", ...known.map((n) => h("span", { class: "guide-price" }, icon(n), trFree(r.prices[n]))));
    }
    sub.append(r.league ? t("prices", trName(r.league)) : "");
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
  // players craft items of level 65+ with perfect orbs all the way (league start aside): that is the default
  const gradeFor = (level) => (level >= 65 ? "perfect" : "");
  const st = craftState[slot] = craftState[slot] || { need: 3, grade: gradeFor(82), itemLevel: 82, quality: "good", main: true, mainMod: "" };
  const out = h("div", {});
  const select = (key, options) => h("select", { onchange: (e) => {
    st[key] = e.target.value;
    if (key === "grade") st.gradeChosen = true;
    run();
  } }, options.map(([v, label]) => h("option", { value: v, selected: String(st[key]) === String(v) }, label)));
  const ilvl = h("input", { type: "number", min: 1, max: 100, value: st.itemLevel, style: "width:64px",
    onchange: (e) => {
      st.itemLevel = Math.max(1, Math.min(100, Number(e.target.value) || 82));
      if (!st.gradeChosen && st.grade !== gradeFor(st.itemLevel)) { st.grade = gradeFor(st.itemLevel); openCraft(box, slot); return; }
      run();
    } });
  const controls = h("div", { class: "row craft-controls" },
    h("label", {}, t("crNeed"), " ", select("need", [1, 2, 3, 4, 5].map((n) => [n, t("crNeedN", n)]))),
    h("label", {}, t("crQuality"), " ", select("quality", [["good", t("crQualityGood")], ["top", t("crQualityTop")], ["any", t("crQualityAny")]])),
    h("label", {}, t("crGrade"), " ", select("grade", [["", t("crGradeNormal")], ["greater", t("crGradeGreater")], ["perfect", t("crGradePerfect")]])),
    h("label", {}, t("crIlvl"), " ", ilvl),
    // the craft revolves around the main mod (the first target): an item without it does not count
    h("label", { title: t("crMainHint") }, h("input", { type: "checkbox", checked: st.main !== false,
      onchange: (e) => { st.main = e.target.checked; run(); } }), " ", t("crMain")));
  box.replaceChildren(h("div", { class: "craft-head" }, h("b", {}, t("crTitle")), h("div", { class: "sub" }, t("crSub"))), controls,
    h("div", { class: "muted small", style: "margin:-2px 0 8px" }, t("crGradeHint")), out);

  async function run() {
    out.replaceChildren(loading(t("crLoading")));
    const q = `slot=${encodeURIComponent(slot)}&need=${st.need}&grade=${st.grade}&item_level=${st.itemLevel}&quality=${st.quality}&mode=${state.mode}&main=${st.main !== false ? 1 : 0}&main_mod=${encodeURIComponent(st.mainMod || "")}`;
    try {
      const r = await cached(`craft:${q}`, () => api(`/api/craft?${q}&${buildQuery()}`));
      out.replaceChildren(renderCraft(r, { mainMod: st.mainMod || "", onMain: (id) => { st.mainMod = id; if (id) st.main = true; openCraft(box, slot); } }));
    } catch (e) {
      out.replaceChildren(h("p", { class: "muted" }, e.message));
    }
  }
  run();
}

// the main mod to craft around, chosen among the mods the base rolls (the ones the build values first)
function craftMainPicker(r, opts) {
  if (!r.choices || !opts || !opts.onMain) return null;
  const label = (c) => `${c.side === "Prefix" ? t("prefix") : t("suffix")} · ${trMod(c.label)}${c.score ? ` (+${fmt(c.score, 1)})` : ""}`;
  return h("div", { class: "small" }, h("label", {}, t("crMainPick"), " ",
    h("select", { onchange: (e) => opts.onMain(e.target.value) },
      h("option", { value: "", selected: !opts.mainMod }, t("crMainAuto")),
      r.choices.map((c) => h("option", { value: c.id, selected: c.id === opts.mainMod }, label(c))))),
    r.mainMissing ? h("div", { class: "bad" }, t("crMainMissing")) : null);
}

// the desecration worth most for the build and how to get it: the bone with the side, the lord's and the echoes omens
function craftDesecration(r) {
  const d = r.desecration;
  if (!d) return null;
  const lordName = (l) => t("lord_" + l);
  const side = (x) => (x === "Prefix" ? t("prefix") : t("suffix"));
  if (!d.best) return h("div", { class: "small muted" }, h("b", {}, t("crDes")), " ", t("crDesNone"));
  const pct = (p) => `${fmt(p * 100, p < 0.1 ? 1 : 0)}%`;
  const money = (div) => (div === null || div === undefined ? "—"
    : div < 1 && r.exaltedPerDivine ? `${fmt(div * r.exaltedPerDivine, 0)} ex` : `${fmt(div, div < 10 ? 2 : 0)} div`);
  const items = (names) => names.map((n, i) => [i ? " + " : "", namedItem(n)]);
  const way = d.recommended !== null && d.recommended !== undefined ? d.ways[d.recommended] : null;
  return h("div", { class: "sk-item" },
    h("b", {}, t("crDes")),
    h("div", { class: "small" }, t("crDesBest", trMod(d.best.lines.join(" / ")), lordName(d.best.lord), side(d.best.side)),
      d.best.score ? h("span", { class: "muted" }, ` (+${fmt(d.best.score, 1)})`) : null),
    way ? h("div", { class: "small" }, t("crDesWay"), " ", items(way.n), " — ", h("b", {}, pct(way.chance)),
      way.expected !== null && way.expected !== undefined ? [" · ", t("crDesExpected"), " ", h("b", {}, money(way.expected))] : null) : null,
    d.lordOmens ? null : h("div", { class: "small muted" }, t("crDesNoLords")),
    h("details", {}, h("summary", { class: "small" }, t("crDesAll")),
      h("table", { class: "small" }, h("tbody", {}, d.ways.map((w, i) => h("tr", { class: i === d.recommended ? "best" : "" },
        h("td", {}, items(w.n)), h("td", { class: "num" }, pct(w.chance)),
        h("td", { class: "num muted" }, w.expected !== null && w.expected !== undefined ? money(w.expected) : "—"))))),
      h("div", { class: "small muted" }, t("crDesNote")),
      h("div", { class: "small" }, t("crDesOptions")),
      h("ul", { class: "small" }, d.options.map((o) => h("li", {}, `${lordName(o.lord)}, ${side(o.side)}: ${trMod(o.lines.join(" / "))}`,
        h("span", { class: "muted" }, o.score ? ` (+${fmt(o.score, 1)})` : ` (${t("crDesNoValue")})`))))));
}

function renderCraft(r, opts) {
  if (!r.targets.length) return h("div", {}, craftMainPicker(r, opts), h("p", { class: "muted" }, t("crNoTargets")));
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
    h("ul", { class: "craft-targets" }, r.targets.map((x, i) => h("li", {},
      chip("tag", x.side === "Prefix" ? t("prefix") : t("suffix")), " ", r.main && i === 0 ? [chip("must", t("crMainChip")), " "] : null,
      h("span", { class: "mod" }, trMod(x.label)),
      h("span", { class: "muted small" }, " " + t("crFromLevel", x.min_level))))));
  // a way that costs more than the budget (~100 div of currency until the item is done) is not how anyone crafts
  const budget = r.budget || 100;
  const tooDear = (s) => s.cost !== null && s.cost !== undefined && s.cost > budget;
  const working = r.strategies.filter((s) => s.per_base > 0 && !tooDear(s));
  const card = (s) => {
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
        r.exaltedPerDivine ? h("span", {}, t("crBasesCost"), " ", h("b", {}, `${money(s.bases * 10 / r.exaltedPerDivine)} – ${money(s.bases * 20 / r.exaltedPerDivine)}`)) : null,
        s.cost_per_base !== null && s.cost_per_base !== undefined ? h("span", {}, t("crPerBaseCost"), " ", h("b", {}, money(s.cost_per_base))) : null),
      h("ol", { class: "craft-steps" }, s.steps.map((x) => h("li", {}, stepText(x)))),
      h("details", {}, h("summary", {}, t("crUse")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th", {}), h("th", { class: "num" }, t("crColAvg")),
          h("th", { class: "num" }, t("crBadLuck")), h("th", { class: "num" }, t("crColPrice")))),
        h("tbody", {}, uses.map(([n, v]) => h("tr", {}, h("td", {}, named(n)),
          h("td", { class: "num" }, fmt(v, v < 10 ? 1 : 0)), h("td", { class: "num muted" }, fmt(s.p90[n], s.p90[n] < 10 ? 1 : 0)),
          h("td", { class: "num muted small" }, r.prices[n] ? trFree(r.prices[n]) : "—")))))));
  };
  const dear = r.strategies.filter(tooDear);
  return h("div", { class: "stack", style: "gap:10px" }, craftMainPicker(r, opts), targets,
    r.essence ? h("div", { class: "small" }, t("crEssence"), " ", named(r.essence)) : null,
    craftDesecration(r),
    h("div", { class: "craft-list" }, r.strategies.filter((s) => !tooDear(s)).map(card)),
    dear.length ? h("details", { class: "craft-dear" }, h("summary", {}, t("crExpensive", dear.length, money(budget))),
      h("div", { class: "craft-list" }, dear.map(card))) : null,
    h("div", { class: "note small muted" }, t(r.estimatedWeights ? "crWeightsNote" : "crWeightsReal") +
      (r.league ? " " + t("prices", trName(r.league)) : "")));
}

// ---------- compare: the inventory as in the game ----------
// Where the game's inventory has each slot: [column, row, width, height] in cells of an 8 x 6 grid; flasks and
// charms in a row below, as on the game's belt.
const DOLL = {
  "Weapon 1": [1, 1, 2, 4], "Helmet": [4, 1, 2, 2], "Amulet": [6, 2, 1, 1], "Weapon 2": [7, 1, 2, 4],
  "Ring 1": [3, 4, 1, 1], "Body Armour": [4, 3, 2, 3], "Ring 2": [6, 4, 1, 1],
  "Gloves": [1, 5, 2, 2], "Belt": [4, 6, 2, 1], "Boots": [7, 5, 2, 2],
};
const DOLL_BELT = ["Flask 1", "Charm 1", "Charm 2", "Charm 3", "Flask 2"];
const SWAP_SLOT = { "Weapon 1": "Weapon 1 Swap", "Weapon 2": "Weapon 2 Swap" };
// the slots the build comparison tries their items in (analysis/versus.py GEAR_SLOTS)
const VERSUS_SLOTS = ["Weapon 1", "Weapon 2", "Weapon 1 Swap", "Weapon 2 Swap", "Helmet", "Body Armour", "Gloves", "Boots",
  "Amulet", "Ring 1", "Ring 2", "Belt"];

// the open build as its file records it: the guide the player's character follows, or the gear before the plan's
// edits (the server's reference "@build")
const RECORDED_REF = "@build";
const recordedLabel = () => (state.build.main ? `${t("chGuide")} ${who(state.build.guide)}` : t("cmpRecorded"));

const gearMap = (items) => Object.fromEntries((items || []).map((i) => [i.slot, i]));
const hasSwapSet = (items) => !!(items && (items["Weapon 1 Swap"] || items["Weapon 2 Swap"]));
const itemArt = (it) => icon((it.name || "").split(",")[0].trim(), "doll-art") || icon(it.baseName, "doll-art");
// rares and uniques by their own name, magic and normal items by the base (affix names have several Russian
// variants); a rare's random name has no official translation, so in Russian it is shown by its base too
function itemTitle(it) {
  const [first, base] = (it.name || "").split(", ");
  if (LANG === "en") return base ? first : it.name;
  if (base) return GAME.names[first] || trName(it.baseName);
  return GAME.names[it.baseName] ? trName(it.baseName) : it.name;
}

// better / worse / mixed / same for the player, from a comparison (analysis/items.py Comparison)
function verdictOf(r) {
  if (r.dps_pct <= -99) return "no";  // a weapon the build's skills cannot use
  const hits = Object.values(r.hit_pct || {});
  const lo = Math.min(...hits), hi = Math.max(...hits);
  if (Math.abs(r.dps_pct) <= 0.5 && Math.abs(lo) <= 0.5 && Math.abs(hi) <= 0.5) return "same";
  if (r.dps_pct >= -0.5 && lo >= -0.5) return "better";
  if (r.dps_pct <= 0.5 && hi <= 0.5) return "worse";
  return "mixed";
}
const BADGE = { better: "▲", worse: "▼", mixed: "±", same: "=", no: "✕" };

// one inventory: each slot a cell with the item's picture framed by rarity; a click picks the slot
// badges: slot -> a comparison verdict ("better"...) or { cls, sym, title }; tip: (item, slot) -> the card shown on hover
function doll(items, { set, selected, onPick, badges, tip }) {
  const slotOf = (pos) => (set === 2 && SWAP_SLOT[pos]) || pos;
  const cell = (key, style, extra = "") => {
    const it = items[key];
    const b = badges && badges[key];
    const badge = !b ? null : typeof b === "string" ? h("span", { class: "doll-badge " + b, title: t("cmpBadge_" + b) }, BADGE[b])
      : h("span", { class: "doll-badge " + b.cls, title: b.title }, b.sym);
    const el = h("button", {
      class: `doll-slot${extra}` + (it ? " r-" + (it.rarity || "normal").toLowerCase() : " vacant") + (selected === key ? " sel" : ""),
      style, title: it && tip ? null : it ? `${slotName(key)}: ${itemTitle(it)}` : slotName(key), onclick: () => onPick(key),
    }, it ? (itemArt(it) || h("span", { class: "doll-name" }, itemTitle(it))) : h("span", { class: "doll-empty" }, slotName(key)), badge);
    return it && tip ? hoverTip(el, () => tip(it, key)) : el;
  };
  return h("div", { class: "doll-wrap" },
    h("div", { class: "doll" }, Object.entries(DOLL).map(([pos, [c, r, w, hh]]) =>
      cell(slotOf(pos), `grid-column:${c} / span ${w};grid-row:${r} / span ${hh}`))),
    h("div", { class: "doll-belt" }, DOLL_BELT.map((key) => cell(key, "", key.startsWith("Flask") ? " belt-flask" : " belt-charm"))));
}

// an item's mods, briefly; the lines the other item has no match for are marked: what you gain / what you lose
const modKey = (line) => line.toLowerCase().replace(/[+-]?\d+(\.\d+)?/g, "#").trim();
function itemCard(it, other, label, side) {
  if (!it) return h("div", { class: "item-card cmp-item" }, h("div", { class: "muted small" }, label), h("p", { class: "muted" }, t("slotEmpty")));
  const lines = (x) => [...x.enchant, ...x.implicit, ...x.runes, ...x.explicit];
  const theirs = new Set(other ? lines(other).map((l) => modKey(l.line)) : []);
  const row = (l, cls) => {
    const only = other && !theirs.has(modKey(l.line));
    return h("li", { class: [cls, l.crafted ? "crafted" : "", l.desecrated ? "desecrated" : "", l.fractured ? "fractured" : "",
      only ? (side === "mine" ? "lose" : "gain") : ""].filter(Boolean).join(" "),
    title: l.line + (only ? " — " + t(side === "mine" ? "cmpLose" : "cmpGain") : "") }, trMod(l.line));
  };
  const title = itemTitle(it), base = trName(it.baseName);
  const sub = [base !== title ? base : null, it.itemLevel ? t("cmpIlvl", it.itemLevel) : null,
    it.quality ? t("cmpQuality", it.quality) : null].filter(Boolean).join(" · ");
  return h("div", { class: "item-card cmp-item r-" + (it.rarity || "normal").toLowerCase() },
    h("div", { class: "muted small" }, label),
    h("div", { class: "cmp-item-head" }, itemIcon(it.name, it.baseName, it.rarity),
      h("div", {}, h("div", { class: "item-name", title: it.name }, title), sub ? h("div", { class: "muted small" }, sub) : null)),
    h("ul", { class: "item-lines" }, it.enchant.map((l) => row(l, "enchant")), it.implicit.map((l) => row(l, "implicit")),
      it.runes.map((l) => row(l, "rune")), it.explicit.map((l) => row(l, "")),
      it.corrupted ? h("li", { class: "corrupted" }, t("corrupted")) : null));
}

// what wearing the other item does: a verdict in words, the changes as chips, every number on demand
function verdictBlock(r, head) {
  const k = verdictOf(r);
  const hits = Object.values(r.hit_pct);
  const title = k === "no" ? t("wrongWeapon") : k === "mixed" ? t("vMixed", pct(r.dps_pct), pct(Math.min(...hits)), pct(Math.max(...hits)))
    : t({ better: "vBetter", worse: "vWorse", same: "vSame" }[k]);
  return h("div", { class: "stack" },
    h("div", { class: "verdict " + (k === "no" ? "worse" : k) }, h("span", { class: "verdict-head" }, head), title),
    deltas({ dps: r.dps_pct, phys_hit: r.hit_pct.Physical, fire_hit: r.hit_pct.Fire, cold_hit: r.hit_pct.Cold,
      lightning_hit: r.hit_pct.Lightning, chaos_hit: r.hit_pct.Chaos, recovery: r.recovery_pct }, METRIC, 0.5),
    Object.keys(r.unmet_requirements).length ? h("div", {}, Object.entries(r.unmet_requirements).map(([at, [have, need]]) =>
      chip("must", t("reqShort", attrName(at), fmt(have), fmt(need))))) : null,
    r.breakeven !== undefined ? h("p", {}, r.breakeven ? t("beOk", trMod(r.breakeven.line), fmt(r.breakeven.factor * 100)) : t("beBad")) : null,
    r.before ? h("details", {}, h("summary", {}, t("cmpAllNumbers")), numbersTable(r)) : null);
}

function numbersTable(r) {
  const b = r.before, a = r.after;
  const keys = ["dps", "life", "es", "ehp", "recovery", "hit_Physical", "hit_Fire", "hit_Cold", "hit_Lightning", "hit_Chaos",
    "res_Fire", "res_Cold", "res_Lightning", "res_Chaos"].filter((k) => b[k] || a[k]);
  return h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("now")),
    h("th", { class: "num" }, t("withCandidate")), h("th", { class: "num" }, t("change")))),
  h("tbody", {}, keys.map((k) => h("tr", {}, h("td", {}, t("st_" + k)), h("td", { class: "num" }, statText(k, b[k])),
    h("td", { class: "num" }, statText(k, a[k])), diffCell(k, a[k], b[k])))));
}

// the player's gear against the build's as recorded (RECORDED_REF), or a pasted item against the worn one
async function compareView() {
  if (!state.cmp || state.cmp.build !== state.build.name) {
    state.cmp = { build: state.build.name, slot: null, source: "build", ref: RECORDED_REF, set: 1 };
  }
  const cmp = state.cmp;
  cmp.ref = RECORDED_REF;
  const refLabel = recordedLabel();
  const mine = gearMap(state.build.items);
  let ref = null;     // the chosen build: who it is and its gear
  let versus = null;  // its items tried in my build, slot by slot, and the two builds' numbers (computed after)

  const myBox = h("div", {}), setBox = h("div", {}), right = h("div", { class: "stack" }), detail = h("div", {}), statsBox = h("div", {});
  const pick = (slot) => { cmp.slot = slot; drawDolls(); drawDetail(); };

  const drawDolls = () => {
    const swap = hasSwapSet(mine) || (cmp.source === "build" && ref && hasSwapSet(ref.items));
    if (!swap && cmp.set === 2) cmp.set = 1;
    setBox.replaceChildren(...(swap ? [h("div", { class: "segmented", title: t("cmpWeapons") }, [1, 2].map((n) =>
      h("button", { class: cmp.set === n ? "active" : "", onclick: () => {
        cmp.set = n;
        const pos = Object.keys(SWAP_SLOT).find((p) => p === cmp.slot || SWAP_SLOT[p] === cmp.slot);  // the picked weapon follows the set
        if (pos) cmp.slot = n === 2 ? SWAP_SLOT[pos] : pos;
        drawDolls(); drawDetail();
      } }, n === 1 ? "⚔ I" : "⚔ II")))] : []));
    myBox.replaceChildren(doll(mine, { set: cmp.set, selected: cmp.slot, onPick: pick }));
    if (cmp.source === "build") drawRef();
  };

  const refDoll = h("div", {});
  const drawRef = () => {
    if (!ref) return;
    const badges = {};
    for (const s of (versus && versus.slots) || []) {
      if (s.ref) badges[s.slot] = s.error ? "no" : s.swap ? verdictOf(s.swap) : null;
    }
    refDoll.replaceChildren(
      h("div", { class: "muted small" }, t("cmpRefInfo", trName(ref.ascendancy || ref.class), ref.level, trName(ref.skill))),
      doll(ref.items, { set: cmp.set, selected: cmp.slot, onPick: pick, badges }),
      versus ? h("div", { class: "muted small cmp-legend" }, t("cmpLegend")) : loading(t("cmpTrying")));
  };

  const drawRight = () => {
    right.replaceChildren(...[h("div", { class: "cmp-ref-title" }, h("b", {}, refLabel)),
      state.build.main ? null : h("div", { class: "sub" }, t("cmpRecordedSub")), refDoll].filter(Boolean));
  };

  const drawDetail = () => {
    const slot = cmp.slot;
    if (!slot) { detail.replaceChildren(h("div", { class: "card cmp-hint" }, t("cmpPick"))); return; }
    const my = mine[slot];
    let result = null, waiting = false, note = null;
    const label = refLabel;
    const other = ref && ref.items[slot];
    const empty = ref ? t("cmpRefEmpty", refLabel) : "";
    const s = versus && versus.slots.find((x) => x.slot === slot);
    if (other && VERSUS_SLOTS.includes(slot)) {
      if (!versus) waiting = true;
      else if (s && s.error) note = t("cannotEquip");
      else if (s && s.swap) result = s.swap;
    }
    detail.replaceChildren(h("div", { class: "card stack" },
      h("h3", {}, slotName(slot)),
      h("div", { class: "cmp-items" },
        itemCard(my, other, t("cmpWorn"), "mine"),
        other ? itemCard(other, my, label, "other") : h("div", { class: "item-card cmp-item" }, h("p", { class: "muted" }, empty))),
      my && other ? h("div", { class: "hint" }, t("cmpMarks")) : null,
      waiting ? loading(t("cmpTrying")) : null,
      note ? h("div", {}, chip("must", note)) : null,
      result ? verdictBlock(result, cmp.source === "build" ? t("cmpIfTheirs", label) : t("cmpIfPasted")) : null,
      /^(Flask|Charm)/.test(slot) && other ? h("div", { class: "hint" }, t("cmpFlaskHint")) : null));
  };

  const drawStats = () => {
    statsBox.replaceChildren(...(versus && ref ? [h("div", { class: "card" }, h("details", {},
      h("summary", {}, h("b", {}, t("cmpBuildStats", refLabel))), h("div", { class: "stack", style: "margin-top:10px" }, versusStats(versus, refLabel))))] : []));
  };

  const loadRef = async () => {
    ref = versus = null;
    statsBox.replaceChildren();
    const name = cmp.ref;
    if (!name) { drawDolls(); drawDetail(); return; }
    refDoll.replaceChildren(loading(t("refLoading")));
    try {
      const g = await cached("refgear:" + name, () => api(`/api/versus/gear?ref=${encodeURIComponent(name)}&${buildQuery()}`));
      if (cmp.ref !== name) return;
      ref = { ...g, items: gearMap(g.items) };
    } catch (e) { refDoll.replaceChildren(h("p", { class: "muted" }, e.message)); return; }
    drawDolls(); drawDetail();
    try {
      const v = await cached("versus:" + name, () => api(`/api/versus?ref=${encodeURIComponent(name)}&${buildQuery()}`));
      if (cmp.ref !== name) return;
      versus = v;
    } catch (e) { statsBox.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
    drawDolls(); drawDetail(); drawStats();
  };

  drawRight(); drawDolls(); drawDetail();
  if (cmp.source === "build") loadRef();
  return h("div", { class: "stack" },
    h("div", { class: "grid two cmp-top" },
      h("div", { class: "card stack" }, h("div", { class: "cmp-head" }, h("h3", {}, t("cmpMine")), setBox), myBox),
      h("div", { class: "card" }, right)),
    detail, statsBox);
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

// the two builds' numbers side by side, and mine with all of their gear at once
function versusStats(v, refName, groups = ["offence", "defence", "resist", "hits", "attributes", "other"]) {
  const rows = [];
  for (const g of groups) {
    const list = v.rows.filter((r) => r.group === g && !(r.mine === 0 && r.ref === 0));
    if (!list.length) continue;
    rows.push(h("tr", { class: "group" }, h("td", { colspan: 4 }, t("grp_" + g))));
    for (const r of list) rows.push(h("tr", {}, h("td", {}, t("st_" + r.key)),
      h("td", { class: "num" }, statText(r.key, r.mine)), h("td", { class: "num" }, statText(r.key, r.ref)),
      diffCell(r.key, r.mine, r.ref, r.higherBetter)));
  }
  const stats = h("div", {},
    h("div", { class: "sub" }, t("refStatsSub", trName(v.mineSkill), trName(v.refSkill))),
    v.mineSkill === v.refSkill ? null : h("div", { class: "action" }, t("refSkillDiffers")),
    h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("mine")),
      h("th", { class: "num" }, refName), h("th", { class: "num" }, t("diffMine")))), h("tbody", {}, rows)));
  let all = null;
  if (v.allGear) {
    const mine = Object.fromEntries(v.rows.map((r) => [r.key, r.mine]));
    const keys = ["dps", "life", "es", "ehp", "hit_Physical", "hit_Chaos", "res_Fire", "res_Cold", "res_Lightning", "res_Chaos", "spiritFree"]
      .filter((k) => mine[k] || v.allGear[k]);
    all = h("div", {}, h("h3", {}, t("refAllGear")), h("div", { class: "sub" }, t("refAllGearSub")),
      h("table", { class: "versus" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num" }, t("now")),
        h("th", { class: "num" }, t("withTheirGear")), h("th", { class: "num" }, t("change")))),
      h("tbody", {}, keys.map((k) => h("tr", {}, h("td", {}, t("st_" + k)), h("td", { class: "num" }, statText(k, mine[k])),
        h("td", { class: "num" }, statText(k, v.allGear[k])), diffCell(k, v.allGear[k], mine[k]))))));
  }
  return [stats, all].filter(Boolean);
}

// ---------- passive tree ----------
// how a node's topics meet the build's (damage, mechanics, defences, skills, weapons)
const fitChips = (f) => (f && (f.fits.length || f.misses.length) ? h("div", { class: "fit-chips" },
  f.fits.map((k) => chip("ok", "✓ " + t("topic_" + k))), f.misses.map((k) => chip("warn", t("topicMissing", t("topic_" + k))))) : null);

TABS.tree = async (view) => {
  view.replaceChildren(loading(t("treeLoading")));
  const points = state.treePoints || 6;
  const [r, graph, asc, jw] = await Promise.all([
    DATA.tree(),
    treeGraph(),
    ascData().catch((e) => ({ error: e.message })),
    DATA.jewels().catch((e) => ({ error: e.message }))]);
  const pointsSel = h("select", { onchange: (e) => { state.treePoints = Number(e.target.value); switchTab("tree"); } },
    [3, 4, 5, 6, 8, 10].map((n) => h("option", { value: n, selected: n === points }, t("upToPoints", n))));
  // a node's name; the pointer over it shows its lines, the road to it and how much of the value is its own
  const nodeName = (n) => hoverTip(h("span", { class: "named pk-node" }, icon(n.name, "ico passive"), trName(n.name)),
    () => h("div", { class: "stack" }, h("div", { class: "row", style: "gap:8px;align-items:center" }, icon(n.name, "ico passive"), h("b", {}, trName(n.name))),
      stats(n.stats),
      n.via && n.via.length ? h("div", { class: "hint" }, t("via", [...new Set(n.via.map(trName))].join(", "))) : null,
      n.with && n.with.length ? h("div", { class: "hint" }, t("alongWithShort", n.with.length)) : null,
      n.ownShare !== undefined && n.via && n.via.length ? h("div", { class: "muted small" }, t("treeOwnShare", Math.round(Math.min(1, Math.max(0, n.ownShare)) * 100))) : null));
  const typeChip = (type) => type === "Keystone" ? chip("tag", t("keystone")) : type === "Notable" ? chip("warn", t("notable")) : null;
  const maxValue = Math.max(0.01, ...r.growth.map((g) => g.perPoint));

  // each mechanic's best notables taken together: computed apart (a few seconds), the tab does not wait for them
  let packs = null;
  const viewTree = (focus) => {
    try { openTreeViewer(graph, r, asc.error ? null : asc, { packages: packs ? packs.packages : [], focus }); } catch (e) { toast(e.message); }
  };
  // the tree map itself at the top of the tab; after an edit on it the advice below is from before - recount on demand
  const stale = h("div", { class: "action hidden tv-stale" }, t("tvEditedNote"), " ",
    h("button", { class: "primary small", onclick: () => { resetCache(); switchTab("tree"); } }, t("tvRecount")));
  const mapBox = h("div", { class: "tree-embed-box" });
  try {
    openTreeViewer(graph, r, asc.error ? null : asc, { embed: mapBox, onEdit: () => stale.classList.remove("hidden") });
  } catch (e) { mapBox.append(h("p", { class: "muted" }, e.message)); }
  const packsHead = h("h3", {}, t("pkTitle"));
  const packsBody = h("div", {}, loading(t("pkLoading")));
  const packsCard = foldedCard(h("div", { class: "card" }, packsHead, packsBody), "packages", null);
  DATA.packages().then((p) => {
    packs = p;
    const best = p.packages[0];
    if (best) packsHead.append(h("span", { class: "fold-sum" }, t("pkSum", p.packages.length, packageName(best), pct(best.changes.dps || 0))));
    packsBody.replaceChildren(...[...packageCard(p, graph, viewTree).childNodes].slice(1));  // its own heading is packsHead
  }).catch((e) => packsBody.replaceChildren(h("p", { class: "muted" }, e.message)));
  const growth = h("div", { class: "card" }, h("h3", {}, t("treeGrowth")),
    h("div", { class: "sub" }, t("treeGrowthSub", t("mode_" + state.mode))),
    r.buildTopics && r.buildTopics.length ? h("div", { class: "small", style: "margin-bottom:8px" }, t("treeBuildTopics"), " ",
      r.buildTopics.map((k) => t("topic_" + k)).join(", ")) : null,
    h("label", { class: "field", style: "max-width:220px;margin-bottom:10px" }, h("span", {}, t("reach")), pointsSel),
    r.growth.length ? h("table", { class: "versus-items" },
      h("thead", {}, h("tr", {}, h("th", {}, t("node")), h("th", { class: "num" }, t("points")), h("th", {}, t("perPoint")), h("th", {}, t("treeGives")), h("th", {}, ""))),
      h("tbody", {}, r.growth.map((g) => h("tr", { class: "dense" },
        h("td", {}, h("div", {}, nodeName(g), " ", typeChip(g.type)), fitChips(g.fit), resourcesMoved(g.resources)),
        h("td", { class: "num" }, g.points),
        h("td", {}, scoreBar(g.perPoint, maxValue)),
        h("td", {}, deltas(g.changes, METRIC, 0.3)),
        h("td", {}, editButton("add", g))))))
      : h("p", { class: "muted" }, t("treeNothing")));

  // notables worth nothing by themselves (only the road pays): on the build's topics but outside PoB's model -
  // worth a look; or asking for what the build lacks - not for it
  const roadRow = (g) => h("tr", { class: "dense" },
    h("td", {}, h("div", {}, nodeName(g), " ", typeChip(g.type)), fitChips(g.fit)),
    h("td", { class: "num" }, g.points),
    h("td", {}, editButton("add", g)));
  const onBuild = (r.roadOnly || []).filter((g) => g.verdict !== "offBuild");
  const offBuild = (r.roadOnly || []).filter((g) => g.verdict === "offBuild");
  const roadOnly = h("div", { class: "stack" },
    onBuild.length ? h("div", { class: "card" }, h("h3", {}, t("treeOnBuild")), h("div", { class: "sub" }, t("treeOnBuildSub")),
      h("table", { class: "versus-items" }, h("tbody", {}, onBuild.map(roadRow)))) : null,
    offBuild.length ? h("div", { class: "card" }, h("h3", {}, t("treeOffBuild")), h("div", { class: "sub" }, t("treeOffBuildSub")),
      h("table", { class: "versus-items" }, h("tbody", {}, offBuild.map(roadRow)))) : null);

  // the other nodes that go with a branch (only reachable through it): they explain uneven numbers
  const alongWith = (names) => {
    if (!names || !names.length) return null;
    const counts = {};
    names.forEach((n) => { counts[n] = (counts[n] || 0) + 1; });
    return h("div", { class: "hint" }, t("alongWith", Object.entries(counts)
      .map(([n, c]) => (c > 1 ? `${c}× ${trName(n)}` : trName(n))).join(", ")));
  };
  const branchRow = (b) => h("tr", { class: "dense" },
    h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type)), alongWith(b.with)),
    h("td", { class: "num" }, b.points), h("td", {}, deltas(b.changes, METRIC, 0.3)), h("td", {}, editButton("remove", b)));
  const respec = h("div", { class: "card" }, h("h3", {}, t("treeRespec")), h("div", { class: "sub" }, t("treeRespecSub")),
    r.respec.length ? h("table", { class: "versus-items" },
      h("thead", {}, h("tr", {}, h("th", {}, t("branch")), h("th", { class: "num" }, t("freed")), h("th", {}, t("youLose")), h("th", {}, ""))),
      h("tbody", {}, r.respec.map(branchRow)))
      : h("p", { class: "muted" }, t("treeNoRespec")));

  const listCard = (title, sub, list) => list.length ? h("div", { class: "card" },
    h("details", {}, h("summary", {}, `${title} (${list.length})`), h("div", { class: "sub", style: "margin-top:8px" }, sub),
      h("table", { class: "versus-items" }, h("tbody", {}, list.map((b) => h("tr", {},
        h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type))), h("td", { class: "num" }, t("pointsN", b.points)),
        h("td", {}, editButton("remove", b)))))))) : null;

  const best = r.growth[0];
  const filled = jw.error ? 0 : jw.sockets.filter((s) => s.item).length;
  const lvTree = auBlock("tree:leveling").list;
  return h("div", { class: "stack" },
    mapBox, stale,
    auCard("tree:about", t("auTreeTitle"), t("auTreePh")),
    AU.edit || lvTree ? h("div", { class: "card au-card" }, h("h3", {}, I("pencil", "c-gold"), " ", t("auTreeLv")),
      h("div", { class: "sub" }, t("auTreeLvSub")), h("div", { class: "lr-sec-v au-tree-lv" }, ...auList("tree:leveling", [], [], ["passive"]))) : null,
    planCard(r.plan, r.points),
    asc.error ? h("div", { class: "card" }, h("p", { class: "muted" }, asc.error))
      : foldedCard(ascendancyCard(asc, graph), "ascendancy", asc.ascendancy ? t("tvAscPoints", asc.points, asc.maxPoints) : null),
    jw.error ? h("div", { class: "card" }, h("p", { class: "muted" }, jw.error)) : foldedCard(jewelCard(jw), "jewels", t("jwSum", filled, jw.sockets.length)),
    packsCard,
    foldedCard(growth, "growth", best ? t("treeGrowthSum", trName(best.name), fmt(best.perPoint, 1)) : null),
    ...[...roadOnly.children].map((c, i) => foldedCard(c, "road" + i, t("pointsListN", c.querySelectorAll("tbody tr").length))),
    foldedCard(respec, "respec", r.respec.length ? t("respecSum", r.respec.length) : null), takenCard(graph),
    listCard(t("treeUnseen"), t("treeUnseenSub"), r.unseen),
    listCard(t("treeAttributes"), t("treeAttributesSub"), r.attributes));
};

// a mechanic's package: its notables, what they give together (and how that differs from one by one), what the
// mechanic gives the build now; shown on the tree or taken at once
const packageName = (pk) => t("pk_" + pk.mechanic);
function packageCard(p, graph, viewTree) {
  const best = Math.max(0.01, ...p.packages.map((pk) => pk.perPoint));
  // a notable's name; the pointer over it shows what it gives
  const nodeName = (n) => hoverTip(h("span", { class: "named pk-node" }, icon(n.name, "ico passive"), trName(n.name)),
    () => h("div", { class: "stack" },
      h("div", { class: "row", style: "gap:8px;align-items:center" }, icon(n.name, "ico passive"), h("b", {}, trName(n.name))),
      h("div", { class: "muted small" }, n.type === "Keystone" ? t("keystone") : t("notable"), " · ", t("pkNodeRoad", n.points)),
      stats(n.stats)));
  const row = (pk) => h("div", { class: "pk-row" + (pk.yours ? " yours" : "") },
    h("div", { class: "pk-head" }, h("b", {}, packageName(pk)), pk.yours ? chip("ok", t("pkYours")) : chip("tag", t("pkOther")),
      h("span", { class: "muted small" }, t("pointsN", pk.points)), scoreBar(pk.perPoint, best)),
    h("div", { class: "pk-nodes" }, pk.notables.map((n, i) => [i ? h("span", { class: "muted" }, " + ") : null, nodeName(n)])),
    h("div", {}, deltas(pk.changes, METRIC, 0.3)), resourcesMoved(pk.resources),
    pk.synergy >= 0.1 ? h("div", { class: "small pos" }, t("pkTogetherMore", Math.round(pk.synergy * 100)))
      : pk.synergy <= -0.1 ? h("div", { class: "small warn-text" }, t("pkTogetherLess", Math.round(-pk.synergy * 100))) : null,
    pk.now ? h("div", { class: "small" }, h("span", { class: "muted" }, t("pkNow", packageName(pk)), " "), deltas(pk.now, METRIC, 0.3)) : null,
    h("div", { class: "row" },
      h("button", { class: "ghost small", title: t("pkShowHint"), onclick: () => viewTree(pk) }, t("pkShow")),
      h("button", { class: "ghost small", title: t("pkTakeHint"), onclick: () => takePackage(pk) }, t("pkTake"))));
  return h("div", { class: "card" }, h("h3", {}, t("pkTitle")), h("div", { class: "sub" }, t("pkSub")),
    resourcesLine(p.resources),
    p.buildMechanics.length ? h("div", { class: "small", style: "margin-bottom:8px" }, t("pkBuildHas"), " ",
      p.buildMechanics.map((k) => t("pk_" + k)).join(", ")) : null,
    p.packages.length ? h("div", { class: "pk-list" }, p.packages.map(row)) : h("p", { class: "muted" }, t("pkNone")));
}
// Rage and charges as the fight is played out (poe2lab.analysis.resources): the level the tree's prices use
function resourcesLine(r) {
  const levels = r && r.levels ? Object.entries(r.levels) : [];
  if (!levels.length) return null;
  const one = ([k, v]) => h("span", { class: "res-chip" }, h("b", {}, t("pk_" + k)), " ",
    t("resLevel", fmt(v.level, 1), fmt(v.max)), v.fullAfter != null ? h("span", { class: "muted" }, " · " + t("resFull", fmt(v.fullAfter, 1))) : null);
  return h("div", { class: "res-line", title: t(r.scenario === "boss" ? "resHintBoss" : "resHintMap") },
    h("span", { class: "muted small" }, t("resTitle")), ...levels.map(one), h("span", { class: "muted small" }, "ⓘ"));
}
// what a node or a package does to Rage and charges: "Rage 63 → 64"
const resourcesMoved = (m) => (m ? h("div", { class: "fit-chips" }, Object.entries(m).map(([k, [a, b]]) =>
  chip(b > a ? "ok" : "warn", t("resMoved", t("pk_" + k), fmt(a, 1), fmt(b, 1))))) : null);

// the notables nearest first: each road starts from the tree as it is after the one before
// `send(body)`: the request (from the tab or the viewer), its answer back; a trade that does not pay is asked about
async function packageFlow(pk, send) {
  const name = packageName(pk);
  const body = { ids: [...pk.notables].sort((a, b) => a.points - b.points).map((n) => n.id), mechanic: pk.mechanic, mode: state.mode };
  const done = (r) => {
    toast(r.removed.length ? t("pkTraded", name, r.removed.length) : t("pkTaken", name), true);
    return r;
  };
  const r = await send(body);
  if (!r) return null;
  if (r.kept) return done(r);
  const why = h("div", { class: "stack" }, h("div", {}, r.fits ? t("pkNotWorth", name) : t("pkNoRoom", name)),
    r.removed.length ? h("div", { class: "small" }, t("pkWouldDrop", r.removed.length), " ",
      h("span", { class: "muted" }, [...new Set(r.removed.map(trName))].slice(0, 8).join(", "))) : null,
    h("div", {}, h("span", { class: "muted small" }, t("pkWouldGive"), " "), deltas(r.changes, METRIC, 0.3)));
  if (!(await confirmInPage(why, t("pkTakeAnyway")))) return null;
  const f = await send({ ...body, force: true });
  return f && f.kept ? done(f) : null;
}
const takePackage = (pk) => packageFlow(pk, (body) => planCall("/api/tree/package", body, { busy: t("pkTaking") }));

// ---- tree plan: edits live in the engine only; every tab computes with them until reset ----
// an edit of the plan from any tab, then the tab again; `rebuild`: the build's gear and gems are read anew (the header,
// the inventory)
async function planCall(path, body, { busy, tab = "tree", rebuild = false } = {}) {
  const view = $("#view");
  hideTip();
  view.replaceChildren(loading(busy || t("counting")));
  try {
    const r = await api(path, { method: "POST", body: body || {} });
    resetCache();
    if (rebuild) await refreshBuild();
    await switchTab(tab);
    return r;
  } catch (e) { toast(e.message); switchTab(tab); return null; }
}
const treeCall = (path, body, busyText) => planCall(path, body, { busy: busyText, rebuild: path === "/api/tree/reset" });

async function refreshBuild() {
  try {
    state.build = await api("/api/build");
    renderHeader();
  } catch (e) { toast(e.message); }
}

async function savePlan() {
  try {
    const r = await api("/api/tree/save", { method: "POST", body: {} });
    toast(t("planSaved", r.name), true);
    loadBuildList();
  } catch (e) { toast(e.message); }
}

// the plan in one line on the tabs that edit it besides the tree: how many edits, what they change, reset / save
// ---- the plan's edits (tree, gems, gear, jewels): one strip under the tabs, on every tab - how many, what they
// change against the build, what exactly, and save / reset ----
async function renderPlanStrip() {
  const strip = $("#plan-strip");
  let plan = null;
  try { plan = await cached("plan", () => api(`/api/plan?${buildQuery()}`)); } catch (_) { /* no build open */ }
  if (!plan || !plan.log.length) { strip.classList.add("hidden"); strip.replaceChildren(); return; }
  // into the build itself: a build the constructor made, or the player's own character in a guide
  const into = ctorOf(state.build) || state.build.main;
  strip.replaceChildren(
    h("b", {}, "✎ ", t("planBarTitle", plan.log.length)), deltas(plan.changes, METRIC, 0.3),
    h("details", { class: "plan-strip-log" }, h("summary", {}, t("planWhat")), h("ul", { class: "plan-log" }, plan.log.map(planLogLine))),
    h("div", { class: "row plan-strip-act" },
      into ? h("button", { class: "primary small", title: t(state.build.main ? "svCommitMainHint" : "svCommitHint"), onclick: commitBuild },
        state.build.main ? t("svCommitMain") : t("svCommit")) : null,
      h("button", { class: "ghost small", onclick: savePlan }, t("planSave")),
      h("button", { class: "ghost small", onclick: () => planCall("/api/tree/reset", {}, { tab: state.tab, rebuild: true }) }, t("planReset"))));
  strip.classList.remove("hidden");
}

// one line of the plan's log: what an edit took and gave
const planNames = (list) => {
  const counts = {};
  (list || []).forEach((n) => { counts[n] = (counts[n] || 0) + 1; });
  return Object.entries(counts).map(([n, c]) => (c > 1 ? `${c}× ${trName(n)}` : trName(n))).join(", ");
};
function planLogLine(e) {
  const names = planNames;
  return e.action === "jewel"
    ? h("li", {}, t("jwLogAt", trName(e.target)), " ", e.removed ? h("span", { class: "neg" }, `− ${jwName(e.removed)}`) : null,
      e.removed && e.added ? " " : null, e.added ? h("span", { class: "pos" }, `+ ${jwName(e.added)}`) : null)
    : e.action === "item" && "worn" in e
    ? h("li", {}, t("gearLog", slotName(e.target)), " ", e.worn ? h("span", { class: "neg" }, `− ${jwName(e.worn)}`) : null, " ",
      h("span", { class: "pos" }, `+ ${jwName(e.item)}`))
    : e.action === "item"
    ? h("li", {}, t("gearLog", slotName(e.target)), " ", [e.quality ? t("gearLogQ", ...e.quality) : null,
      e.sockets ? t("gearLogS", ...e.sockets) : null,
      e.catalyst ? t("gearLogC", e.catalyst[0] ? trName(`${e.catalyst[0]} Catalyst`) : t("gearNoCatalyst"), e.catalyst[1]) : null,
      ...(e.added || []).map((n) => "+ " + trName(n))].filter(Boolean).join(", "))
    : e.action === "gem"
    ? h("li", {}, t("gmLogAt", trName(e.target)), " ", e.removed ? h("span", { class: "neg" }, `− ${trName(e.removed)}`) : null,
      e.removed && e.added ? " " : null,
      e.added ? h("span", { class: "pos" }, `+ ${trName(e.added)}${e.level ? ` (${t("gmLevelQ", e.level, e.quality)})` : ""}`) : null,
      e.dropped && e.dropped.length ? h("span", { class: "muted" }, " " + t("gmDropped", e.dropped.map(trName).join(", "))) : null)
    : e.action === "swap"
    ? h("li", {}, (e.target || "").startsWith("package:") ? [h("b", {}, t("pkLog", t("pk_" + e.target.slice(8)))), h("br")] : null,
      h("span", { class: "neg" }, `− ${names(e.removed)}`), h("br"), h("span", { class: "pos" }, `+ ${names(e.added)}`))
    : e.action === "add" && (e.target || "").startsWith("package:")
    ? h("li", { class: "pos" }, `+ ${t("pkLog", t("pk_" + e.target.slice(8)))} (${t("pointsN", e.nodes.length)}): ${names(e.nodes)}`)
    : e.action === "add" ? h("li", { class: "pos" }, `+ ${trName(e.target)} (${t("pointsN", e.nodes.length)}${e.set ? " · " + t("tvWsSet", e.set) : ""}): ${names(e.nodes)}`)
      : h("li", { class: "neg" }, `− ${trName(e.target)} (${t("pointsN", e.nodes.length)}${e.set ? " · " + t("tvWsSet", e.set) : ""}): ${names(e.nodes)}`);
}

function editButton(action, node) {
  return h("button", { class: "ghost small nowrap", title: action === "add" ? t("takeHint") : t("dropHint"),
    onclick: () => treeCall(`/api/tree/${action}`, { id: node.id, name: node.name }) }, action === "add" ? t("take") : t("drop"));
}

function pointsLine(p) {
  if (!p) return null;
  const left = p.total - p.used;
  return h("div", { class: "tv-points" }, h("b", { class: left < 0 ? "neg" : "" }, t("tvPoints", p.used, p.total)),
    h("span", { class: left < 0 ? "neg" : "muted" }, " · " + (left < 0 ? t("tvOver", -left) : t("tvLeft", left))),
    h("span", { class: p.asc > p.ascTotal ? "neg" : "muted" }, " · " + t("tvAscPoints", p.asc, p.ascTotal)),
    // the weapon sets' nodes, each of its own limit
    ...(p.wsTotal ? [1, 2].map((k) => h("span", { class: `tv-wsn ws${k}` + (p["ws" + k] > p.wsTotal ? " over" : ""),
      title: t("tvWsPointsHint", p.wsTotal) }, " · ", t("tvWsPoints", k, p["ws" + k], p.wsTotal))) : []));
}

function planCard(plan, points) {
  const optimize = h("button", { class: "primary", onclick: async () => {
    const r = await treeCall("/api/tree/optimize", { mode: state.mode, seed: Math.floor(Math.random() * 1e9) }, t("optimizing"));
    if (r) toast(r.found ? t("optimized", r.found) : t("optimizedNone"), !!r.found);
  } }, plan && plan.log.length ? t("optimizeMore") : t("optimize"));
  // the points: what the character's level gives (pointsLine); the edits themselves are in the strip above the tab
  return h("div", { class: "card plan" },
    h("h3", {}, t("planTitle")), h("div", { class: "sub" }, t("planSub", t("mode_" + state.mode))), pointsLine(points),
    plan && plan.log.length ? null : h("p", { class: "muted" }, t("planEmpty")),
    h("div", { class: "row", style: "margin-top:10px" }, optimize));
}

// ---- jewels in the tree's sockets: each socket's jewel and what it gives; take it out, or put in a unique, one
// made the way the game makes them (a base, a rarity, the mods that base rolls) or one copied from the game ----
const JW_DELTA = [["dps", "m_dps"], ["ehp", "m_ehp"]];
const JW_RANGE = /\(-?[\d.]+--?[\d.]+\)/;
const jwName = (n) => itemTitle({ name: n, baseName: (n || "").split(", ")[1] || "" });

// What a jewel does on the tree beyond its lines (poe2lab.analysis.jewels): a timeless jewel's conqueror and the
// passives it swaps, From Nothing's keystone and the nodes taken without a path, a Time-Lost jewel's sum over its radius
const JE_KIND = (k) => t("jeKind_" + k);
const jeNames = (reached) => {
  const big = reached.filter((n) => n.type === "notable" || n.type === "keystone").map((n) => trName(n.name));
  const small = reached.length - big.length;
  return [...big, small ? t("jeMoreSmall", small) : null].filter(Boolean).join(", ");
};
function jewelEffect(e) {
  if (!e) return null;
  const rows = [];
  if (e.kind === "timeless") {
    rows.push(h("div", {}, "⚔ ", t("jeTimeless", t("jeConq_" + e.conqueror.kind), e.conqueror.seed)));
    for (const r of e.replaced) rows.push(h("div", { class: "je-swap" }, h("div", {}, h("span", { class: "muted" }, trName(r.name)), " → ", h("b", {}, trName(r.now))),
      h("ul", { class: "item-lines small" }, r.lines.map((l) => h("li", {}, trMod(l))))));
    if (e.unknown.length) rows.push(h("div", { class: "hint" }, t("jeUnknown", e.unknown.length, e.unknown.map((x) => trName(x)).join(", "))));
    if (e.small) rows.push(h("div", { class: "muted small" }, t("jeSmall", e.small)));
  } else if (e.kind === "fromNothing") {
    rows.push(h("div", {}, t("jeNothing", trName(e.keystone), e.reached.length)));
    if (e.reached.length) rows.push(h("div", { class: "muted small" }, jeNames(e.reached)));
  } else if (e.kind === "radiusMods") {
    for (const g of e.grants) rows.push(h("div", {}, g.total ? t("jeGrant", g.count, JE_KIND(g.kind), trMod(g.total)) : t("jeEffectOf", g.count, JE_KIND(g.kind))));
  } else {
    rows.push(h("div", {}, t(e.kind === "leap" ? "jeLeap" : "jeReach", e.reached.length)));
    if (e.reached.length) rows.push(h("div", { class: "muted small" }, jeNames(e.reached)));
  }
  return h("div", { class: "je stack" }, e.radius ? h("div", { class: "muted small" }, t("jeRadius", t("jeRadius_" + e.radius.replace(/ /g, "")))) : null, ...rows);
}
// the same in one line, for a socket's tile
function jewelGist(s) {
  const e = s.effect, it = s.item;
  if (e && e.kind === "timeless") {
    const r = e.replaced[0];
    return r ? `⚔ ${trName(r.name)} → ${trName(r.now)}` : `⚔ ${t("jeConq_" + e.conqueror.kind)}: ${t("jeUnknownShort", e.unknown.length)}`;
  }
  if (e && e.kind === "fromNothing") return t("jeNothingShort", trName(e.keystone), e.reached.length);
  if (e && e.kind === "radiusMods") return e.grants.map((g) => (g.total ? trMod(g.total) : t("jeEffectOf", g.count, JE_KIND(g.kind)))).join(" · ");
  if (e) return t(e.kind === "leap" ? "jeLeap" : "jeReach", e.reached.length);
  // a unique without a radius: its own line says what it gives
  return it.rarity === "UNIQUE" && it.explicit.length ? trMod(it.explicit[0].line) : null;
}

function jewelCard(jw) {
  const art = (s) => s.item ? itemIcon(s.item.name, s.item.baseName, s.item.rarity) || h("span", { class: "jw-gem" }) : h("span", { class: "jw-hole" });
  // over a jewel: its lines and what it does on the tree
  const tip = (s) => () => h("div", { class: "stack" }, h("b", { class: "r-" + (s.item.rarity || "normal").toLowerCase() }, itemTitle(s.item)),
    h("ul", { class: "item-lines small" }, [...s.item.implicit, ...s.item.explicit].map((m) => h("li", {}, trMod(m.line)))), jewelEffect(s.effect));
  const tile = (s) => {
    const gist = s.item ? jewelGist(s) : null;
    const el = h("button", { class: "jw-socket" + (s.item ? " r-" + (s.item.rarity || "normal").toLowerCase() : " vacant"),
      title: s.item ? null : t("jwOpen"), onclick: () => jewelEditor(s) },
    h("div", { class: "jw-art" }, art(s)),
    h("div", { class: "jw-name" }, s.item ? itemTitle(s.item) : t("jwEmpty")),
    gist ? h("div", { class: "jw-gist small" }, gist) : null,
    h("div", { class: "muted small" }, t("jwNear", trName(s.near))),
    s.without ? h("div", { class: "jw-without" }, h("span", { class: "muted small" }, t("jwWithout")), deltas(s.without, JW_DELTA, 0.3)) : null);
    return s.item ? hoverTip(el, tip(s)) : el;
  };
  return h("div", { class: "card" }, h("h3", {}, t("jwTitle")),
    jw.sockets.length ? h("div", { class: "sub" }, t("jwSub")) : null,
    jw.sockets.length ? h("div", { class: "jw-grid" }, jw.sockets.map(tile)) : h("p", { class: "muted" }, t("jwNone")));
}

let JW_CATALOG = null;
// opts.after(path, body): how an edit is made (default: through the Tree tab); opts.drop: taking the socket itself off,
// opts.dropCount: how many nodes go with it
async function jewelEditor(socket, opts = {}) {
  const edit = opts.after || treeCall;
  if (!JW_CATALOG) {
    try { JW_CATALOG = await api("/api/jewels/catalog"); } catch (e) { toast(e.message); return; }
  }
  const cat = JW_CATALOG;
  const emptySlots = () => ({ Prefix: [], Suffix: [] });
  const own = socket.item && cat.bases.find((b) => b.name === socket.item.baseName);
  const ed = { tab: "create", base: (own || cat.bases.find((b) => b.colour === "int") || cat.bases[0]).name, rarity: "rare",
    slots: emptySlots(), corruption: null, unique: null, roll: 0.5, text: "", q: "" };

  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) close(); } });
  const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } };
  const close = () => { clearTimeout(timer); back.remove(); document.removeEventListener("keydown", onKey, true); };
  const body = h("div", { class: "stack" });
  const preview = h("div", { class: "stack" });
  const put = h("button", { class: "primary", disabled: true, onclick: () => {
    const s = spec();
    close();
    edit("/api/jewels/set", { node: socket.node, ...s });
  } }, t("jwPut"));
  const remove = socket.item ? h("button", { class: "ghost", onclick: () => {
    close();
    edit("/api/jewels/remove", { node: socket.node });
  } }, t("jwRemove")) : null;
  const drop = opts.drop ? h("button", { class: "ghost", title: t("jwDropSocketHint"), onclick: () => { close(); opts.drop(); } },
    t("jwDropSocket", opts.dropCount || 1)) : null;

  // what goes to the server: a unique, a made jewel or a pasted one; null when nothing is chosen yet
  const spec = () => {
    if (ed.tab === "unique") return ed.unique ? { unique: ed.unique.name, base: ed.unique.base, roll: ed.roll } : null;
    if (ed.tab === "paste") return ed.text.trim() ? { text: ed.text } : null;
    const mods = [...ed.slots.Prefix, ...ed.slots.Suffix].filter(Boolean);
    return mods.length || ed.corruption ? { base: ed.base, rarity: ed.rarity, mods, corruption: ed.corruption } : null;
  };
  let seq = 0, timer = null;
  const refresh = () => { clearTimeout(timer); timer = setTimeout(runPreview, 250); };
  async function runPreview() {
    const s = spec(), my = ++seq;
    put.disabled = true;
    if (!s) { preview.replaceChildren(h("p", { class: "muted" }, t("jwPick"))); return; }
    preview.replaceChildren(loading(t("counting")));
    try {
      const r = await api("/api/jewels/preview", { method: "POST", body: { node: socket.node, ...s } });
      if (my !== seq) return;
      preview.replaceChildren(itemCard(r.item, null, t("jwResult")),
        h("div", {}, h("div", { class: "sub", style: "margin:0 0 4px" }, t(socket.item ? "jwVsNow" : "jwVsEmpty")), deltas(r.change, METRIC, 0.3)));
      put.disabled = false;
    } catch (e) { if (my === seq) preview.replaceChildren(h("p", { class: "neg" }, e.message)); }
  }

  const modText = (m) => m.lines.map(trMod).join(" / ");
  const rollSlider = (value, on) => h("div", { class: "jw-roll", title: t("jwRollHint") }, t("jwRollLow"),
    h("input", { type: "range", min: 0, max: 100, value: Math.round(value * 100), oninput: (e) => on(Number(e.target.value) / 100) }),
    t("jwRollHigh"));

  const drawCreate = () => {
    const base = cat.bases.find((b) => b.name === ed.base);
    const byId = Object.fromEntries([...base.mods, ...base.corruption].map((m) => [m.id, m]));
    const limits = cat.limits[ed.rarity];
    const baseTiles = h("div", { class: "jw-bases" }, cat.bases.map((b) => h("button", {
      class: "jw-base" + (b.name === ed.base ? " sel" : ""), title: trName(b.name),
      onclick: () => { if (ed.base !== b.name) { ed.base = b.name; ed.slots = emptySlots(); ed.corruption = null; draw(); refresh(); } } },
    itemIcon(null, b.name, "normal") || h("span", { class: "jw-gem c-" + b.colour }), h("span", { class: "small" }, trName(b.name)))));
    const rarity = h("div", { class: "segmented" }, ["magic", "rare"].map((k) => h("button", { class: ed.rarity === k ? "active" : "",
      onclick: () => {
        ed.rarity = k;
        for (const side of ["Prefix", "Suffix"]) ed.slots[side] = ed.slots[side].slice(0, cat.limits[k][side === "Prefix" ? 0 : 1]);
        draw(); refresh();
      } }, t("jwRarity_" + k))));
    // one mod per family, as in the game: the families already on the jewel are not offered again
    const slot = (side, i) => {
      const cur = ed.slots[side][i] || null;
      const used = new Set([...ed.slots.Prefix, ...ed.slots.Suffix].filter((x) => x && x !== cur).map((x) => byId[x.id].group));
      const opts = base.mods.filter((m) => m.type === side && !used.has(m.group));
      const option = (m) => h("option", { value: m.id, selected: !!cur && cur.id === m.id }, modText(m));
      const desecrated = opts.filter((m) => m.set === "Desecrated");
      const sel = h("select", { class: cur ? "" : "muted", onchange: () => {
        ed.slots[side][i] = sel.value ? { id: sel.value, roll: cur ? cur.roll : 0.5 } : null;
        draw(); refresh();
      } }, h("option", { value: "" }, t("jwNoMod")),
      h("optgroup", { label: t("jwModsNormal") }, opts.filter((m) => m.set !== "Desecrated").map(option)),
      desecrated.length ? h("optgroup", { label: t("jwModsDesecrated") }, desecrated.map(option)) : null);
      const ranged = cur && byId[cur.id].lines.some((l) => JW_RANGE.test(l));
      return h("div", { class: "jw-slot" + (cur && byId[cur.id].set === "Desecrated" ? " desecrated" : "") }, sel,
        ranged ? rollSlider(cur.roll, (v) => { cur.roll = v; refresh(); }) : null);
    };
    const side = (name, n) => [h("div", { class: "jw-side" }, t(name === "Prefix" ? "jwPrefixes" : "jwSuffixes")),
      ...Array.from({ length: n }, (_, i) => slot(name, i))];
    const corr = h("select", { class: ed.corruption ? "" : "muted", onchange: () => {
      ed.corruption = corr.value ? { id: corr.value, roll: 0.5 } : null;
      draw(); refresh();
    } }, h("option", { value: "" }, t("jwNoCorruption")),
    base.corruption.map((m) => h("option", { value: m.id, selected: !!ed.corruption && ed.corruption.id === m.id }, modText(m))));
    const corrRanged = ed.corruption && byId[ed.corruption.id].lines.some((l) => JW_RANGE.test(l));
    return [baseTiles, rarity, ...side("Prefix", limits[0]), ...side("Suffix", limits[1]),
      h("div", { class: "jw-side" }, t("jwCorruption")),
      h("div", { class: "jw-slot" }, corr, corrRanged ? rollSlider(ed.corruption.roll, (v) => { ed.corruption.roll = v; refresh(); }) : null)];
  };

  const drawUnique = () => {
    const match = (u) => !ed.q || [u.name, trName(u.name), trName(u.base)].join(" ").toLowerCase().includes(ed.q.toLowerCase());
    const cards = () => cat.uniques.filter(match).map((u) => h("button", {
      class: "jw-unique" + (ed.unique === u ? " sel" : ""), title: u.lines.map(trMod).join("\n"),
      onclick: () => { ed.unique = u; draw(); refresh(); } },
    itemIcon(u.name, u.base, "unique"), h("div", {}, h("div", { class: "jw-uname" }, trName(u.name)), h("div", { class: "muted small" }, trName(u.base)))));
    const list = h("div", { class: "jw-uniques" }, cards());
    const q = h("input", { type: "search", placeholder: t("jwSearch"), value: ed.q, oninput: () => { ed.q = q.value; list.replaceChildren(...cards()); } });
    return [q, list, ed.unique && ed.unique.ranged ? rollSlider(ed.roll, (v) => { ed.roll = v; refresh(); }) : null];
  };

  const drawPaste = () => {
    const ta = h("textarea", { rows: 12, placeholder: t("jwPastePh"), spellcheck: "false", oninput: () => { ed.text = ta.value; refresh(); } }, ed.text);
    return [ta];
  };

  const tabs = () => h("div", { class: "segmented" }, [["create", t("jwCreate")], ["unique", t("jwUniques")], ["paste", t("jwPaste")]]
    .map(([k, label]) => h("button", { class: ed.tab === k ? "active" : "", onclick: () => { ed.tab = k; draw(); refresh(); } }, label)));
  const draw = () => body.replaceChildren(tabs(), ...(ed.tab === "create" ? drawCreate() : ed.tab === "unique" ? drawUnique() : drawPaste()));

  back.append(h("div", { class: "ask card stack jw-editor", role: "dialog", "aria-modal": "true" },
    h("div", { class: "jw-head" }, h("h3", {}, t("jwEditTitle", trName(socket.near))),
      h("button", { class: "ghost small", title: t("cancel"), onclick: close }, "✕")),
    socket.item ? h("details", {}, h("summary", {}, t("jwNow", itemTitle(socket.item))), itemCard(socket.item, null, "")) : null,
    h("div", { class: "jw-main" }, body, h("div", { class: "jw-out stack" }, preview, h("div", { class: "row" }, put, remove, drop)))));
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
  draw();
  runPreview();
}

// ---------- loot filter ----------
// the loot filter's market block: on or off, and the two price bars, each in exalted or divine orbs (per viewer)
const LOOT_MARKET = { market: true, top: 1, top_unit: "div", low: 50, low_unit: "ex", demand: true, demand_ilvl: 82, demand_min: 2 };
// the part of the game the filter is for: the campaign (below area level 65) or maps; a character still in the
// campaign starts on the campaign's, anything else on the maps'; the player's last pick is remembered
function lootStage() {
  try { const v = localStorage.getItem("poe2lab.lootStage"); if (v === "leveling" || v === "maps") return v; } catch (_) { /* storage blocked */ }
  return state.build && state.build.main && (state.build.info.level || 0) < 65 ? "leveling" : "maps";
}
function lootMarket() {
  try { return { ...LOOT_MARKET, ...JSON.parse(localStorage.getItem("poe2lab.lootMarket") || "{}") }; } catch (_) { return { ...LOOT_MARKET }; }
}
const lootQuery = (m) => new URLSearchParams(Object.entries(m).map(([k, v]) => [k, String(v)])).toString();

TABS.loot = async (view) => {
  view.replaceChildren(loading(t("lootLoading")));
  const stage = lootStage();
  const mk = { ...lootMarket(), stage };
  const r = await cached(`loot:${state.mode}:${lootQuery(mk)}`, () => api(`/api/lootfilter?mode=${state.mode}&${lootQuery(mk)}&${buildQuery()}`));
  // two filters: the campaign's and the maps'; the player switches between them in the game at maps
  const stageSeg = h("div", { class: "seg loot-stage" }, [["leveling", "run"], ["maps", "map"]].map(([k, ic]) =>
    h("button", { class: stage === k ? "active" : "", title: t("lootStageHint_" + k), onclick: () => {
      try { localStorage.setItem("poe2lab.lootStage", k); } catch (_) { /* storage blocked */ }
      switchTab("loot");
    } }, I(ic), h("span", {}, t("lootStage_" + k)))));
  const leveling = stage === "leveling";
  const rows = r.rules.map((x) => leveling ? h("tr", {},
    h("td", {}, slotName(x.slot)),
    h("td", {}, h("span", { class: "named", title: x.base }, icon(x.base), trName(x.base)),
      x.unique ? h("div", { class: "hint" }, t("lootUniqueLv")) : null),
    h("td", { class: "small" }, x.leveling.length ? t("lootLevelingCell", x.leveling.length) : h("span", { class: "muted" }, "—")))
    : h("tr", {},
    h("td", {}, slotName(x.slot)),
    h("td", {}, h("span", { class: "named", title: x.base }, icon(x.base), trName(x.base)),
      x.unique ? h("div", { class: "hint" }, t("lootUnique")) : null),
    h("td", { class: "num" }, x.unique ? "—" : x.item_level),
    h("td", {}, x.unique ? h("span", { class: "muted small" }, t("lootByBase"))
      : x.affixes.length ? hoverTip(h("span", { class: "pk-node small" }, t("lootModsN", x.mods.length)),
        () => linesTip(icon(x.base), trName(x.base), x.mods.map((m) => h("li", { title: m }, trMod(m))), t("lootAffixes", x.affixes.length)))
        : h("span", { class: "muted small" }, t("lootNoMods")))));
  const head = leveling ? [t("slot"), t("lootLvClass"), t("lootLeveling")] : [t("slot"), t("lootBase"), t("lootIlvl"), t("lootGold")];
  const what = foldedCard(h("div", { class: "card" }, h("h3", {}, t("lootWhat")), h("div", { class: "sub" }, t(leveling ? "lootWhatSubLv" : "lootWhatSub", t("mode_" + state.mode))),
    h("table", { class: "versus-items" }, h("thead", {}, h("tr", {}, head.map((x, i) => h("th", { class: !leveling && i === 2 ? "num" : null }, x)))), h("tbody", {}, rows)),
    leveling ? lootLevelingExtras(r.leveling) : null,
    h("div", { class: "hint", style: "margin-top:8px" }, t(leveling ? "lootLevelingLegend" : "lootLegend"))), "what", t("lootWhatSum", r.rules.length));

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
  const name = h("input", { type: "text", placeholder: t("lootNamePh", t("lootStageShort_" + stage)), style: "width:100%" });
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
        file: chosen || null, text: text.value, name: name.value.trim() || null, ...mk } });
      done.replaceChildren(h("div", { class: "action" }, t("lootSaved", res.name, res.path)));
      toast(t("lootSavedShort", res.name), true);
    } catch (e) { toast(e.message); }
    save.disabled = false;
  } }, t("lootSave"));
  const done = h("div", {});
  const build = h("div", { class: "card stack" }, h("h3", {}, t("lootBuild_" + stage)), h("div", { class: "sub" }, t("lootBuildSub")),
    seg, paneBox, h("label", { class: "field" }, h("span", {}, t("lootName")), name), h("div", {}, save), done,
    h("div", { class: "hint" }, t("lootOnline")));
  const copy = h("button", { class: "ghost small", onclick: async () => {
    try { await navigator.clipboard.writeText(r.block); toast(t("copied"), true); } catch (e) { toast(e.message); }
  } }, t("copyBlock"));
  const preview = h("div", { class: "card" }, h("details", {}, h("summary", {}, t("lootPreview")),
    h("div", { class: "row", style: "margin:8px 0" }, copy), h("pre", { class: "filter-preview" }, r.block)));
  return h("div", { class: "stack" }, stageSeg, h("div", { class: "sub" }, t("lootIntro_" + stage)), what,
    leveling ? null : marketCard(r.market, mk), leveling ? null : demandCard(r.demand, mk), build, preview);
};

// the campaign's extras: the weapon of the way the player levels with, what the build's author planned for the gear
function lootLevelingExtras(x) {
  if (!x) return null;
  const rows = [
    x.weapons.length ? h("li", {}, t("lootLvWeapon", x.weapons.map((c) => t("lootClass", c)).join(", "))) : null,
    x.bases.length ? h("li", {}, t("lootLvPlanBases"), " ", x.bases.map((b, i) => [i ? ", " : "", h("span", { class: "named" }, icon(b), trName(b))])) : null,
    x.uniques.length ? h("li", {}, t("lootLvPlanUniques"), " ", x.uniques.map((b, i) => [i ? ", " : "", h("span", { class: "named" }, icon(b), trName(b))])) : null,
  ].filter(Boolean);
  return h("div", { class: "loot-extras" }, h("div", { class: "lr-sec-k" }, t("lootLvExtras")),
    rows.length ? h("ul", { class: "item-lines small" }, rows) : h("div", { class: "muted small" }, t("lootLvNoExtras")));
}

// the maps' filter: the bases most players craft on - the kinds of gear the ladder wears rare, each with its
// end-game bases, white from an item level every tier rolls at
function demandCard(d, mk) {
  const redo = (patch) => {
    try { localStorage.setItem("poe2lab.lootMarket", JSON.stringify({ ...lootMarket(), ...patch })); } catch (_) { /* storage blocked */ }
    switchTab("loot");
  };
  const on = h("input", { type: "checkbox", checked: mk.demand, onchange: (e) => redo({ demand: e.target.checked }) });
  const ilvl = h("select", { onchange: (e) => redo({ demand_ilvl: Number(e.target.value) }) },
    [75, 78, 80, 82].map((n) => h("option", { value: n, selected: Number(mk.demand_ilvl) === n }, n)));
  const least = h("select", { onchange: (e) => redo({ demand_min: Number(e.target.value) }) },
    [1, 2, 3, 5].map((n) => h("option", { value: n, selected: Number(mk.demand_min || 2) === n }, n)));
  const shareBar = (v) => h("span", { class: "demand-share", style: `--v:${Math.min(100, v)}%` }, h("i"));
  const body = [];
  if (mk.demand && d && d.error) body.push(h("p", { class: "bad small" }, d.error));
  else if (mk.demand && d && d.source === "top") {
    // what the ladder's top characters of each class wear rare, by kind of gear; each base with how many wear it
    body.push(h("div", { class: "muted small" }, t("demandTop", d.perClass, d.classes, d.characters, trName(d.league || ""))),
      ...d.groups.map((g) => h("details", { class: "market-group" }, h("summary", {}, h("b", {}, t("lootKind", g.kind)), " ",
        g.share ? shareBar(g.share) : null,
        h("span", { class: "muted small" }, g.share ? t("demandShare", fmt(g.share, 0), g.bases.length) : t("demandBasesN", g.bases.length))),
      h("ul", { class: "item-lines small demand-bases" }, g.bases.map((b) => h("li", { title: t("demandWho", b.classes.map((c) => trName(c)).join(", "), b.ilvl[0], b.ilvl[1]) },
        h("span", { class: "named" }, icon(b.base), trName(b.base)), " ", h("b", { class: "demand-n" }, `×${b.n}`)))))));
  } else if (mk.demand && d) {
    body.push(h("div", { class: "hint" }, d.note || ""), h("div", { class: "muted small" }, t("demandLadder", trName(d.league || ""), fmt(d.characters || 0))),
      ...d.kinds.map((k) => h("details", { class: "market-group" }, h("summary", {}, h("b", {}, t("lootKind", k.kind)), " ", shareBar(k.share),
        h("span", { class: "muted small" }, t("demandShare", fmt(k.share, 0), k.bases.length))),
        h("ul", { class: "item-lines small demand-bases" }, k.bases.map((b) => h("li", {}, h("span", { class: "named" }, icon(b), trName(b))))))));
  }
  const count = d && (d.groups ? d.groups.reduce((n, g) => n + g.bases.length, 0) : d.kinds ? d.kinds.length : 0);
  return foldedCard(h("div", { class: "card stack" }, h("h3", {}, t("demandTitle")), h("div", { class: "sub" }, t("demandSub")),
    h("label", { class: "row", style: "gap:8px" }, on, t("demandOn")),
    mk.demand ? h("div", { class: "row", style: "gap:16px;flex-wrap:wrap" }, h("label", { class: "row", style: "gap:8px" }, t("demandIlvl"), ilvl),
      h("label", { class: "row", style: "gap:8px" }, t("demandLeast"), least)) : null, ...body),
  "demand", mk.demand && count ? t(d.groups ? "demandSumTop" : "demandSum", count) : t("marketSumOff"));
}

// the market block: what poe.ninja prices at the chosen bars, and the bars themselves
function marketCard(m, mk) {
  const redo = (patch) => {
    try { localStorage.setItem("poe2lab.lootMarket", JSON.stringify({ ...mk, ...patch })); } catch (_) { /* storage blocked */ }
    switchTab("loot");
  };
  const bar = (key) => h("span", { class: "row", style: "gap:6px;display:inline-flex" },
    h("input", { type: "number", min: 0.001, step: "any", value: mk[key], style: "width:80px",
      onchange: (e) => { const v = Number(e.target.value); if (v > 0) redo({ [key]: v }); } }),
    h("select", { onchange: (e) => redo({ [key + "_unit"]: e.target.value }) },
      ["ex", "div"].map((u) => h("option", { value: u, selected: mk[key + "_unit"] === u }, u))));
  const on = h("input", { type: "checkbox", checked: mk.market, onchange: (e) => redo({ market: e.target.checked }) });
  const price = (div) => (m && div * m.exaltedPerDivine < 100 ? `${fmt(div * m.exaltedPerDivine, 0)} ex` : `${fmt(div, 1)} div`);
  const list = (rows, name) => h("ul", { class: "item-lines small market-list" }, rows.map((x) =>
    h("li", {}, h("span", { class: "named" }, icon(name(x)), trName(name(x))), " — ", h("b", {}, price(x.div !== undefined ? x.div : x[1])))));
  const body = [];
  if (mk.market && m && m.error) body.push(h("p", { class: "bad small" }, m.error));
  else if (mk.market && m) {
    const sm = m.summary;
    const group = (title, items, levelled, uniques) => {
      const n = items.length + levelled.length + uniques.length;
      return h("details", { class: "market-group" }, h("summary", {}, h("b", {}, title), " ", h("span", { class: "muted small" }, t("marketCount", n))),
        items.length ? list(items, (x) => x[0]) : null,
        levelled.length ? h("ul", { class: "item-lines small" }, levelled.map((x) => h("li", {}, t("marketLevelled", trName(x.base), x.level), " — ", h("b", {}, price(x.div))))) : null,
        uniques.length ? h("div", {}, h("div", { class: "muted small" }, t("marketUniques")),
          h("ul", { class: "item-lines small" }, uniques.map((u) => h("li", { title: u.names.join(", ") },
            h("span", { class: "named" }, icon(u.base), trName(u.base)), " — ", t("marketFrom", price(u.div)))))) : null);
    };
    if (m.topDiv < m.lowDiv) body.push(h("p", { class: "hint" }, t("marketBarsSwapped")));
    body.push(h("div", { class: "muted small" }, t("marketLeague", trName(m.league), fmt(m.exaltedPerDivine, 0))),
      group(t("marketTop"), sm.top, sm.levelled.top, sm.uniques.top),
      group(t("marketLow"), sm.low, sm.levelled.low, sm.uniques.low),
      sm.maybe.length ? h("details", { class: "market-group" }, h("summary", {}, h("b", {}, t("marketMaybe")), " ",
        h("span", { class: "muted small" }, t("marketCount", sm.maybe.length))),
        h("ul", { class: "item-lines small" }, sm.maybe.map((u) => h("li", { title: u.names.join(", ") },
          h("span", { class: "named" }, icon(u.base), trName(u.base)), " — ", t("marketMaybeOne", u.names.map(trName).join(", "), price(u.div)))))) : null);
  }
  return foldedCard(h("div", { class: "card stack" }, h("h3", {}, t("marketTitle")), h("div", { class: "sub" }, t("marketSub")),
    h("label", { class: "row", style: "gap:8px" }, on, t("marketOn")),
    mk.market ? h("div", { class: "row craft-controls" }, h("label", {}, t("marketTopBar"), " ", bar("top")),
      h("label", {}, t("marketLowBar"), " ", bar("low"))) : null,
    ...body), "market", mk.market ? t("marketSumOn", `${mk.top} ${mk.top_unit}`) : t("marketSumOff"));
}

// ---------- levelling up to the build (poe2lab.analysis.leveling) ----------
// Guides are for 75+; up to that the player levels on their own. Four questions (only when asked for), then a
// roadmap by acts - above all when to switch to the build and why, each reason with PoB's number.
const LR_WEAPON = { quarterstaff: "🥢", mace: "🔨", bow: "🏹", crossbow: "🎯", spear: "🔱", talisman: "🐺", spell: "✨", minion: "💀" };
const LR_ELEMENT = { fire: "🔥", cold: "❄️", lightning: "⚡", chaos: "☠️", physical: "⚔️" };
const LR_MIN_GUIDE = 60;  // a build below this level is not a guide to level up to
const lrWayTitle = (w) => (w.id === "build" ? t("lrWayBuild")
  : `${t("lrWeapon_" + w.weapon)}${w.element ? " · " + t("lrEl_" + w.element) : ""}`);
const lrWayIcon = (w) => (w.id === "build" ? "⭐" : `${LR_WEAPON[w.weapon] || ""}${w.element ? LR_ELEMENT[w.element] || "" : ""}`);
const lrSkill = (s) => h("span", { class: "lr-skill" + (s.until ? " until" : ""), title: t("lrFromLevel", s.level) }, gemName(s.name),
  h("span", { class: "lr-lvl" }, s.level));
// a stage's mark on the track and in its card: the act's number, I for the interludes, a star for maps
const lrStageMark = (key) => (key.startsWith("act") ? key.slice(3) : key === "interlude" ? (LANG === "en" ? "I" : "И") : "★");
const lrStageName = (key) => t("lrStage_" + key);

function levelingCard() {
  const card = h("div", { class: "card lr-card hidden" }, h("h3", {}, t("lrTitle")), loading(t("lrLoading")));
  DATA.leveling()
    .then((d) => { if (d.ways.level >= LR_MIN_GUIDE) { card.classList.remove("hidden"); drawLeveling(card, d); } else card.remove(); })
    .catch(() => card.remove());
  return card;
}

// why the switch is at its level: the piece the build waits for, in words
function lrReason(p) {
  if (p.kind === "skill") {
    if (p.source === "ascendancy") return t("lrWhySkillAsc", trName(p.name), trName(p.sourceName), p.trial);
    if (p.source === "item") return t("lrWhySkillItem", trName(p.name), trItem(p.sourceName.split(",")[0]), p.level);
    return p.level ? t("lrWhySkill", trName(p.name), p.level) : t("lrWhySkillUnknown", trName(p.name));
  }
  if (p.kind === "support") return t("lrWhySupport", trName(p.firstName || p.name), pct(p.dps), p.level);
  if (p.kind === "source") return t("lrWhySource", t("lrMech_" + p.mechanic), trName(p.name), p.via ? trName(p.via) : "", p.level);
  if (p.kind === "buff") return t("lrWhyBuff", trName(p.name), pct(p.dps), p.level);
  if (p.kind === "spirit") return p.short ? t("lrWhySpiritShort", p.need, p.have) : t("lrWhySpirit", p.need, p.level);
  if (p.kind === "snapshot") return t("lrWhySnapshot", p.at, lrProblems(p.problems));
  return t("lrWhyUnique", trItem(p.name.split(",")[0]), pct(p.dps), p.level);
}

// what does not work yet as a character of that level has the build (PoB's snapshot): Spirit, mana
function lrProblems(xs) {
  return xs.map((x) => x.kind === "spirit" ? t("lrProbSpirit", x.have, x.need) : t("lrProbMana", fmt(x.cost), fmt(x.regen, 1))).join(", ");
}

// the attributes the gems want more of than a character of that level has without attribute nodes and gear
function lrAttributes(xs) {
  return xs.map((x) => t("lrAttr_" + x.attr, x.need, x.have)).join(", ");
}

// where the Spirit comes from, by level: quests, items, the rest
function lrSpiritSources(p) {
  return p.sources.map((x) => {
    // a quest by its area (the boss names have no translation), an item by its slot
    const what = x.kind === "quest" ? questArea(x.area) : x.kind === "item" ? slotName(x.slot) : t("lrSpiritOther");
    return `${what} +${x.spirit}` + (x.level ? ` (${t("lrLv", x.level)})` : "");
  }).join(" · ");
}

// Invoker's Spirit from body armour: what the armour must give, and the catch of taking the notable early
function lrArmourNote(p) {
  const a = p.armour;
  if (!a || !a.need) return null;
  const amounts = a.rates.map((r) => `${fmt(a.need * r.per)} ${t("lrDef_" + r.what.replace(/ /g, ""))}`).join(t("lrOr"));
  return h("div", { class: "hint" }, t("lrArmourSpirit", trName(a.node), a.need, amounts), a.noGear ? " " + t("lrNoGearSpirit") : "");
}

function lrPart(p, trade) {
  const pic = p.kind === "unique" ? itemIcon(p.name, p.name.split(",")[1], "unique")
    : p.kind === "spirit" ? h("span", { class: "lr-emoji" }, "✨")
    : p.kind === "snapshot" ? h("span", { class: "lr-emoji" }, "🧪") : icon(p.name);
  const gem = p.firstName || p.name;
  const name = p.kind === "unique" ? h("b", {}, trItem(p.name.split(",")[0]))
    : p.kind === "spirit" ? h("b", {}, t("lrSpirit"))
    : p.kind === "snapshot" ? h("b", {}, t("lrSnapshot"))
    : hoverTip(h("b", { class: "pk-node" }, trName(gem)), () => gemTipCard(gem));
  let note = null;
  if (p.kind === "support" && p.firstName) note = t("lrSupportFull", trName(p.name), p.full);
  if (p.kind === "skill" && !p.level) note = lrReason(p);
  if (p.kind === "skill" && p.source === "ascendancy") note = t("lrApprox");
  if (p.kind === "unique" && p.core && !trade) note = t("lrSsfUnique", pct(p.dps));
  if (p.kind === "unique" && p.defence) note = t("lrDefUnique", pct(p.ehp));
  if (p.kind === "source") note = [t("lrSourceNote", t("lrMech_" + p.mechanic), p.via ? trName(p.via) : ""),
    p.spirit ? t("lrReserves", p.spirit) : "", p.byHand ? t("lrByHand", p.byHand) : ""].filter(Boolean).join(" · ");
  if (p.kind === "buff") note = [p.mechanic ? t("lrMakes", t("lrMech_" + p.mechanic)) : "", p.spirit ? t("lrReserves", p.spirit) : ""].filter(Boolean).join(" · ") || null;
  if (p.kind === "spirit") note = lrSpiritSources(p);
  if (p.kind === "snapshot") note = lrReason(p);
  const worth = p.kind === "skill" ? t("lrMainSkill") : p.kind === "spirit" ? t("lrSpiritNeed", p.need, p.have)
    : p.kind === "snapshot" ? ""
    : p.kind !== "unique" ? t("lrDps", pct(p.dps)) : p.core ? t("lrDps", pct(p.dps)) : t("lrEhp", pct(p.ehp));
  return h("div", { class: "lr-part" + (p.decisive ? " decisive" : "") + (p.kind === "unique" && p.core && !trade ? " ssf" : "") },
    h("span", { class: "lr-part-ico" }, pic),
    h("div", { class: "lr-part-body" }, h("div", {}, name, " ", h("span", { class: "chip " + (p.decisive ? "must" : "tag") },
      p.level ? t("lrFrom", p.level) : "?")), note ? h("div", { class: "small muted" }, note) : null,
      p.kind === "spirit" ? lrArmourNote(p) : null),
    h("span", { class: "lr-worth" }, worth),
    p.decisive ? h("span", { class: "lr-wait" }, t("lrWaitFor")) : null);
}

function drawLeveling(card, d) {
  const head = card.querySelector("h3");
  const edit = (label, cls) => h("button", { class: cls, onclick: () => levelingWizard(d, (nd) => { state.cache.leveling = nd; drawLeveling(card, nd); }) }, label);
  card.classList.toggle("lr-hero", !d.answers || !d.roadmap);
  if (!d.answers || !d.roadmap) {
    card.replaceChildren(head, h("div", { class: "lr-hero-body" },
      h("div", { class: "lr-hero-art", "aria-hidden": "true" }, "🗺"),
      h("div", { class: "lr-hero-text" },
        h("div", { class: "lr-hero-title" }, t("lrHeroTitle", d.ways.level)),
        h("p", { class: "small" }, t("lrIntro")),
        h("div", { class: "lr-hero-steps" }, [["⚔", "lrStep1"], ["🚩", "lrStep2"], ["🗓", "lrStep3"]].map(([ico, key], i) =>
          h("span", { class: "lr-hero-step" }, h("b", {}, `${i + 1}`), ico, " ", t(key)))),
        edit(t("lrMake"), "primary lr-hero-btn"))));
    return;
  }
  const r = d.roadmap, sw = r.switch, a = r.answers;
  const decisive = sw.parts.filter((p) => p.decisive);
  const banner = h("div", { class: "lr-switch" }, h("span", { class: "lr-flag" }, "🚩"),
    h("div", {}, h("div", { class: "lr-switch-title" }, sw.level ? t("lrSwitchAt", sw.level, lrStageName(sw.stage)) : t("lrSwitchUnknown")),
      decisive.length ? h("div", {}, t("lrBecause"), " ", decisive.map(lrReason).join("; ")) : null,
      sw.early ? h("div", { class: "small" }, t("lrEarly", sw.early.level, pct(sw.early.dps - 100),
        sw.early.without.map((n) => trName(n)).join(", ")),
        sw.early.problems.length ? " " + t("lrEarlyProblems", sw.early.level, lrProblems(sw.early.problems)) : "") : null,
      sw.snapshot && sw.snapshot.ok ? h("div", { class: "small muted", title: t("lrSnapshotHint") }, "🧪 ", t("lrChecked", sw.snapshot.level),
        sw.snapshot.attributes.length ? " " + t("lrAttrHint", lrAttributes(sw.snapshot.attributes)) : "") : null,
      r.characterLevel ? h("div", { class: "small muted" }, r.characterLevel >= (sw.level || 999) ? t("lrReady", r.characterLevel) : t("lrLeft", r.characterLevel, sw.level - r.characterLevel)) : null));
  const core = sw.parts.filter((p) => p.core);
  const extra = sw.parts.filter((p) => !p.core && p.kind === "unique" && p.defence);
  const blind = sw.parts.filter((p) => p.kind === "unique" && !p.core && !p.defence && Math.abs(p.dps) < 1 && Math.abs(p.ehp) < 1);
  const why = h("div", { class: "lr-why" }, h("div", { class: "section-title" }, t("lrWhyTitle")),
    ...core.map((p) => lrPart(p, sw.trade)), ...extra.map((p) => lrPart(p, sw.trade)),
    blind.length ? h("div", { class: "small muted" }, t("lrBlind", blind.map((p) => trItem(p.name.split(",")[0])).join(", "))) : null);
  const until = r.way.skills.filter((s) => !sw.level || s.level < sw.level || r.way.id === "build");
  const before = h("div", { class: "lr-before" }, h("span", { class: "section-title" }, t("lrUntil")),
    h("span", { class: "lr-way" }, lrWayIcon(r.way), " ", lrWayTitle(r.way)),
    ...auList("lv:before", until.slice(0, 6).map((x) => "gem:" + x.name), until.slice(0, 6).map(lrSkill), ["gem"]));
  // a section of a stage: a small label over its items
  const sec = (key, items, cls = "") => (items.length ? h("div", { class: "lr-sec " + cls },
    h("div", { class: "lr-sec-k" }, t("lrSec_" + key)), h("div", { class: "lr-sec-v" }, ...items)) : null);
  // one line, the whole text on hover
  const line = (icon, text) => h("div", { class: "lr-line", title: text }, h("span", { class: "lr-line-ico" }, icon), h("span", { class: "lr-line-t" }, text));
  const stage = (s) => {
    const to = s.switch ? sw.parts.filter((p) => p.core && !["unique", "spirit", "snapshot"].includes(p.kind)) : [];
    const lv = (part) => `lv:${s.key}:${part}`;
    const ownTree = !!auBlock(lv("tree")).list;
    const tree = s.tree.length && !ownTree && !AU.edit ? [hoverTip(h("div", { class: "lr-line pk-node" }, h("span", { class: "lr-line-ico" }, "🌳"),
      h("span", { class: "lr-line-t" }, t("lrTree", s.tree.length, trName(s.tree[0].name)))),
    () => h("div", { class: "stack" }, h("b", {}, t("lrTreeTip")), h("ol", { class: "small" }, s.tree.map((n) => h("li", {}, trName(n.name), h("span", { class: "muted" }, ` · ~${n.points}`))))))] : [];
    return h("div", { class: "lr-stage" + (s.switch ? " switch" : "") + (s.here ? " here" : ""), "data-stage": s.key },
      h("div", { class: "lr-stage-head" }, h("span", { class: "lr-mark" }, lrStageMark(s.key)),
        h("div", { class: "lr-stage-name" }, h("b", {}, lrStageName(s.key)), h("span", { class: "muted small" }, s.to ? t("lrRange", s.from, s.to) : t("lrRangeOpen", s.from))),
        s.penalty ? h("span", { class: "lr-pen" + (a.pace === "safe" ? " hard" : ""), title: t("lrResist", s.penalty) }, `🔥 ${s.penalty}%`) : null),
      s.here || s.switch ? h("div", { class: "lr-badges" }, s.here ? h("span", { class: "chip ok" }, t("lrHere")) : null,
        s.switch ? h("span", { class: "chip must" }, "🚩 " + t("lrSwitchShort", sw.level)) : null) : null,
      sec("switch", to.map((p) => h("span", { class: "lr-skill" }, gemName(p.firstName || p.name))), "lr-sec-to"),
      sec("skills", auList(lv("skills"), s.skills.map((x) => "gem:" + x.name), s.skills.map(lrSkill), ["gem"])),
      sec("gems", auList(lv("gems"), s.gems.map((g) => "gem:" + g.name), s.gems.map((g) => h("span", { class: "lr-skill" }, gemName(g.name))), ["gem", "support"])),
      sec("gear", auList(lv("gear"), [], [], ["unique", "base", "rune"])),
      sec("tree", auList(lv("tree"), s.tree.map((n) => `passive:${n.id}|${n.name}`), [], ["passive"])),
      s.supportTier.length ? h("div", { class: "lr-line muted" }, h("span", { class: "lr-line-ico" }, "🔹"), h("span", { class: "lr-line-t" }, t("lrSupportTier", s.supportTier.join(", ")))) : null,
      sec("growth", [...tree, ...s.ascendancy.map((x) => line("👑", t("lrAsc", x.trial, trName(x.name)))),
        ...s.uniques.map((u) => line(u.defence ? "🛡" : "💰", trItem(u.name.split(",")[0])))]),
      h("div", { class: "lr-rewards" }),
      auNote(lv("note"), t("auStagePh")),
      a.novice && t("lrNov_" + s.key) !== "lrNov_" + s.key ? h("div", { class: "hint" }, t("lrNov_" + s.key)) : null,
      a.novice && s.switch ? h("div", { class: "hint" }, t("lrNovSwitch")) : null);
  };
  // the track: every stage a mark on one line, where the player is and where the build begins
  const track = h("div", { class: "lr-track" }, r.stages.map((s) => h("div", { class: "lr-tick" + (s.here ? " here" : "") + (s.switch ? " switch" : ""),
    title: lrStageName(s.key) }, h("span", { class: "lr-tick-dot" }, s.switch ? "🚩" : lrStageMark(s.key)),
    h("span", { class: "lr-tick-l" }, s.to ? t("lrRange", s.from, s.to) : t("lrRangeOpen", s.from)))));
  const tips = [t(a.pace === "safe" ? "lrTipSafe" : "lrTipFast"), t(a.trade ? "lrTipTrade" : "lrTipSsf")];
  card.replaceChildren(...[head, banner, auNote("lv:intro", t("auLvIntroPh")), why, before,
    // the track and the stages in one grid, a column each: every mark stands over its stage
    h("div", { class: "lr-timeline", style: `--n:${r.stages.length}` }, track, h("div", { class: "lr-stages" }, r.stages.map(stage))),
    h("ul", { class: "small lr-tips" }, tips.map((x) => h("li", {}, x))),
    h("div", { class: "row" }, edit(t("lrEdit"), "ghost small"),
      h("span", { class: "muted small" }, t("lrAnswers", lrWayTitle(r.way), t(a.trade ? "lrTradeShort" : "lrSsfShort"), t(a.pace === "safe" ? "lrSafeShort" : "lrFastShort"))),
      h("button", { class: "link small", onclick: () => { state.openLeveling = true; switchTab("skills"); } }, t("lrMore")))].filter(Boolean));
  head.querySelector(".fold-sum")?.remove();
  if (sw.level) head.append(h("span", { class: "fold-sum" }, "🚩 " + t("lrSwitchShort", sw.level)));
  questsData().then((qd) => {  // each act's reward choice: the one to take (or taken)
    for (const q of qd.choices) {
      const pick = q.options.find((o) => o.value === q.chosen) || q.options.find((o) => o.best);
      const box = card.querySelector(`.lr-stage[data-stage="${QUEST_ACT[q.act]}"] .lr-rewards`);
      if (!pick || !box) continue;
      if (!box.childElementCount) box.append(h("div", { class: "lr-sec-k" }, t("lrSec_rewards")));
      const text = `${questName(q)}: ${optionTitle(q, q.options.indexOf(pick)) || optionText(pick)}`;
      box.append(h("div", { class: "lr-line" + (q.chosen === pick.value ? " done" : ""), title: text },
        h("span", { class: "lr-line-ico" }, q.chosen === pick.value ? "✓" : "🎁"), h("span", { class: "lr-line-t" }, text)));
    }
  }).catch(() => {});
}

// the levelling tab's line about the plan: the switch level, or where to make the plan
function levelingNote() {
  const box = h("div", { class: "action lr-note hidden" });
  DATA.leveling().then((d) => {
    if (d.ways.level < LR_MIN_GUIDE) return;
    const sw = d.roadmap && d.roadmap.switch;
    box.replaceChildren(h("span", {}, sw && sw.level ? "🚩 " + t("lrSwitchAt", sw.level, lrStageName(sw.stage)) : t("lrNoPlan")), " ",
      h("button", { class: "link small", onclick: () => switchTab("overview") }, t("lrToOverview")));
    box.classList.remove("hidden");
  }).catch(() => {});
  return box;
}

// ---------- the campaign's rewards: which to take (poe2lab.analysis.quests) ----------
// Each option of a choice priced by PoB in its place on this build; the player marks what they took, and every
// number counts it from then on (the answer is set in PoB's configuration and kept in the build profile).
const QUEST_ACT = { 1: "act1", 2: "act2", 3: "act3", 4: "act4", 5: "interlude" };
// the choices' own names: the lessons are official, the quests are named by what they give
const QUEST_OPTION_NAMES = { "Tribal Medicine": ["Kaom's Lesson", "Rakiata's Lesson"] };
const questsData = () => cached(`quests:${state.mode}`, () => api(`/api/quests?mode=${state.mode}&${buildQuery()}`));
const questName = (q) => t("qn_" + q.info.replace(/[^A-Za-z]/g, "")) === "qn_" + q.info.replace(/[^A-Za-z]/g, "") ? trName(q.info) : t("qn_" + q.info.replace(/[^A-Za-z]/g, ""));
// PoB writes some areas with capitals ("Halls Of The Dead"), the game's names do not
const questArea = (a) => (trName(a) !== a ? trName(a) : trName(a.replace(/ (Of|The|And|In)(?= )/g, (m) => m.toLowerCase())));
const questWhere = (q) => `${lrStageName(QUEST_ACT[q.act] || "maps")} · ${questArea(q.area)}`;
function optionTitle(q, i) {
  const names = QUEST_OPTION_NAMES[q.info];
  return names ? trName(names[i]) : null;
}
const optionText = (o) => o.lines.map((l) => trMod(l)).join(" · ");
const worthless = (o) => !Object.values(o.changes).some((v) => Math.abs(v) >= 0.3);

// the player's answer kept in the build profile: every number counts the reward from now on
async function saveQuest(var_, value) {
  const nd = await api(`/api/quests?mode=${state.mode}&${buildQuery()}`, { method: "POST", body: { var: var_, value } });
  resetCache();
  state.cache[`quests:${state.mode}`] = Promise.resolve(nd);
  toast(t("qSaved"), true);
  return nd;
}

function questsCard() {
  const card = h("div", { class: "card stack q-card" }, h("h3", {}, t("qTitle")), h("div", { class: "sub" }, t("qSub")),
    loading(t("qLoading")));
  const draw = (d) => {
    const head = card.querySelector("h3");
    head.querySelector(".fold-sum")?.remove();
    head.append(h("span", { class: "fold-sum" }, d.unchosen.length ? t("qSumOpen", d.unchosen.length) : t("qSumDone")));
    const save = async (var_, value) => {
      try { draw(await saveQuest(var_, value)); } catch (e) { toast(e.message); }
    };
    const choice = (q) => h("div", { class: "q-quest" },
      h("div", { class: "q-head" }, h("b", {}, questName(q)), h("span", { class: "muted small" }, questWhere(q)),
        q.chosen ? null : h("span", { class: "chip warn" }, t("qNotChosen"))),
      h("div", { class: "q-options" }, q.options.map((o, i) => h("button", {
        class: "q-option" + (q.chosen === o.value ? " chosen" : "") + (o.best ? " best" : ""),
        title: t("qPickHint"), onclick: () => save(q.var, q.chosen === o.value ? "None" : o.value) },
      h("div", { class: "q-opt-top" }, optionTitle(q, i) ? h("b", {}, optionTitle(q, i)) : null,
        o.best ? h("span", { class: "chip ok" }, "★ " + t("qBest")) : null,
        q.chosen === o.value ? h("span", { class: "chip tag" }, "✓ " + t("qTaken")) : null),
      h("div", { class: "small" }, optionText(o)),
      worthless(o) ? h("div", { class: "hint" }, o.blind ? t("qBlind_" + o.blind) : t("qNothing")) : deltas(o.changes, METRIC, 0.3)))));
    const fixed = d.fixed.map((f) => h("label", { class: "q-fixed" },
      h("input", { type: "checkbox", checked: f.taken, onchange: (e) => save(f.var, e.target.checked) }),
      h("span", {}, f.lines.map((l) => trMod(l)).join(" · ")), h("span", { class: "muted small" }, questWhere(f)),
      Object.values(f.changes).some((v) => Math.abs(v) >= 0.3) ? deltas(f.changes, METRIC, 0.3) : null));
    card.replaceChildren(...[head, card.querySelector(".sub"), ...d.choices.map(choice),
      h("details", {}, h("summary", { class: "small" }, t("qFixed", d.fixed.filter((f) => f.taken).length, d.fixed.length)),
        h("div", { class: "hint" }, t("qFixedHint")), h("div", { class: "stack", style: "gap:4px;margin-top:6px" }, fixed))].filter(Boolean));
  };
  questsData().then(draw).catch((e) => card.append(h("p", { class: "muted" }, e.message)));
  return foldedCard(card, "quests", null);
}

// The overview's map of the campaign's permanent stats: act by act, each reward's stat, who or what gives it, where
// and at which level, and whether the build counts it; the sum of what is taken on top. A fixed reward is marked
// taken here with a press; a choice opens the profile, where its options are compared.
const QUEST_BOSSES = new Set(["Beira", "King In The Mists", "Candlemass", "Ignagduk", "Blackjaw", "Lythara"]);
// a reward's picture by what it gives, in its colour
const QUEST_ICONS = [[/Spirit/, "spark", "var(--gold)"], [/Fire Resistance/, "fire", "var(--fire)"],
  [/Cold Resistance/, "cold", "var(--cold)"], [/Lightning Resistance/, "bolt", "var(--lightning)"],
  [/Chaos Resistance/, "chaos", "var(--chaos)"], [/Elemental Resistances/, "shield", "var(--gold)"],
  [/Mana/, "drop", "var(--mana)"], [/Life/, "heart", "var(--bad)"], [/Movement Speed/, "run", "var(--good)"],
  [/Charm|Flask/, "flag", "var(--guide)"], [/Armour|Evasion|Energy Shield|Deflection/, "shield", "var(--text-2)"],
  [/Strength|Dexterity|Intelligence|Attributes/, "person", "var(--text-2)"]];
function questIcon(text) {
  const [, id, color] = QUEST_ICONS.find(([re]) => re.test(text)) || [null, "star", "var(--muted)"];
  const svg = I(id);
  svg.style.color = color;
  return svg;
}
// the same stat from several rewards added up ("+10% to Cold Resistance" twice: +20%); a line with more than one
// number is listed as it is
function questTotals(lines) {
  const sums = new Map();
  for (const line of lines) {
    const nums = line.match(/\d+(\.\d+)?/g) || [];
    const key = nums.length === 1 ? line.replace(/\d+(\.\d+)?/, "#") : line;
    sums.set(key, (sums.get(key) || 0) + (nums.length === 1 ? Number(nums[0]) : 0));
  }
  // in the pictures' order: Spirit, the resistances, mana, life, the rest
  const rank = (line) => (QUEST_ICONS.findIndex(([re]) => re.test(line)) + 1 || QUEST_ICONS.length + 1);
  return [...sums].map(([key, n]) => (key.includes("#") ? key.replace("#", String(Math.round(n * 10) / 10)) : key))
    .sort((a, b) => rank(a) - rank(b));
}

function questMapCard() {
  const card = h("div", { class: "card stack qm-card" }, h("h3", {}, t("qmTitle")), h("div", { class: "sub" }, t("qmSub")),
    loading(t("qLoading")));
  const toggle = async (var_, value) => {
    try { await saveQuest(var_, value); switchTab(state.tab); } catch (e) { toast(e.message); }
  };
  const draw = (d) => {
    const all = [...d.fixed, ...d.choices].sort((a, b) => a.act - b.act || a.level - b.level);
    const taken = (q) => (q.options ? !!q.chosen : q.taken);
    const tile = (q) => {
      const pick = q.options && (q.options.find((o) => o.value === q.chosen) || q.options.find((o) => o.best));
      const lines = q.options ? (pick ? pick.lines : []) : q.lines;
      const stat = q.options && !pick ? t("qmChoose", q.options.length) : lines.map((l) => trMod(l)).join(" · ");
      const who = QUEST_BOSSES.has(q.info) ? I("skull") : I("compass");
      return h("button", {
        class: "qm-reward" + (taken(q) ? " taken" : "") + (q.options ? " choice" : ""),
        title: q.options ? t("qmChoiceHint") : t(q.taken ? "qmUntake" : "qmTake"),
        onclick: () => (q.options ? switchTab("profile") : toggle(q.var, !q.taken)) },
      h("div", { class: "qm-stat" }, questIcon(lines.join(" ") || q.options.map((o) => o.value).join(" ")), h("b", {}, stat)),
      q.options ? h("div", { class: "qm-pick" }, q.chosen ? "✓ " + t("qmChosen", q.options.length)
        : pick ? "★ " + t("qmBestOf", q.options.length) : t("qNotChosen")) : null,
      h("div", { class: "qm-who" }, who, h("span", {}, questName(q))),
      h("div", { class: "qm-where muted small" }, questArea(q.area), " · ", t("lrLv", q.level)),
      h("span", { class: "qm-mark" }, taken(q) ? "✓" : ""));
    };
    const acts = [...new Set(all.map((q) => QUEST_ACT[q.act] || "maps"))];
    const totals = questTotals(all.filter(taken).flatMap((q) => (q.options ? q.options.find((o) => o.value === q.chosen).lines : q.lines)));
    const head = card.querySelector("h3");
    head.querySelector(".fold-sum")?.remove();
    head.append(h("span", { class: "fold-sum" }, t("qmSum", all.filter(taken).length, all.length)));
    card.replaceChildren(...[head, card.querySelector(".sub"),
      totals.length ? h("div", { class: "qm-totals" }, h("span", { class: "lr-sec-k" }, t("qmTotal")),
        totals.map((l) => h("span", { class: "qm-total" }, questIcon(l), trMod(l)))) : null,
      h("div", { class: "qm-acts" }, acts.map((a) => h("div", { class: "qm-act" },
        h("div", { class: "qm-act-head" }, h("span", { class: "lr-mark" }, lrStageMark(a)), h("b", {}, lrStageName(a))),
        all.filter((q) => (QUEST_ACT[q.act] || "maps") === a).map(tile))))].filter(Boolean));
  };
  questsData().then(draw).catch((e) => card.append(h("p", { class: "muted" }, e.message)));
  return card;
}

// the best reward not marked yet, for "what to do next": the one worth most for the goal
async function questStep() {
  const d = await questsData();
  const open = d.choices.filter((q) => !q.chosen).map((q) => [q, q.options.find((o) => o.best)]).filter(([, o]) => o);
  open.sort((a, b) => b[1].score - a[1].score);
  return open[0] || null;
}

// the four questions, one screen each, as tiles; nothing is asked unless the player presses the button
function levelingWizard(d, done) {
  const a = { trade: true, pace: "fast", novice: false, ...(d.answers || {}) };
  if (!a.way || !d.ways.ways.some((w) => w.id === a.way)) a.way = (d.ways.ways[0] || {}).id;
  let step = 0;
  const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); close(); } };
  const close = () => { back.remove(); document.removeEventListener("keydown", onKey, true); };
  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) close(); } });
  const box = h("div", { class: "ask card stack lr-wizard", role: "dialog", "aria-modal": "true" });
  back.append(box);
  const tile = (on, pick, ico, title, ...more) => h("button", { class: "lr-tile" + (on ? " active" : ""), onclick: () => { pick(); next(); } },
    h("span", { class: "lr-tile-ico" }, ico), h("b", {}, title), ...more);
  const choice = (key, options) => h("div", { class: "lr-tiles two" }, options.map(([value, ico, title, sub]) =>
    tile(a[key] === value, () => { a[key] = value; }, ico, title, h("span", { class: "small muted" }, sub))));
  const screens = [
    () => [h("h3", {}, t("lrQWay", trName(d.ways.class))), h("div", { class: "small muted" }, t("lrQWaySub")),
      h("div", { class: "lr-tiles" }, d.ways.ways.map((w) => tile(a.way === w.id, () => { a.way = w.id; }, lrWayIcon(w), lrWayTitle(w),
        h("span", { class: "lr-tile-skills" }, w.skills.slice(0, 3).map((s) => gemHover(h("span", {}, icon(s.name) || trName(s.name)), s.name))),
        h("span", { class: "small muted" }, t("lrFromLevel", w.from)),
        w.id !== "build" && w.likeBuild ? h("span", { class: "chip ok" }, t("lrLike")) : w.id !== "build" && w.sameWeapon ? h("span", { class: "chip tag" }, t("lrSameWeapon")) : null)))],
    () => [h("h3", {}, t("lrQTrade")), choice("trade", [[true, "🛒", t("lrTrade"), t("lrTradeSub")], [false, "🎒", t("lrSsf"), t("lrSsfSub")]])],
    () => [h("h3", {}, t("lrQPace")), choice("pace", [["fast", "⚡", t("lrFast"), t("lrFastSub")], ["safe", "🛡", t("lrSafe"), t("lrSafeSub")]])],
    () => [h("h3", {}, t("lrQNovice")), choice("novice", [[true, "🌱", t("lrNovice"), t("lrNoviceSub")], [false, "🎯", t("lrExpert"), t("lrExpertSub")]])],
  ];
  const draw = () => box.replaceChildren(...screens[step](),
    h("div", { class: "row lr-nav" }, step ? h("button", { class: "ghost small", onclick: () => { step--; draw(); } }, t("lrBack")) : null,
      h("span", { class: "lr-dots" }, screens.map((_, i) => h("span", { class: i === step ? "on" : "" }))),
      h("button", { class: "ghost small", onclick: close }, t("cancel"))));
  async function next() {
    if (++step < screens.length) { draw(); return; }
    box.replaceChildren(loading(t("lrLoading")));
    try {
      const nd = await api(`/api/leveling?${buildQuery()}`, { method: "POST", body: a });
      close();
      done(nd);
    } catch (e) { close(); toast(e.message); }
  }
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
  draw();
}

// ---------- mechanics ----------
// ---------- skills: each skill with its gems and the links between skills; the gem order while levelling ----------
TABS.skills = async (view) => {
  const body = h("div", { class: "stack" }, loading(t("skLoading")));
  view.replaceChildren(body);
  let r;
  try {
    r = await DATA.skills("build");
  } catch (e) {
    body.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message)));
    return;
  }
  // under the skills, folded: what the damage is made of, and the gems while levelling (counted when opened)
  const damage = h("div", { class: "stack" }, loading(t("calcReport")));
  report().then((rep) => damage.replaceChildren(...renderDamage(rep)))
    .catch((e) => damage.replaceChildren(h("p", { class: "muted" }, e.message)));
  const explained = h("div", { class: "grid two masonry" }, loading(t("exLoading")));
  body.replaceChildren(...renderSkillsBuild(r), h("div", { class: "section-title" }, "🔍 ", t("exTitle")), explained,
    h("div", { class: "section-title" }, t("skDamageTitle")), damage, levelingGemsCard());
  betterSupports(body);
  DATA.skills("explain")
    .then((d) => explained.replaceChildren(...explainCards(d, d.guide)))
    .catch((e) => explained.replaceChildren(errorCard(e)));
};

// ---------- how the build works (poe2lab.analysis.explain) ----------
// the cards in order: damage first (crit, its damage, speed), mana, the meta gems, then the defences
function explainCards(d, guide) {
  return [d.charges ? chargesCard(d.charges) : null,
    d.crit && d.crit.value > 0 ? critCard(d.crit, guide) : null, d.critDamage && d.crit && d.crit.value > 0 ? critDamageCard(d.critDamage) : null,
    d.speed && d.speed.value > 0 ? speedCard(d.speed) : null, d.mana ? manaCard(d.mana) : null, ...(d.metas || []).map(metaCard),
    ...(d.defences || []).map(defenceCard)].filter(Boolean);
}
const pctOf = (v) => `${fmt(v, 1)}%`;
// where a modifier comes from, by name: a passive, the ascendancy, a jewel, an item, a gem
function exSource(x) {
  const name = x.kind === "item" || x.kind === "jewel" ? trItem(x.name.split(",")[0]) : x.kind === "gem" ? gemName(x.name) : trName(x.name);
  return h("span", {}, name, x.count > 1 ? h("span", { class: "muted" }, ` ×${x.count}`) : "",
    h("span", { class: "muted small" }, " · ", t("exKind_" + (x.kind === "tree" && x.small ? "small" : x.kind))));
}
const exConds = (x) => x.conds.map((c) => h("span", { class: "chip warn", title: c }, t("exIf", conditionLabel(c).replace(/\?\s*$/, ""))));

// one stat as PoB makes it: a formula (when it gives PoB's number), the base, "increased" by source, "more", and the
// conditions it stands on; `fmtV` writes the stat's values
function bdCard(icon, title, b, { formula, baseLine, extra, fmtV, key, sum }) {
  return foldedCard(h("div", { class: "card ex-card" }, h("h3", {}, icon, " ", title),
    b.exact && formula ? h("div", { class: "ex-formula" }, formula) : null,
    baseLine ? h("div", { class: "small muted" }, baseLine) : null,
    b.inc.length ? h("table", { class: "ex-table" }, h("tbody", {}, b.inc.map((x) => h("tr", {}, h("td", {}, exSource(x), " ", exConds(x)),
      h("td", { class: "num" }, `${x.value > 0 ? "+" : ""}${fmt(x.value)}%`))),
      b.incRest ? h("tr", {}, h("td", { class: "muted small" }, t("exMore", b.incRest)), h("td", {})) : null)) : null,
    b.more.length ? h("div", { class: "small" }, h("b", {}, t("exMoreTitle")), " ",
      b.more.map((x, i) => [i ? " · " : "", exSource(x), ` ×${fmt(1 + x.value / 100, 2)}`, " ", exConds(x)])) : null,
    ...b.without.map((w) => h("div", { class: "hint" }, "⚠ ", t("exWithout", conditionLabel(w.label).replace(/\?\s*$/, ""), fmtV(w.value), pct(w.dps)))),
    extra || null),
  key, sum);
}

// the main skill's crit chance
function critCard(c, guide) {
  const adds = c.adds.reduce((a, x) => a + x.value, 0);
  return bdCard("🎯", t("exCritTitle", trName(c.skill), pctOf(c.value)), c, {
    formula: t("exCritFormula", pctOf(c.base + adds), fmt(c.incTotal), fmt(c.moreTotal, 2), pctOf(c.value)),
    baseLine: [c.weapon ? t("exCritBaseWeapon", pctOf(c.base), trItem(c.weapon.split(",")[0])) : t("exCritBaseSkill", pctOf(c.base)),
      adds ? " " + t("exCritAdds", pctOf(adds), c.adds.map((x) => trName(x.name)).join(", ")) : ""].join(""),
    extra: guide && guide.crit ? h("div", { class: "small muted" }, t("exGuideCrit", trName(guide.skill), pctOf(guide.crit))) : null,
    fmtV: pctOf, key: "ex-crit", sum: pctOf(c.value) });
}

// A main skill that spends charges on use (poe2lab.analysis.explain.charges), any skill and any charge: what one
// use deals at each count of them, as bars; how many there can be and from what, what makes them and how often, what
// else spends them, the supports that put a condition on its use. PoB's DPS of it is one use repeated without a
// break, which such a skill is not: one use is what counts.
function chargesCard(c) {
  const kind = t("lrMech_" + c.kind).toLowerCase();
  const most = Math.max(...c.steps.map((x) => x.damage), 1);
  const last = c.steps[c.steps.length - 1];
  const often = ([lo, hi]) => {
    const one = (v) => (v <= 0 ? t("exChNever") : v >= 1 ? t("exChPerSec", fmt(v, 1)) : t("exChEvery", fmt(1 / v, 1 / v < 10 ? 1 : 0)));
    return Math.abs(hi - lo) <= 0.05 * Math.max(lo, hi) ? one(lo) : `${one(lo)} – ${one(hi)}`;
  };
  const steps = h("div", { class: "ch-steps" }, c.steps.map((x) => h("div", { class: "ch-step" + (x.charges === c.now ? " now" : "") },
    h("span", { class: "ch-n" }, t("exChCharges", x.charges)),
    h("span", { class: "ch-bar" }, h("i", { style: `width:${Math.max(2, (x.damage / most) * 100)}%` })),
    h("span", { class: "ch-v" }, t("exChHits", fmt(x.hits)), " · ", h("b", {}, fmt(x.damage))),
    x.charges === c.now ? chip("tag", t("exChNow")) : null)));
  const from = c.maxFrom.map((x) => `${x.name === "Base" ? t("exChBase") : x.kind === "item" ? trItem(x.name.split(",")[0]) : trName(x.name)} +${fmt(x.value)}`).join(", ");
  const makers = [
    ...c.makers.map((m) => h("div", { class: "small" }, "• ", m.meta && m.rate
      ? t("exChMakerMeta", trName(m.skill), trName(m.meta), often(m.rate.boss), often(m.rate.pack))
      : t("exChMakerSelf", trName(m.skill)))),
    ...c.lines.map((l) => h("div", { class: "small" }, "• ", trMod(l.line), h("span", { class: "muted" }, ` (${l.from.includes(",") ? trItem(l.from.split(",")[0]) : trName(l.from)})`)))];
  return foldedCard(h("div", { class: "card ex-card" }, h("h3", {}, "🔁 ", t("exChTitle", trName(c.skill), kind)),
    // more hits per charge; or more damage with each; or PoB counts only "charges or none" (what each further one
    // gives is the skill's description's, which PoB does not count)
    h("div", { class: "ex-formula" }, c.perCharge ? t("exChHow", fmt(c.perCharge), kind)
      : c.steps.length > 2 && last.damage > c.steps[1].damage * 1.01 ? t("exChHowDamage", kind)
      : c.steps.length > 1 ? t("exChFlat", kind, fmt(c.steps[1].damage / Math.max(c.steps[0].damage, 1), 2)) : t("exChHowDamage", kind)),
    steps,
    c.speed > 0 ? h("div", { class: "hint" }, t("exChPobDps", fmt(c.speed, 1))) : null,
    h("div", { class: "small" }, t("exChMax", fmt(c.max)), from ? h("span", { class: "muted" }, ` — ${from}`) : null),
    makers.length ? h("div", { class: "stack", style: "gap:2px" }, h("b", { class: "small" }, t("exChMakers", kind)), ...makers)
      : h("div", { class: "small neg-text" }, t("exChNone", kind)),
    c.spenders.length ? h("div", { class: "small" }, "⚠ ", t("exChSpenders", c.spenders.map(trName).join(", "), kind)) : null,
    c.conditions.length ? h("div", { class: "small" }, "⚠ ", t("exChCondition"), " ", c.conditions.map((n, i) => [i ? ", " : "", gemName(n)])) : null),
  "ex-charges", t("exChSum", fmt(last.hits), fmt(last.damage)));
}

// what a crit deals over a normal hit
function critDamageCard(c) {
  const base = c.adds.reduce((a, x) => a + x.value, 0);
  return bdCard("💥", t("exCritDmgTitle", trName(c.skill), fmt(c.value, 2)), c, {
    formula: t("exCritDmgFormula", fmt(base), fmt(c.incTotal), fmt(c.moreTotal, 2), fmt(c.bonus)),
    baseLine: t("exCritDmgBase", fmt(base)), fmtV: (v) => `×${fmt(v, 2)}`, key: "ex-critdmg", sum: `×${fmt(c.value, 2)}` });
}

// how often the main skill is used
function speedCard(c) {
  return bdCard("⏱", t("exSpeedTitle", trName(c.skill), fmt(c.value, 2)), c, {
    formula: t("exSpeedFormula", fmt(c.base, 2), fmt(c.incTotal), fmt(c.moreTotal, 2), fmt(c.value, 2)),
    baseLine: c.base ? (c.weapon ? t("exSpeedBaseWeapon", fmt(c.base, 2), trItem(c.weapon.split(",")[0])) : t("exSpeedBaseSpell", fmt(c.base, 2))) : null,
    fmtV: (v) => fmt(v, 2), key: "ex-speed", sum: `${fmt(c.value, 2)}/${t("exSec")}` });
}

// the character's life, energy shield, evasion, armour: the gear's own first
function defenceCard(d) {
  const adds = d.adds.reduce((a, x) => a + x.value, 0);
  return bdCard("🛡", t("exDefTitle_" + d.stat, fmt(d.value)), d, {
    formula: t("exDefFormula", fmt(d.base), fmt(d.incTotal), fmt(d.moreTotal, 2), fmt(d.value)),
    baseLine: [d.gear.length ? t("exDefGear", d.gear.map((g) => `${slotName(g.slot)} ${fmt(g.value)}`).join(", ")) : "",
      adds ? " " + t("exDefAdds", fmt(adds), d.adds.map((x) => x.kind === "item" ? trItem(x.name.split(",")[0]) : trName(x.name)).join(", ")) : ""].join(""),
    fmtV: (v) => fmt(v), key: "ex-def-" + d.stat, sum: fmt(d.value) });
}

// how the main skill's mana comes and goes, why leech takes little, and what fixes it
function manaCard(m) {
  const leechTypes = [...new Set(m.leechFrom.map((x) => x.type))];
  const shares = Object.entries(m.shares).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${t("dmgFull_" + k).toLowerCase()} ${fmt(v)}%`).join(", ");
  const leechShare = leechTypes.reduce((a, k) => a + (k === "All" ? 100 : k === "Elemental" ? (m.shares.Fire || 0) + (m.shares.Cold || 0) + (m.shares.Lightning || 0) : m.shares[k] || 0), 0);
  const viaElemental = m.flags.includes("ManaLeechBasedOnElementalDamage");
  return foldedCard(h("div", { class: "card ex-card" }, h("h3", {}, "💧 ", t("exManaTitle", trName(m.skill), `${m.net >= 0 ? "+" : ""}${fmt(m.net)}`)),
    h("div", { class: "ex-formula" }, t("exManaFlow", fmt(m.spent), fmt(m.cost), fmt(m.regen), fmt(m.leech), fmt(m.leechMax))),
    m.net < 0 && m.lasts ? h("div", { class: "small" }, t("exManaLasts", fmt(m.lasts, m.lasts < 10 ? 1 : 0), fmt(m.pool))) : null,
    m.bursts ? h("div", { class: "hint" }, t("exManaBursts")) : null,
    m.leechFrom.length ? h("div", { class: "small" }, t("exLeechFrom", m.leechFrom.map((x) => `${trItem(x.from.split(",")[0])} ${fmt(x.value, 1)}%`).join(", "),
      leechTypes.map((k) => t("exLeechType_" + k)).join(", ")),
      shares ? " " + t("exHitMade", shares) : "",
      !viaElemental && leechShare < 50 && m.leech < m.leechMax * 0.9 ? h("b", {}, " " + t("exLeechLow", fmt(leechShare))) : "",
      viaElemental ? " " + t("exLeechElemental") : "") : h("div", { class: "small" }, t("exNoLeech")),
    m.fixes.length ? h("div", { class: "stack" }, h("b", { class: "small" }, t("exFixes")),
      ...m.fixes.map((f) => h("div", { class: "row small" }, gemName(f.name), h("b", { class: "pos" }, t("exFixMana", `+${fmt(f.mana)}`)),
        h("span", { class: "muted" }, t("exFixNet", `${f.net >= 0 ? "+" : ""}${fmt(f.net)}`)),
        Math.abs(f.dps) >= 0.5 ? deltas({ dps: f.dps }, METRIC, 0.5) : null,
        f.lineage ? chip("warn", t("exLineage")) : null, f.life ? chip("tag", t("exLifeCost")) : null))) : null),
  "ex-mana", `${m.net >= 0 ? "+" : ""}${fmt(m.net)}/${t("exSec")}`);
}

// a meta gem (or a skill triggered on crit): what fills it, how often it goes off, what it gives the main skill
function metaCard(x) {
  const range = ([a, b]) => (Math.abs(b - a) <= 0.05 * Math.max(a, b) ? fmt(a, 1) : `${fmt(a, 1)}–${fmt(b, 1)}`);
  const rangeInt = ([a, b]) => (Math.abs(b - a) <= 0.05 * Math.max(a, b) ? fmt(a) : `${fmt(a)}–${fmt(b)}`);
  const e = x.energy;
  return foldedCard(h("div", { class: "card ex-card" }, h("h3", {}, "⚡ ", gemName(x.gem)),
    ...(x.fed || []).map((f) => h("div", { class: "small" }, t("exMetaFed", t("trgEvent_" + f.event), trName(f.skill), fmt(f.perSecond, 1)))),
    e ? h("div", { class: "small" }, t("exMetaEnergy", Object.entries(e.gains).map(([k, v]) => `${t("trgEvent_" + k).toLowerCase()} ${fmt(v, 2)}`).join(", "),
      fmt(e.gem), fmt(e.supports), fmt(e.passives), fmt(e.more, 2), fmt(x.multiplier, 2))) : null,
    x.cost ? h("div", { class: "small" }, t("exMetaCost", fmt(x.cost))) : null,
    x.rate ? h("div", {}, h("b", {}, t("trgRate", range(x.rate.boss), range(x.rate.pack)))) : null,
    ...x.gives.map((g) => h("div", { class: "small" }, "→ ", t("exMetaGives", trName(g.skill), t("lrMech_" + g.mechanic)),
      g.dps != null ? h("b", {}, " " + t("exMetaWithout", pct(g.dps))) : "")),
    ...x.skills.filter((s) => s.dps).map((s) => h("div", { class: "small" }, t("trgDps", trName(s.name), rangeInt(s.dps.boss), rangeInt(s.dps.pack)))),
    x.spirit ? h("div", { class: "small muted" }, t("exMetaSpirit", x.spirit)) : null,
    x.unknown && x.unknown.length ? h("div", { class: "small muted" }, t("trgUnknown", x.unknown.map((k) => t("trgEvent_" + k)).join(", "))) : null,
    h("div", { class: "hint" }, t("trgHint"))),
  "ex-meta-" + x.gem, x.rate ? `${range(x.rate.boss)}/${t("exSec")}` : null);
}

// Supports worth more than each skill's weakest one, among those the character can have now (loaded after the
// page is shown: PoB tries every support on every skill): a line in each skill's card.
function betterSupports(root) {
  DATA.skills("supports").then((d) => {
    for (const x of d.skills) {
      const card = root.querySelector(`.sk-group[data-group="${x.group}"]`);
      if (!card) continue;
      // the weakest by damage may be there for defence or a mechanic PoB does not count: said, not hidden
      const blind = Math.abs(x.weakestWorth) < 0.5;
      const more = card.querySelector(".sk-more");
      card.insertBefore(h("div", { class: "sk-better sk-better-line", title: t("skBetterHint") },
        h("b", {}, "💡 "), h("span", { class: "muted small" },
          t("skBetterInstead", trName(x.weakest), pct(x.weakestWorth)),
          x.weakestEhp >= 0.5 ? " " + t("skBetterDefends", pct(x.weakestEhp)) : blind ? " " + t("skBetterBlind") : "", ":"),
        ...x.better.map((b) => h("span", { class: "sk-better-gem" }, gemName(b.name), " ", h("b", { class: "pos" }, pct(b.net))))), more);
    }
  }).catch(() => {});
}

// The gems while levelling, as the game shows them (renderSkillsLeveling): a folded card, counted the first time it
// is opened - it tries every support on every skill. "More" on the levelling card opens it.
function levelingGemsCard() {
  const inner = h("div", { class: "stack" });
  const card = foldedCard(h("div", { class: "card" }, h("h3", {}, "💎 ", t("skLevelingTitle")), inner), "leveling-gems",
    t("skLevelingSum"));
  let loaded = false;
  const load = async () => {
    if (loaded) return;
    loaded = true;
    inner.replaceChildren(loading(t("skLoadingLevel")));
    try {
      const r = await DATA.skillsLeveling();
      inner.replaceChildren(levelingNote(), ...renderSkillsLeveling(r));
    } catch (e) {
      inner.replaceChildren(h("p", { class: "muted" }, e.message),
        of ? h("button", { class: "ghost small", onclick: () => { state.levelOf = "build"; switchTab("skills"); } }, t("lvByBuild")) : null);
    }
  };
  // opened by the player, by "More" on the levelling card, or remembered open
  whenOpen(card, load, () => {
    if (!state.openLeveling) return;
    state.openLeveling = false;
    if (card.classList.contains("collapsed")) card.querySelector("h3").click();
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  return card;
}

// Run `load` once a folded card is open - remembered open, or opened by a click; `ready` first, once the card is
// on the page and folded. Timers, not animation frames: a hidden page gets none of those.
function whenOpen(card, load, ready) {
  const head = card.querySelector("h3");
  head.addEventListener("click", () => setTimeout(() => { if (!card.classList.contains("collapsed")) load(); }, 0));
  const check = (n) => {
    if (!card.isConnected || !card.dataset.fold) {
      if (n < 100) setTimeout(() => check(n + 1), 50);
      return;
    }
    if (ready) ready();
    if (!card.classList.contains("collapsed")) load();
  };
  setTimeout(() => check(0), 0);
}

// ---------- the ascendancy and the taken notables (cards of the Tree tab) ----------
const treeGraph = () => cached("tree-graph", () => api(`/api/tree/graph?${buildQuery()}`));
const ascData = () => cached(`asc:${state.mode}`, () => api(`/api/ascendancy?mode=${state.mode}&${buildQuery()}`));

// a node's name with its own picture (the tree graph knows every node's, ascendancy ones included)
function graphNodeName(graph) {
  const pics = new Map(graph.nodes.map((n) => [n.id, n.img]));
  return (n) => h("span", { class: "named", title: n.name },
    pics.get(n.id) ? h("img", { class: "ico passive", src: `/icons/${pics.get(n.id)}`, alt: "" }) : icon(n.name, "ico passive"),
    h("b", {}, trName(n.name)));
}

function ascendancyCard(asc, graph) {
  const nodeName = graphNodeName(graph);
  // the best set of notables the points left buy (PoB tried the combinations together)
  const byNode = new Map(graph.nodes.map((n) => [n.id, n]));
  // a notable that grants or triggers a skill: PoB does not count that skill's damage, the worth is too low
  const skillBlind = (n) => (n.stats || []).some((l) => /^(Grants Skill:|Trigger )/.test(l))
    ? h("div", { class: "hint" }, t("psSkillBlind")) : null;
  const planBox = (plan, left) => (plan ? h("div", { class: "ps-plan" },
    h("div", {}, h("b", {}, t("psPlanTitle", plan.points, left)), " ", h("span", { class: "muted small" }, t("psPlanWorth", fmt(plan.value, 1), plan.points))),
    h("div", { class: "ps-plan-nodes" }, plan.ids.map((id, i) => [i ? h("span", { class: "muted" }, " + ") : null,
      nodeName(byNode.get(id) || { id, name: plan.names[i] })])),
    deltas(plan.changes, METRIC, 0.3),
    h("div", { class: "hint" }, t("psPlanHint", plan.path.length))) : null);

  // no ascendancy yet: every ascendancy of the class, its notables priced on the build, to choose from
  const choiceMax = Math.max(0.01, ...(asc.choices || []).flatMap((c) => c.notables.map((n) => n.value)));
  if ((asc.choices || []).length) {
    return h("div", { class: "card" }, h("h3", {}, t("psNoAscTitle", trName(asc.class))),
      h("div", { class: "sub" }, t("psNoAscSub")),
      asc.choices.map((c) => h("details", { class: "ps-choice", open: c === asc.choices[0] },
        h("summary", {}, h("b", {}, trName(c.name)), " ", h("span", { class: "muted small" }, t("psChoiceWorth", fmt(c.worth, 1)))),
        planBox(c.plan, asc.maxPoints),
        h("table", { class: "versus-items" }, h("tbody", {}, c.notables.map((n) => h("tr", {},
          h("td", {}, nodeName(n), stats(n.stats), fitChips(n.fit),
            n.value <= 0.05 ? h("div", { class: "hint" }, t("psAscNoValue")) : skillBlind(n)),
          h("td", {}, scoreBar(n.value, choiceMax)),
          h("td", {}, deltas(n.changes, METRIC, 0.3)))))))));
  }
  const maxValue = Math.max(0.01, ...asc.options.map((o) => o.value));
  return h("div", { class: "card" }, h("h3", {}, t("psAscTitle", trName(asc.ascendancy) || t("psNoAsc"))),
    h("div", { class: "sub" }, t("psAscPoints", asc.points, asc.maxPoints), asc.points >= asc.maxPoints ? " " + t("psAscFull") : ""),
    planBox(asc.plan, asc.maxPoints - asc.points),
    asc.taken.length ? h("div", { class: "ps-list" }, asc.taken.map((n) => h("div", { class: "ps-node taken" },
      nodeName(n), stats(n.stats)))) : null,
    asc.options.length ? h("details", { style: "margin-top:12px" }, h("summary", {}, t("psAscOptions", asc.options.length)),
      h("table", { class: "versus-items" }, h("tbody", {}, asc.options.map((o) => h("tr", {},
        h("td", {}, nodeName(o), stats(o.stats), fitChips(o.fit),
          o.via.length ? h("div", { class: "hint" }, t("via", o.via.map(trName).join(", "))) : null,
          o.value <= 0.05 ? h("div", { class: "hint" }, t("psAscNoValue")) : skillBlind(o)),
        h("td", { class: "num" }, t("pointsN", o.points)),
        h("td", {}, scoreBar(o.value, maxValue)),
        h("td", {}, deltas(o.changes, METRIC, 0.3))))))) : null);
}

function takenCard(graph) {
  const nodeName = graphNodeName(graph);
  const taken = graph.nodes.filter((n) => n.alloc && !n.asc && (n.type === "Notable" || n.type === "Keystone"))
    .sort((a, b) => (b.type === "Keystone") - (a.type === "Keystone") || trName(a.name).localeCompare(trName(b.name)));
  return taken.length ? h("div", { class: "card" }, h("details", {}, h("summary", {}, t("psTaken", taken.length)),
    h("div", { class: "sub", style: "margin-top:8px" }, t("psTakenSub", graph.points)),
    h("div", { class: "ps-list" }, taken.map((n) => h("div", { class: "ps-node" + (n.type === "Keystone" ? " keystone" : "") },
      nodeName(n), stats(n.stats)))))) : null;
}

// The passive tree drawn from PoB's own layout: allocated nodes in gold, the best growth options and the road to
// them in green, respec candidates outlined in red; the main tree and the ascendancy apart. Wheel zooms, drag pans,
// hovering a node shows what it gives.
// opts.packages: the mechanics' packages, shown with the hints; opts.focus: one package alone, to see and take
function openTreeViewer(graph, tree, asc, opts = {}) {
  const css = getComputedStyle(document.documentElement);
  const col = (name, fallback) => (css.getPropertyValue(name) || fallback).trim();
  // taken: gold on the main tree, red and green in weapon set I and II (PoB's colours); hints blue, respec violet
  const C = { gold: col("--gold", "#d6a54f"), hint: "#4da3ff", respec: "#b57bff", ws: [null, "#e5484d", "#3ecf74"],
    line: "rgba(153,161,174,.28)", node: "#2b303a", nodeEdge: "rgba(153,161,174,.55)", bg: col("--bg", "#0f1115") };
  // the ascendancy: the plan (the best set of notables the points left buy) counts as growth, with its road; the
  // other notables PoB values are "useful" (pale); with no points left, every option worth something is growth
  let planned, growth, road, useful, worth, respec;
  // the green suggestions can be switched off (remembered in this browser): the sets drawn are then empty
  let hints = true;
  try { hints = localStorage.getItem("poe2lab.treeHints") !== "off"; } catch { /* no storage: shown */ }
  let full = null;
  // a package opened to be seen shows whatever the switch says
  const applyHints = () => {
    ({ planned, growth, road, useful } = hints || focus ? full : { planned: new Set(), growth: new Set(), road: new Set(), useful: new Set() });
  };
  let packs = opts.packages || [], focus = opts.focus || null;
  let packOf = new Map();  // a package's notable -> its mechanic, for the tip
  let latest = null;  // the tree analysis the hints are from (a regrow brings a newer one)
  const suggest = (tree, asc) => {
    latest = { tree, asc };
    packOf = new Map((focus ? [focus] : packs).flatMap((pk) => pk.notables.map((n) => [n.id, pk.mechanic])));
    if (focus) {
      // one package alone: its notables and their road, nothing else suggested
      planned = new Set();
      growth = new Set(focus.notables.map((n) => n.id));
      road = new Set(focus.path);
      useful = new Set();
      worth = new Map();
      respec = new Set((tree.respec || []).map((b) => b.id));
      full = { planned, growth, road, useful };
      applyHints();
      return;
    }
    const plans = asc ? [asc.plan, ...(asc.choices || []).map((c) => c.plan)].filter(Boolean) : [];
    const ascUseful = asc ? [...(asc.options || []), ...(asc.choices || []).flatMap((c) => c.notables)].filter((o) => o.value > 0.05) : [];
    planned = new Set(plans.flatMap((p) => p.ids));
    const ascGrowth = plans.length ? [...planned] : ascUseful.map((o) => o.id);
    growth = new Set([...(tree.growth || []).map((g) => g.id), ...ascGrowth, ...packOf.keys()]);
    road = new Set([...(tree.growth || []).flatMap((g) => g.path || []), ...plans.flatMap((p) => p.path), ...packs.flatMap((pk) => pk.path),
      ...(plans.length ? [] : ascUseful.flatMap((o) => o.path || []))]);
    useful = new Set(ascUseful.map((o) => o.id).filter((id) => !growth.has(id)));
    worth = new Map([...(tree.growth || []).map((g) => [g.id, g]), ...ascUseful.map((o) => [o.id, o])]);
    respec = new Set((tree.respec || []).map((b) => b.id));
    full = { planned, growth, road, useful };
    applyHints();
  };
  suggest(tree, asc);
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const R = { Normal: 22, Notable: 36, Keystone: 52, Socket: 30, ClassStart: 46, AscendClassStart: 46, Mastery: 30 };
  // each node's own picture (unpacked from the game), loaded once and drawn when the node is big enough to see it
  const pictures = new Map();
  const picture = (file) => {
    if (!file) return null;
    let img = pictures.get(file);
    if (!img) {
      img = new Image();
      img.onload = () => scheduleDraw();
      img.src = `/icons/${file}`;
      pictures.set(file, img);
    }
    return img.complete && img.naturalWidth ? img : null;
  };
  let queued = false;
  const scheduleDraw = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; draw(); }); } };
  // the game's art behind the tree (treeart.js): the stone background, the class circle, the ascendancy circles;
  // each picture is decoded at about the size it is seen at
  const art = graph.art || {};
  const want = (where, size) => (where && where.file ? { file: where.file, layer: where.layer, size } : null);
  const wanted = { tile: want(art.tile, 256), center: want(art.center && art.center.image, 750),
    ring: want(art.center && art.center.ring, 1000), active: want(art.center && art.center.active, 1000),
    asc: new Map((art.asc || []).map((a) => [a.name, want(a.image, 750)])) };
  if (art.version) loadTreeArt(art.version, [wanted.tile, wanted.center, ...wanted.asc.values(), wanted.ring, wanted.active], scheduleDraw);
  // the nodes' frames as the game draws them (taken, on the way, not taken) and the jewels in the sockets
  const PIC = 128;
  const frameWant = (n, state) => {
    const f = n.fr && graph.frames ? graph.frames[n.fr] : null;
    return f ? want(f[state] || f.unalloc, PIC) : null;
  };
  const loadFrames = () => {
    if (!art.version) return;
    const wants = [];
    for (const f of Object.values(graph.frames || {})) for (const st of ["alloc", "path", "unalloc"]) if (f[st]) wants.push(want(f[st], PIC));
    for (const n of graph.nodes) if (n.jewel && n.jewel.art) wants.push(want(n.jewel.art, PIC));
    loadTreeArt(art.version, wants, scheduleDraw);
  };
  loadFrames();
  // a jewel's picture: the tree's own (bases, some uniques), else the item's from the game's icons
  const jewelPicture = (j) => (j.art && treeArt(want(j.art, PIC))) || picture(ICONS[(j.name || "").split(",")[0].trim()] || ICONS[j.base]);

  // opts.embed: a box on the page the viewer lives in (full screen by its button); opts.onEdit: after an edit on it
  const embed = opts.embed || null;
  const overlay = h("div", { class: embed ? "tree-overlay embedded" : "tree-overlay" });
  const canvas = h("canvas", { class: "tree-canvas" });
  const tip = h("div", { class: "tree-tip hidden" });
  let showAsc = false, scale = 0.03, ox = 0, oy = 0, hover = null, pinned = null;
  // which tree a click takes nodes in: 0 the main one, 1 and 2 weapon set I and II (PoB's allocation mode)
  let wset = 0;
  const takenColor = (n) => (n.mode ? C.ws[n.mode] : C.gold);
  // what taking a node costs in the chosen tree (0: it cannot be taken there)
  const costOf = (n) => (wset && n.wc ? n.wc[wset - 1] : n.cost);
  // why a node cannot be taken or dropped in the chosen tree (PoB's rule for keystones and jewel sockets)
  const blocked = (n) => (!n.glob || n.asc ? null : n.alloc ? (wset && !n.mode ? t("tvWsGlobalDrop") : null)
    : wset ? t("tvWsGlobal") : n.wnear ? t("tvWsNear") : null);
  const wsSeg = h("div", { class: "segmented small-seg tv-ws", title: t("tvWsHint") }, [0, 1, 2].map((k) =>
    h("button", { class: (k === 0 ? "active" : "") + (k ? ` ws${k}` : ""), onclick: (e) => {
      wset = k;
      wsSeg.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === e.currentTarget));
      canvas.classList.toggle("ws1", k === 1);
      canvas.classList.toggle("ws2", k === 2);
      if (hover) showTip(hover, lastTip[0], lastTip[1]);
      draw();
    } }, k ? t("tvWsSet", k) : t("tvWsMain"))));
  let lastTip = [0, 0];
  const seg = h("div", { class: "segmented small-seg" }, [["main", t("tvMain")], ["asc", t("tvAsc")]].map(([k, label]) =>
    h("button", { class: k === "main" ? "active" : "", onclick: (e) => {
      showAsc = k === "asc";
      seg.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === e.target));
      hover = pinned = null;
      tip.classList.add("hidden");
      fit(); draw();
    } }, label)));
  const dot = (c, ring) => h("span", { class: "tv-dot", style: ring ? `border:2px solid ${c}` : `background:${c}` });
  let edited = false, busy = false;
  const pointsBox = h("span", { class: "tv-points" });
  const regrow = h("button", { class: "ghost small tv-regrow", title: t("tvRegrowHint"), onclick: async () => {
    if (busy) return;
    busy = true;
    regrow.disabled = true;
    regrow.textContent = t("tvRegrowing");
    try {
      const points = state.treePoints || 6;
      const [tr, as, pk] = await Promise.all([api(`/api/tree?mode=${state.mode}&points=${points}&${buildQuery()}`),
        api(`/api/ascendancy?mode=${state.mode}&${buildQuery()}`).catch(() => null),
        api(`/api/tree/packages?mode=${state.mode}&${buildQuery()}`).catch(() => null)]);
      packs = pk ? pk.packages : [];
      setFocus(null);
      suggest(tr, as);
      setHints(true);  // asked for the best growth: show it
      regrow.classList.remove("stale");
      draw();
      toast(tr.growth.length ? t("tvRegrown", tr.growth.length) : t("treeNothing"), !!tr.growth.length);
    } catch (e) { toast(e.message); }
    busy = false;
    regrow.disabled = false;
    regrow.textContent = t("tvRegrow");
  } }, t("tvRegrow"));
  const packBox = h("span", { class: "tv-pack" });
  const setFocus = (pk) => {
    focus = pk;
    if (!pk) { packBox.replaceChildren(); packBox.classList.add("hidden"); return; }
    packBox.classList.remove("hidden");
    packBox.replaceChildren(...[h("b", {}, pk.label ? `${pk.label}: ${pk.points}` : t("pkFocus", t("pk_" + pk.mechanic), pk.points)),
      pk.changes ? deltas(pk.changes, METRIC, 0.3) : null,
      pk.take === false ? null : h("button", { class: "primary small", title: t("pkTakeHint"), onclick: async () => {
        let taken = null;
        await packageFlow(pk, async (body) => {
          let r = null;
          await run(async () => { r = await api("/api/tree/package", { method: "POST", body }); });
          if (r && r.kept) taken = r;
          return r;
        });
        if (!taken) return;
        setFocus(null);
        suggest(latest.tree, latest.asc);
        await refreshGraph(null);
      } }, t("pkTake")),
      h("button", { class: "ghost small", title: t("pkAllHint"), onclick: () => { setFocus(null); suggest(latest.tree, latest.asc); setHints(true); draw(); } }, t("pkAll"))]
      .filter(Boolean));  // native replaceChildren would write a null out
  };
  const hintsBtn = h("button", { class: "ghost small tv-hints", title: t("tvHintsHint"), onclick: () => { setHints(!hints); draw(); } });
  const hintsLegend = h("span", { class: "tree-legend-part" });
  const setHints = (on) => {
    hints = on;
    try { localStorage.setItem("poe2lab.treeHints", on ? "on" : "off"); } catch { /* not remembered */ }
    applyHints();
    hintsBtn.classList.toggle("on", on);
    hintsBtn.setAttribute("aria-pressed", String(on));
    hintsBtn.textContent = on ? t("tvHintsOn") : t("tvHintsOff");
    hintsLegend.classList.toggle("hidden", !on);
  };
  const drawPoints = () => {
    const line = pointsLine(graph.budget);
    if (line) pointsBox.replaceChildren(...line.childNodes);
  };
  drawPoints();
  const detach = () => { document.removeEventListener("keydown", onKey); window.removeEventListener("resize", onResize); };
  const close = () => {
    overlay.remove(); detach();
    if (edited) { resetCache(); switchTab("tree"); }  // the tab's numbers follow the edits
  };
  const fullBtn = h("button", { class: "tree-close", title: t("tvFull"), onclick: () => setFull(!overlay.classList.contains("full")) }, "⛶");
  const setFull = (on) => {
    overlay.classList.toggle("full", on);
    fullBtn.textContent = on ? "×" : "⛶";
    fullBtn.title = on ? t("tvFullExit") : t("tvFull");
  };
  // Esc a dialog over the viewer already took (the jewel editor, a question) closes only that dialog; an embedded
  // viewer only leaves full screen; one whose page is gone stops listening
  const onKey = (e) => {
    if (!overlay.isConnected) { detach(); return; }
    if (e.key === "Escape" && !e.defaultPrevented) { if (embed) setFull(false); else close(); }
  };
  const onResize = () => { if (!overlay.isConnected) detach(); else draw(); };
  setFocus(focus);
  // a colour with its word, kept together when the legend wraps
  const key = (d, text) => h("span", { class: "tv-key" }, d, text);
  hintsLegend.append(key(dot(C.hint), t("tvGrowth")), key(dot("rgba(77,163,255,.45)"), t("tvRoad")),
    ...(full.useful.size ? [key(dot("rgba(77,163,255,.3)"), t("tvUseful"))] : []),
    h("span", { class: "muted small", title: t("tvCalloutsHint") }, t("tvCallouts")));
  setHints(hints);
  const helpBox = h("div", { class: "tv-help-box hidden" },
    h("div", { class: "tree-legend small" }, key(dot(C.gold), t("tvAlloc")), key(dot(C.ws[1]), t("tvWsSet", 1)), key(dot(C.ws[2]), t("tvWsSet", 2)),
      hintsLegend, key(dot(C.respec, true), t("tvRespec"))),
    h("div", { class: "muted small" }, t("tvHint")));
  const helpBtn = h("button", { class: "ghost small tv-help", title: t("tvHelp"), "aria-expanded": "false", onclick: () => {
    const on = helpBox.classList.toggle("hidden") === false;
    helpBtn.setAttribute("aria-expanded", String(on));
    helpBtn.classList.toggle("on", on);
  } }, "?");
  overlay.append(h("div", { class: "tree-bar" }, h("b", {}, t("tvTitle", trName(graph.class), trName(graph.ascendancy))), seg,
    wsSeg, hintsBtn, regrow, pointsBox, packBox,
    h("span", { class: "tv-help-wrap" }, helpBtn, helpBox),
    embed ? fullBtn : h("button", { class: "tree-close", title: t("tvClose"), onclick: close }, "×")), canvas, tip);
  (embed || document.body).append(overlay);
  document.addEventListener("keydown", onKey);

  // a node with no links at all is not reached by a path (sockets and notables granted otherwise): shown taken only
  const visible = () => graph.nodes.filter((n) => (showAsc ? n.asc : !n.asc) && (n.alloc || n.links.length));
  function fit() {
    const all = visible();
    const pk = focus && !showAsc ? new Set(focus.path) : null;
    const shown = pk ? all.filter((n) => pk.has(n.id)) : showAsc ? all : all.filter((n) => n.alloc || growth.has(n.id) || road.has(n.id));
    const ns = shown.length ? shown : all;
    const xs = ns.map((n) => n.x), ys = ns.map((n) => n.y);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const w = canvas.clientWidth || window.innerWidth, hgt = canvas.clientHeight || window.innerHeight;
    scale = Math.min(w / ((x1 - x0) + 800), hgt / ((y1 - y0) + 800));
    ox = w / 2 - ((x0 + x1) / 2) * scale;
    oy = hgt / 2 - ((y0 + y1) / 2) * scale;
  }
  const sx = (n) => n.x * scale + ox, sy = (n) => n.y * scale + oy;
  // a node's size on screen as PoB draws it: the icon's and the frame's radius are their widths in tree units
  // (R: nodes PoB gives no icon size); never below a dot to see and hit
  const iconR = (n) => Math.max(n.type === "Normal" ? 1.2 : 2.2, (n.sz || R[n.type] || 22) * scale);
  const frameR = (n, r = iconR(n)) => (n.sz ? ((n.fs || n.sz) / n.sz) * r : r);
  // a frame in a weapon set's colour, as PoB draws it (the picture multiplied by the colour), made once
  const tints = new Map();
  const tinted = (img, color) => {
    let byImg = tints.get(img);
    if (!byImg) { byImg = new Map(); tints.set(img, byImg); }
    let c = byImg.get(color);
    if (!c) {
      c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      const x = c.getContext("2d");
      x.drawImage(img, 0, 0);
      x.globalCompositeOperation = "multiply";
      x.fillStyle = color;
      x.fillRect(0, 0, c.width, c.height);
      x.globalCompositeOperation = "destination-in";
      x.drawImage(img, 0, 0);
      byImg.set(color, c);
    }
    return c;
  };

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, hgt = canvas.clientHeight;
    if (canvas.width !== w * dpr || canvas.height !== hgt * dpr) { canvas.width = w * dpr; canvas.height = hgt * dpr; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, w, hgt);
    // on the art the links and node rims are drawn lighter to stay readable
    const lit = drawArt(ctx, w, hgt);
    const line = lit ? "rgba(214,219,228,.42)" : C.line, edge = lit ? "rgba(226,230,238,.8)" : C.nodeEdge;
    const ns = visible();
    // links as PoB draws them: an arc of the connection's own orbit through both nodes, an arc along the orbit
    // when both nodes sit on the same orbit of one group, a straight line otherwise
    const arcTo = (cx, cy, r, from, to) => {
      const a1 = Math.atan2(from.y - cy, from.x - cx), a2 = Math.atan2(to.y - cy, to.x - cx);
      let d = a2 - a1;
      while (d > Math.PI) d -= 2 * Math.PI;
      while (d < -Math.PI) d += 2 * Math.PI;
      ctx.arc(cx * scale + ox, cy * scale + oy, r * scale, a1, a1 + d, d < 0);
    };
    for (const n of ns) {
      for (const c of n.arcs || []) {
        const m = byId.get(c.id);
        if (!m || m === n || m.asc !== n.asc || (showAsc ? !n.asc : n.asc)) continue;
        const both = n.alloc && m.alloc && (!n.mode || !m.mode || n.mode === m.mode);
        const hinted = !both && (road.has(n.id) || n.alloc) && (road.has(m.id) || m.alloc) && (road.has(n.id) || road.has(m.id));
        ctx.strokeStyle = both ? C.ws[n.mode || m.mode] || C.gold : hinted ? C.hint : line;
        ctx.lineWidth = both || hinted ? Math.max(1.5, 10 * scale) : Math.max(0.6, 5 * scale);
        ctx.beginPath();
        const r = c.orbit ? (graph.orbitRadii || [])[Math.abs(c.orbit)] : 0;
        const dx = m.x - n.x, dy = m.y - n.y, dist = Math.hypot(dx, dy);
        if (r && dist < 2 * r) {
          // the circle of radius r through both nodes, on the side the orbit's sign names (PoB's BuildConnector)
          const perp = Math.sqrt(r * r - dist * dist / 4) * (c.orbit > 0 ? 1 : -1);
          arcTo(n.x + dx / 2 + perp * (dy / dist), n.y + dy / 2 - perp * (dx / dist), r, n, m);
        } else if (!c.orbit && n.group === m.group && n.o === m.o && n.r > 0) {
          arcTo(n.gx, n.gy, n.r, n, m);
        } else {
          ctx.moveTo(sx(n), sy(n));
          ctx.lineTo(sx(m), sy(m));
        }
        ctx.stroke();
      }
    }
    for (const n of ns) {
      const x = sx(n), y = sy(n);
      const r = iconR(n);
      if (x < -r || y < -r || x > w + r || y > hgt + r) continue;  // off screen
      const status = n.alloc ? takenColor(n) : growth.has(n.id) ? C.hint : road.has(n.id) ? "rgba(77,163,255,.6)"
        : useful.has(n.id) ? "rgba(77,163,255,.3)" : null;
      const img = r >= 5 ? picture(n.img) : null;
      // the frame, at PoB's size for the node's type (sz: the icon's width, fs: the frame's), scaled to the icon
      const frame = r >= 4 ? treeArt(frameWant(n, n.alloc ? "alloc" : n === hover ? "path" : "unalloc")) : null;
      if (frame) {
        const fr = frameR(n, r);
        if (img) {
          ctx.save();
          ctx.beginPath();
          ctx.arc(x, y, r, 0, 2 * Math.PI);
          ctx.clip();
          ctx.fillStyle = C.node;
          ctx.fill();
          if (!status) ctx.filter = "brightness(0.8)";
          ctx.drawImage(img, x - r, y - r, 2 * r, 2 * r);
          ctx.restore();
        }
        ctx.drawImage(n.alloc && n.mode ? tinted(frame, C.ws[n.mode]) : frame, x - fr, y - fr, 2 * fr, 2 * fr);
        const jp = n.jewel ? jewelPicture(n.jewel) : null;
        if (jp) ctx.drawImage(jp, x - fr * 0.78, y - fr * 0.78, fr * 1.56, fr * 1.56);
        // what the frame does not say: a suggestion, a branch to respec, the node under the pointer
        const ring = respec.has(n.id) ? C.respec : n === hover || n === pinned ? "#fff"
          : !n.alloc && (growth.has(n.id) || road.has(n.id) || useful.has(n.id)) ? status : null;
        if (ring) {
          ctx.beginPath();
          ctx.arc(x, y, fr + 1.5, 0, 2 * Math.PI);
          ctx.lineWidth = n === hover || n === pinned || respec.has(n.id) ? 2 : growth.has(n.id) ? 2.5 : 1.5;
          ctx.strokeStyle = ring;
          ctx.stroke();
        }
        continue;
      }
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      if (img) {
        // the game's look: taken and suggested nodes in colour, the rest dimmed and grey
        ctx.save();
        ctx.clip();
        ctx.fillStyle = C.node;
        ctx.fill();
        if (!status) ctx.filter = "brightness(0.8)";
        ctx.drawImage(img, x - r, y - r, 2 * r, 2 * r);
        ctx.restore();
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        ctx.lineWidth = n.type === "Keystone" ? 3 : n.type === "Notable" ? 2.5 : 1.5;
        ctx.strokeStyle = respec.has(n.id) ? C.respec : n === hover || n === pinned ? "#fff" : status || edge;
        ctx.stroke();
        continue;
      }
      ctx.fillStyle = status || C.node;
      ctx.fill();
      if (n.type !== "Normal" || respec.has(n.id) || n === hover || n === pinned) {
        ctx.lineWidth = respec.has(n.id) || n === hover || n === pinned ? 2 : 1;
        ctx.strokeStyle = respec.has(n.id) ? C.respec : n === hover || n === pinned ? "#fff" : edge;
        ctx.stroke();
      }
    }
    labels(ctx);
    callouts(ctx, w, hgt);
  }

  // over each suggested node a small window: what it gives to damage (⚔) and to defence (🛡), and its place among
  // the suggestions of this view - the best one biggest (by worth per point), the rest smaller down to the last
  function callouts(ctx, w, hgt) {
    if (!hints && !focus) return;
    const defenceOf = (c) => (Math.abs(c.ehp || 0) >= 0.1 ? c.ehp
      : Math.max(c.phys_hit || 0, c.fire_hit || 0, c.cold_hit || 0, c.lightning_hit || 0, c.chaos_hit || 0, c.recovery || 0));
    const shown = visible().filter((n) => !n.alloc && growth.has(n.id) && worth.has(n.id) && worth.get(n.id).changes)
      .map((n) => ({ n, w: worth.get(n.id) }))
      .sort((a, b) => (b.w.perPoint ?? b.w.value ?? 0) - (a.w.perPoint ?? a.w.value ?? 0));
    if (!shown.length) return;
    const last = Math.max(1, shown.length - 1);
    const boxes = [];
    const placed = [];
    shown.forEach(({ n, w: v }, rank) => {
      const x = sx(n), y = sy(n);
      if (x < -60 || y < -60 || x > w + 60 || y > hgt + 60) return;
      const k = 1 - 0.4 * (rank / last);  // the best 1, the last 0.6
      const dmg = v.changes.dps || 0, def = defenceOf(v.changes);
      const parts = [];
      if (Math.abs(dmg) >= 0.1) parts.push({ text: `⚔ ${pct(dmg)}`, color: dmg > 0 ? "#ffad66" : "#ff6b6b" });
      if (Math.abs(def) >= 0.1) parts.push({ text: `🛡 ${pct(def)}`, color: def > 0 ? "#7fd8a6" : "#ff6b6b" });
      if (!parts.length) return;
      const size = Math.round(9 + 7 * k), pad = Math.round(2 + 4 * k);
      ctx.font = `600 ${size}px system-ui, sans-serif`;
      const badge = `${rank + 1}`;
      const badgeW = ctx.measureText(badge).width + pad * 1.6;
      const widths = parts.map((q) => ctx.measureText(q.text).width);
      const bw = badgeW + widths.reduce((a, b) => a + b, 0) + pad * (parts.length + 1);
      const bh = size + pad * 2;
      let bx = x - bw / 2, by = y - frameR(n) - 10 - bh;
      // above the ones already placed that it would cover
      for (let i = 0; i < 6 && placed.some((b) => bx < b.x + b.w && bx + bw > b.x && by < b.y + b.h && by + bh > b.y); i++) by -= bh + 2;
      placed.push({ x: bx, y: by, w: bw, h: bh });
      boxes.push({ x, y, bx, by, bw, bh, k, size, pad, badge, badgeW, parts, widths, top: frameR(n), first: rank === 0 });
    });
    // the worst first, so the best are drawn on top
    for (const b of boxes.reverse()) {
      ctx.save();
      ctx.globalAlpha = 0.75 + 0.25 * b.k;
      const edgeColor = b.first ? C.gold : C.hint;
      ctx.beginPath();  // a thin line down to its node
      ctx.moveTo(b.x, b.y - b.top - 2);
      ctx.lineTo(b.x, b.by + b.bh);
      ctx.lineWidth = 1;
      ctx.strokeStyle = edgeColor;
      ctx.stroke();
      ctx.beginPath();
      ctx.roundRect(b.bx, b.by, b.bw, b.bh, 6);
      ctx.fillStyle = "rgba(14, 16, 21, 0.92)";
      ctx.fill();
      ctx.lineWidth = 1 + b.k;
      ctx.strokeStyle = edgeColor;
      ctx.stroke();
      ctx.font = `700 ${b.size}px system-ui, sans-serif`;
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      const mid = b.by + b.bh / 2 + 0.5;
      ctx.beginPath();
      ctx.roundRect(b.bx + 2, b.by + 2, b.badgeW, b.bh - 4, 4);
      ctx.fillStyle = edgeColor;
      ctx.fill();
      ctx.fillStyle = "#0e1015";
      ctx.fillText(b.badge, b.bx + 2 + b.pad * 0.8, mid);
      ctx.font = `600 ${b.size}px system-ui, sans-serif`;
      let tx = b.bx + 2 + b.badgeW + b.pad;
      b.parts.forEach((q, i) => {
        ctx.fillStyle = q.color;
        ctx.fillText(q.text, tx, mid);
        tx += b.widths[i] + b.pad;
      });
      ctx.restore();
    }
  }

  function drawArt(ctx, w, hgt) {
    const tile = treeArt(wanted.tile);
    if (tile) {
      // the stone moves with the tree when it is dragged, but keeps its size when zooming (as in PoB)
      const pattern = ctx.createPattern(tile, "repeat");
      pattern.setTransform(new DOMMatrix().translate(ox % tile.width, oy % tile.height));
      ctx.fillStyle = pattern;
      ctx.fillRect(0, 0, w, hgt);
    }
    // a picture centred on a tree point; `half` is half its width in tree units (PoB's sizes)
    const place = (img, x, y, half, angle) => {
      const r = half * scale, cx = x * scale + ox, cy = y * scale + oy;
      if (!img || cx + r < 0 || cy + r < 0 || cx - r > w || cy - r > hgt) return;
      ctx.save();
      ctx.translate(cx, cy);
      if (angle) ctx.rotate(angle);
      ctx.drawImage(img, -r, -r, 2 * r, 2 * r);
      ctx.restore();
    };
    const c = art.center;
    if (!showAsc && c) {
      place(treeArt(wanted.center), c.x, c.y, c.w);
      place(treeArt(wanted.active), c.x, c.y, c.activeW, c.angle);
      place(treeArt(wanted.ring), c.x, c.y, c.ringW);
    }
    if (showAsc) for (const a of art.asc || []) place(treeArt(wanted.asc.get(a.name)), a.x, a.y, a.w);
    if (!tile) return false;
    // a veil over the art: the nodes and links stay the main thing (the ascendancy pictures are brighter)
    ctx.fillStyle = showAsc ? "rgba(8, 9, 12, 0.55)" : "rgba(8, 9, 12, 0.4)";
    ctx.fillRect(0, 0, w, hgt);
    return true;
  }

  // the ascendancies' names over their trees (several are shown while none is chosen)
  function labels(ctx) {
    if (!showAsc) return;
    const groups = new Map();
    for (const n of visible()) {
      const g = groups.get(n.asc) || { x: 0, y: 0, top: Infinity, k: 0 };
      g.x += sx(n); g.k += 1; g.top = Math.min(g.top, sy(n));
      groups.set(n.asc, g);
    }
    ctx.font = "600 15px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, .9)";
    ctx.shadowBlur = 6;
    for (const [name, g] of groups) {
      ctx.fillStyle = C.gold;
      ctx.fillText(trName(name), g.x / g.k, Math.max(20, g.top - 22));
    }
    ctx.restore();
  }

  function nodeAt(x, y) {
    let best = null, bd = Infinity;
    for (const n of visible()) {
      const d = Math.hypot(sx(n) - x, sy(n) - y), r = Math.max(6, frameR(n) + 2);
      if (d < r && d < bd) { best = n; bd = d; }
    }
    return best;
  }
  function showTip(n, x, y) {
    if (!n) { tip.classList.add("hidden"); return; }
    lastTip = [x, y];
    const tags = [n.alloc ? (n.mode ? t("tvWsSet", n.mode) : t("tvAlloc")) : null,
      packOf.has(n.id) && !n.alloc ? (packOf.get(n.id) === "guide" ? t("vsTreeTag") : t("pkTag", t("pk_" + packOf.get(n.id)))) : null,
      planned.has(n.id) ? t("tvPlan") : growth.has(n.id) && !packOf.has(n.id) ? t("tvGrowth") : null,
      road.has(n.id) && !growth.has(n.id) ? t("tvRoad") : null, useful.has(n.id) ? t("tvUseful") : null,
      respec.has(n.id) ? t("tvRespec") : null].filter(Boolean);
    const w = worth.get(n.id);
    const start = n.type === "ClassStart" || n.type === "AscendClassStart";
    const socket = n.type === "Socket" && n.alloc;
    const why = blocked(n), cost = costOf(n);
    const act = start ? null : socket ? t("tvClickJewel") : why || (n.alloc ? t("tvClickDrop", n.drop)
      : cost ? t("tvClickTake", cost) + (wset && !n.asc ? " " + t("tvWsInto", wset) : "") : t("tvUnreachable"));
    tip.replaceChildren(...[h("div", { class: "row", style: "gap:8px;align-items:center" },
      n.img ? h("img", { src: `/icons/${n.img}`, class: "tv-tip-ico", alt: "" }) : null, h("b", {}, trName(n.name) || "—")),
      tags.length ? h("div", { class: "muted small" }, tags.join(" · ")) : null,
      n.asc ? h("div", { class: "muted small" }, trName(n.asc)) : null,
      n.jewel ? h("div", { class: "tip-name r-" + (n.jewel.rarity || "normal").toLowerCase() }, "◆ ", itemTitle({ name: n.jewel.name, baseName: n.jewel.base })) : null,
      n.jewel && n.jewel.lines ? h("ul", { class: "item-lines small" }, n.jewel.lines.map((l) => h("li", {}, trMod(l)))) : null,
      n.jewel ? jewelEffect(n.jewel.effect) : null,
      stats(n.stats), w && w.changes ? h("div", { class: "small" }, h("span", { class: "muted" }, t("tvWorth", fmt(w.value, 1), w.points)), deltas(w.changes, METRIC, 0.3)) : null,
      act ? h("div", { class: "tv-act " + (why ? "warn" : n.alloc ? "neg" : "pos") }, act) : null].filter(Boolean));
    tip.classList.remove("hidden");
    const bw = overlay.clientWidth;
    tip.style.left = `${Math.min(x + 16, bw - 340)}px`;
    tip.style.top = `${y + 16}px`;
  }

  let drag = null;
  canvas.addEventListener("mousedown", (e) => { drag = { x: e.clientX, y: e.clientY, ox, oy, moved: false }; });
  window.addEventListener("mouseup", () => { drag = null; }, { once: false });
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (drag && (e.buttons & 1)) {
      ox = drag.ox + (e.clientX - drag.x); oy = drag.oy + (e.clientY - drag.y);
      drag.moved = drag.moved || Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 3;
      draw();
      return;
    }
    const n = nodeAt(x, y);
    if (n !== hover) { hover = n; draw(); }
    if (!pinned) showTip(n, e.clientX - overlay.getBoundingClientRect().left, e.clientY - overlay.getBoundingClientRect().top);
  });
  // the tree as the server has it now, after an edit (a click, a jewel, a package); `n`: the node whose tip to show
  async function refreshGraph(n, tipAt) {
    const fresh = await api(`/api/tree/graph?${buildQuery()}`);
    graph.nodes = fresh.nodes;
    graph.budget = fresh.budget;
    graph.frames = fresh.frames;
    byId.clear();
    for (const x of graph.nodes) byId.set(x.id, x);
    edited = true;
    if (opts.onEdit) opts.onEdit();
    delete state.cache.plan;  // the strip of the plan's edits follows the tree's
    renderPlanStrip();
    regrow.classList.add("stale");  // the hints were for the tree before this edit
    loadFrames();
    drawPoints();
    hover = n ? byId.get(n.id) || null : null;
    if (hover) showTip(hover, ...tipAt);
    draw();
  }
  // one edit at a time: the tree is busy until the server answers
  async function run(fn) {
    busy = true;
    canvas.classList.add("busy");
    try { await fn(); } catch (err) { toast(err.message); }
    busy = false;
    canvas.classList.remove("busy");
  }
  // a click as in PoB: a node not taken is taken with the path to it, a taken one goes with what hangs on it
  canvas.addEventListener("click", async (e) => {
    if ((drag && drag.moved) || busy) return;
    const rect = canvas.getBoundingClientRect(), at = overlay.getBoundingClientRect();
    const n = nodeAt(e.clientX - rect.left, e.clientY - rect.top);
    const why = n && !(n.type === "Socket" && n.alloc) ? blocked(n) : null;
    if (why) { toast(why); return; }
    if (!n || n.type === "ClassStart" || n.type === "AscendClassStart" || (!n.alloc && !costOf(n))) {
      pinned = n && n !== pinned ? n : null;
      showTip(pinned || n, e.clientX - at.left, e.clientY - at.top);
      draw();
      return;
    }
    const tipAt = [e.clientX - at.left, e.clientY - at.top];
    const refresh = () => refreshGraph(n, tipAt);
    if (n.type === "Socket" && n.alloc) {
      await run(async () => {
        const socket = (await api(`/api/jewels?${buildQuery()}`)).sockets.find((s) => s.node === n.id);
        if (!socket) return;
        tip.classList.add("hidden");
        jewelEditor(socket, {
          after: (path, body) => run(async () => { await api(path, { method: "POST", body }); await refresh(); }),
          dropCount: n.drop,
          drop: async () => {
            // more than the socket hangs on it: say so first, a click must not take half the tree unawares
            if (n.drop > 1 && !(await confirmInPage(t("tvDropSocketAsk", n.drop - 1), t("jwDropSocket", n.drop)))) return;
            run(async () => { await api("/api/tree/remove", { method: "POST", body: { id: n.id, name: n.name } }); await refresh(); });
          },
        });
      });
      return;
    }
    await run(async () => {
      await api(`/api/tree/${n.alloc ? "remove" : "add"}`, { method: "POST", body: { id: n.id, name: n.name, set: wset } });
      await refresh();
    });
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
    const k = Math.exp(-e.deltaY * 0.0015);
    ox = x - (x - ox) * k; oy = y - (y - oy) * k; scale *= k;
    draw();
  }, { passive: false });
  window.addEventListener("resize", onResize);
  // drawn once it has a size (an embedded viewer is laid out after the tab is put on the page), again on each change
  let sized = false;
  new ResizeObserver(() => {
    if (!canvas.clientWidth || !canvas.clientHeight) return;
    if (!sized) { sized = true; fit(); }
    draw();
  }).observe(canvas);
}

// A gem's name; the pointer over it shows the gem as the game describes it (once the build's skills are read), the
// same card on every tab. Its English name is there too, to search the trade site or a guide.
const GEM_TIPS = new Map();
// every gem of the game (/api/gems, read once): the card of a gem the open build does not have
const GEM_ALL = new Map();
let gemAllLoading = null;
function loadAllGems() {
  if (!gemAllLoading) {
    gemAllLoading = api("/api/gems").then((list) => { for (const g of list) if (!GEM_ALL.has(g.name)) GEM_ALL.set(g.name, g); })
      .catch(() => { gemAllLoading = null; });
  }
  return gemAllLoading;
}
function gemTipCard(name, note) {
  const gem = GEM_TIPS.get(name) || GEM_ALL.get(name);
  if (!gem && !note && (LANG === "en" || trName(name) === name)) return null;  // nothing to add to the name
  const lines = gem ? (LANG !== "en" && gem.linesLocal && gem.linesLocal.length ? gem.linesLocal : (gem.lines || []).map(trMod)) : [];
  const desc = gem && gameText(gem.description);
  return h("div", { class: "stack" },
    h("div", { class: "row", style: "gap:8px;align-items:center" }, icon(name), h("b", {}, trName(name)),
      gem ? h("span", { class: "muted small" }, gem.support ? t("skTipSupport") : t("skTipActive")) : null),
    LANG !== "en" && trName(name) !== name ? h("div", { class: "muted small" }, name) : null,
    desc ? h("div", { class: "small" }, desc) : null,
    lines.length ? h("ul", { class: "item-lines small" }, lines.map((l) => h("li", {}, l))) : null,
    gem && gem.mechanics ? mechChips(gem) : null,
    note ? h("div", { class: "hint" }, note) : null);
}
// a gem's picture (or any element) that shows the gem's card on hover
const gemHover = (el, name, note) => (el ? hoverTip(el, () => gemTipCard(name, note)) : el);
const gemName = (name) => hoverTip(h("span", { class: "named pk-node" }, icon(name), trName(name)), () => gemTipCard(name));
// an item's card on hover: its picture and name, its lines, a note under them
function linesTip(pic, name, rows, note) {
  return h("div", { class: "stack" }, h("div", { class: "row", style: "gap:8px;align-items:center" }, pic, h("b", {}, name)),
    rows.length ? h("ul", { class: "item-lines small" }, rows) : h("div", { class: "muted small" }, t("gearNoMods")),
    note ? h("div", { class: "hint" }, note) : null);
}
const uniqueTip = (name, base, lines) => linesTip(itemIcon(name, base, "unique"), trItem(name.split(",")[0]),
  lines.map((l) => h("li", { title: l }, trMod(l))));
// the game's own description in the player's language (from the installed game), English otherwise
const gameText = (text) => (LANG === "en" ? text : GAME.names[text] || null);
const MECH_NAMES = {};
// the mechanics' names in the English view (the server names them as the Russian client does)
const MECH_EN = { impale: "Impale", ice_crystal: "Ice Crystal", freeze: "Freeze", shock: "Shock", ignite: "Ignite",
  bleed: "Bleeding", poison: "Poison", frenzy: "Frenzy Charges", power: "Power Charges", endurance: "Endurance Charges",
  rage: "Rage", infusion: "Infusion", armour_break: "Armour Break", glory: "Glory", combo: "Combo",
  heavy_stun: "Heavy Stun", shapeshift: "Shapeshift" };

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
    h("div", { class: "small term-text" }, termText(text)),
    h("div", { class: "hint" }, t(k.source === "poe2lab" ? "termSourceOwn" : "termSource")));
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
  for (const [k, m] of Object.entries(r.mechanics || {})) MECH_NAMES[k] = LANG === "en" ? MECH_EN[k] || m.name : m.name;
  TERMS = r.terms || {};
  // a gem or unique of a link; the pointer over it shows what it is (the game's description, its lines, what it
  // creates and uses) - the same data as its card below
  for (const g of r.groups) for (const gem of g.gems) GEM_TIPS.set(gem.name, gem);
  const itemsByName = new Map((r.items || []).map((it) => [it.name, it]));
  const itemTip = (name) => {
    const it = itemsByName.get(name);
    const card = uniqueTip(name, name.split(",")[1], it ? it.lines : []);
    if (it) card.append(mechChips(it) || "");
    return card;
  };
  const ref = (x) => (x.item ? hoverTip(h("span", { class: "named pk-node" }, `${trItem(x.gem.split(",")[0])} (${slotName(x.skill)})`), () => itemTip(x.gem))
    : h("span", { class: "named" }, gemName(x.gem), x.support ? h("span", { class: "muted" }, " → ", gemName(x.skill)) : null));
  // the game's own explanation of a mechanic when the game data is unpacked, ours otherwise
  const explain = (l) => {
    const official = (l.terms || []).filter((id) => TERMS[id]);
    if (!official.length || LANG === "en" && !TERMS[official[0]].text) return h("div", { class: "hint" }, LANG === "en" ? "" : l.explain);
    return h("div", { class: "hint" }, official.map((id, i) => h("div", {}, i ? h("b", {}, `${termName(id)}: `) : null,
      termText(LANG !== "en" && TERMS[id].textLocal ? TERMS[id].textLocal : TERMS[id].text))));
  };
  const links = foldedCard(h("div", { class: "card" }, h("h3", {}, t("skLinks")), h("div", { class: "sub" }, t("skLinksSub")),
    r.links.length ? r.links.map((l) => h("div", { class: "sk-link" + (l.missing ? " missing" : "") },
      h("div", {}, h("b", {}, MECH_NAMES[l.key] || l.name), l.missing ? h("span", { class: "chip must", style: "margin-left:8px" }, t("skMissing")) : null),
      explain(l),
      l.creates.length ? h("div", { class: "small" }, h("span", { class: "muted" }, t("skCreatedBy")), " ", l.creates.map((x, i) => [i ? ", " : "", ref(x)])) : null,
      h("div", { class: "small" }, h("span", { class: "muted" }, t("skUsedBy")), " ", l.uses.map((x, i) => [i ? ", " : "", ref(x)]))))
      : h("p", { class: "muted small" }, t("skNoLinks"))),
  "links", r.links.length ? t("skLinksSum", r.links.length, r.links.filter((l) => l.missing).length) : null);
  // a gem's row: what the build gets from it; its description and lines are on hover over its name
  const gemRow = (gem, g) => {
    if (!gem.support) {
      // the skill's own numbers as if it were the main one: crit is each skill's own in the game
      const n = (r.numbers || []).find((x) => x.group === g.index && x.name === gem.name);
      const nums = n && (n.dps > 0 || n.crit > 0) ? h("div", { class: "sk-nums small" },
        n.dps > 0 ? h("span", {}, "DPS ", h("b", {}, fmt(n.dps))) : h("span", { class: "muted" }, t("skNoDps")),
        n.crit > 0 ? h("span", { title: t("skCritHint") }, t("skCrit"), " ", h("b", {}, `${fmt(n.crit, 1)}%`), n.critMulti ? ` ×${fmt(n.critMulti, 2)}` : "") : null,
        n.speed > 0 ? h("span", {}, h("b", {}, fmt(n.speed, 2)), " ", t("skPerSec")) : null,
        n.hitChance > 0 && n.hitChance < 100 ? h("span", {}, t("skHit"), " ", h("b", {}, `${fmt(n.hitChance, 0)}%`)) : null) : null;
      return h("div", { class: "sk-active" }, h("div", { class: "row" }, h("b", {}, gemName(gem.name)),
        gem.available ? h("span", { class: "muted small" }, t("skFromLevel", gem.available)) : null),
        nums, mechChips(gem), termChips(gem.terms));
    }
    const worth = gem.worth ? deltas(gem.worth, METRIC, 0.5) : null;
    return h("div", { class: "sk-support" + (gem.enabled ? "" : " off") },
      h("div", { class: "row" }, gemName(gem.name), gem.enabled ? null : chip("warn", t("skDisabled")),
        gem.because.length ? h("span", { class: "muted small" }, t("skFits", (LANG === "en" && gem.becauseEn ? gem.becauseEn : gem.because).join(", "))) : null),
      worth && !gem.worthIf ? h("div", { class: "small" }, h("span", { class: "muted" }, t(g.measured === "own" ? "skWorthOwn" : g.measured === "hit" ? "skWorthHit" : "skWorthMain")), " ", worth) : null,
      // PoB gives it nothing until a Configuration box is ticked (Retreat: a melee hit recently): what it gives then
      gem.worthIf ? h("div", { class: "small", title: t("skWorthIfHint") }, h("span", { class: "muted" },
        t("skWorthIf", gem.worthIf.conditions.map((c) => `«${conditionLabel(c)}»`).join(", "))), " ",
        deltas(gem.worthIf.worth, METRIC, 0.5)) : null,
      // raw stat ids ("support_momentum_...") mean nothing to a player; the English view keeps them
      (() => { const shown = (LANG === "en" && gem.unseenEn ? gem.unseenEn : gem.unseen).filter((u) => LANG === "en" || !/^[A-Za-z0-9%+]+(_[A-Za-z0-9%+]+)+$/.test(u));
        return shown.length ? h("div", { class: "hint" }, t("skUnseen"), " ", shown.join("; ")) : null; })(),
      mechChips(gem), termChips(gem.terms));
  };
  // a meta gem: what it does with the gems socketed in it, what fills its energy and what in the build does that
  const metaBlock = (g) => {
    const m = g.meta;
    if (!m || (m.kind === "socketed" && !m.socketed.length)) return null;
    const list = (xs) => xs.map(trName).join(", ");
    return h("div", { class: "sk-meta" },
      h("div", {}, h("b", {}, t("metaTitle_" + m.kind, trName(m.gem))),
        m.socketed.length ? " " + t("metaSocketed", list(m.socketed)) : ""),
      m.kind === "energy" && m.sources.length ? h("div", { class: "small" }, t("metaEnergy", m.sources.map((k) => t("metaSrc_" + k)).join(", "))) : null,
      m.kind === "energy" ? Object.entries(m.feeders).filter(([, xs]) => xs.length).map(([k, xs]) =>
        h("div", { class: "small muted" }, t("metaFeeds", t("metaSrc_" + k), list(xs)))) : null,
      m.missing.length ? h("div", { class: "small neg-text" }, t("metaMissing", m.missing.map((k) => t("metaSrc_" + k)).join(", "))) : null,
      termChips(m.kind === "energy" ? ["Meta", "Energy", "Trigger", "Invocation"] : m.kind === "aura" ? ["Meta", "Curse", "Aura"] : ["Meta"]));
  };
  // how often a triggered skill goes off and what it deals from that - PoB does not count it (analysis/triggers)
  const span = ([a, b], f = (x) => fmt(x, 1)) => Math.abs(b - a) <= 0.05 * Math.max(a, b) ? f(a) : `${f(a)}–${f(b)}`;
  const triggerBlock = (g) => {
    const xs = (r.triggers || []).filter((x) => x.group === g.index);
    if (!xs.length) return null;
    return xs.map((x) => h("div", { class: "sk-trigger", title: t("trgHint") },
      h("div", {}, h("b", {}, t("trgTitle"))),
      x.rate ? h("div", { class: "small" }, t("trgRate", span(x.rate.boss), span(x.rate.pack))) : null,
      ...(x.fed || []).map((f) => h("div", { class: "small muted" }, t("trgFed", t("trgEvent_" + f.event), trName(f.skill), fmt(f.perSecond, 1)))),
      ...(x.rate ? x.skills : []).map((s) => h("div", { class: "small" }, s.dps
        ? [t("trgDps", trName(s.name), span(s.dps.boss, (v) => fmt(v)), span(s.dps.pack, (v) => fmt(v))),
          s.pobDps >= 1 ? h("span", { class: "muted" }, " · ", t("trgPob", fmt(s.pobDps))) : null]
        : t("trgTimes", trName(s.name), span(s.rate.boss), span(s.rate.pack)))),
      x.unknown.length ? h("div", { class: "small muted" }, t("trgUnknown", x.unknown.map((k) => t("trgEvent_" + k)).join(", "))) : null));
  };
  // the main skill's group open, the others folded to their skill's damage (or their supports' count)
  const groupSum = (g) => {
    const tr = (r.triggers || []).find((x) => x.group === g.index && x.skills.some((s) => s.dps));
    if (tr) return `≈ DPS ${span(tr.skills.find((s) => s.dps).dps.boss, (v) => fmt(v))}`;
    const n = (r.numbers || []).find((x) => x.group === g.index && x.dps > 0);
    const supports = g.gems.filter((x) => x.support).length;
    return n ? `DPS ${fmt(n.dps)}` : supports ? t("skSupportsN", supports) : null;
  };
  // a support as a pill: its name (the game's description on hover) and what it gives the skill, by colour -
  // green a gain (with a tick when it waits for a condition the build itself makes), amber a gain waiting for a
  // condition nothing in the build makes, blue the mana it keeps, red one that does nothing (nothing in the build
  // makes what it spends), grey nothing PoB sees; the reason on hover over the value
  const supportPill = (gem, g) => {
    const shown = (LANG === "en" && gem.unseenEn ? gem.unseenEn : gem.unseen).filter((u) => LANG === "en" || !/^[A-Za-z0-9%+]+(_[A-Za-z0-9%+]+)+$/.test(u));
    const fits = (LANG === "en" && gem.becauseEn ? gem.becauseEn : gem.because).join(", ");
    const measured = t(g.measured === "own" ? "skWorthOwn" : g.measured === "hit" ? "skWorthHit" : "skWorthMain");
    let cls = "none", value = "—", why = t("skPillNone");
    const d = gem.worth ? gem.worth.dps || 0 : 0, e = gem.worth ? gem.worth.ehp || 0 : 0;
    if (!gem.enabled) { cls = "off"; value = t("skDisabled"); why = ""; }
    else if (gem.dead) {
      cls = "dead"; value = t("skPillDead");
      why = t("skPillDeadHint", gem.dead.name.toLowerCase(), gem.dead.makers.map(trName).join(", ") || "—");
    } else if (gem.worthIf) {
      const v = gem.worthIf.worth.dps || gem.worthIf.worth.ehp || 0;
      const made = (gem.worthIf.byBuild || []).length > 0;
      cls = made ? "pos" : "if"; value = `${pct(v)} ${made ? "✓" : "⚠"}`;
      why = t("skWorthIf", gem.worthIf.conditions.map((c) => `«${conditionLabel(c)}»`).join(", ")) + " " + pct(v) + ". " +
        (made ? t("skPillMakers", gem.worthIf.byBuild.map((n) => (/\s/.test(n) && n.length > 30 ? trMod(n) : trName(n))).join(", ")) : t("skPillNoMakers"));
    } else if (gem.mana) { cls = "mana"; value = t("skPillMana", fmt(gem.mana)); why = t("skPillManaHint"); }
    else if (Math.abs(d) >= 0.5) { cls = d > 0 ? "pos" : "neg"; value = pct(d); why = measured; }
    else if (Math.abs(e) >= 0.5) { cls = e > 0 ? "pos" : "neg"; value = `eHP ${pct(e)}`; why = measured; }
    const title = [why, fits ? t("skFits", fits) : "", shown.length ? `${t("skUnseen")} ${shown.join("; ")}` : ""].filter(Boolean).join("\n");
    return h("span", { class: `sk-pill ${cls}` }, gemName(gem.name), h("b", { class: "sk-pill-v", title }, value));
  };
  // a skill's own numbers in a line: its damage per second, crit, how often
  const headNums = (g) => {
    const n = (r.numbers || []).find((x) => x.group === g.index && x.dps > 0);
    if (!n) return null;
    return h("span", { class: "sk-head-nums" }, "DPS ", h("b", {}, fmt(n.dps)),
      n.crit > 0 ? ` · ${t("skCrit")} ${fmt(n.crit, 0)}%` : "", n.speed > 0 ? ` · ${fmt(n.speed, 1)}/${t("exSec")}` : "");
  };
  // each group: a head (its skills, numbers), its role (filled in when counted), what a meta gem and a trigger do,
  // the supports as pills; the rest - skill kinds, terms, mechanics, each gem's full row - under "more"
  const cards = r.groups.filter((g) => g.gems.length).sort((a, b) => b.main - a.main).map((g) => {
    const supports = g.gems.filter((x) => x.support);
    const nums = headNums(g);
    const card = h("div", { class: "card sk-group" + (g.enabled ? "" : " off") + (g.main ? " wide" : ""), "data-group": g.index },
      h("div", { class: "sk-head" }, h("h3", {}, `${g.index}. `, g.actives.map((a, i) => [i ? " + " : "", gemName(a.name)])),
        g.main ? chip("tag", t("skMain")) : null, g.enabled ? null : chip("warn", t("skDisabled")),
        g.slot ? h("span", { class: "muted small" }, slotName(g.slot)) : null, nums),
      metaBlock(g),
      triggerBlock(g),
      supports.length ? h("div", { class: "sk-pills" }, supports.map((x) => supportPill(x, g))) : null,
      auNote("sk:" + g.actives.map((a) => a.name).join("+"), t("auLinkPh")),
      h("details", { class: "sk-more" }, h("summary", { class: "muted small" }, t("skMore")),
        g.actives[0] && (g.actives[0].typeTags || []).length ? typeChips(g.actives[0].typeTags) : null,
        g.gems.filter((x) => !x.support).map((x) => gemRow(x, g)),
        supports.length ? h("div", { class: "sk-supports" }, supports.map((x) => gemRow(x, g))) : null));
    // folded, the head shows the numbers: the summary only for a skill without them (triggered, supports only)
    return g.main ? card : foldedCard(card, "group:" + g.actives.map((a) => a.name).join("+"), nums ? null : groupSum(g));
  });
  const items = (r.items || []).length ? foldedCard(h("div", { class: "card" }, h("h3", {}, t("skUniques")), h("div", { class: "sub" }, t("skUniquesSub")),
    h("div", { class: "grid two" }, r.items.map((it) => h("div", { class: "sk-item" },
      h("div", { class: "row" }, itemIcon(it.name, it.name.split(",")[1], "unique"),
        hoverTip(h("b", { class: "pk-node" }, trItem(it.name.split(",")[0])), () => itemTip(it.name)),
        h("span", { class: "muted small" }, slotName(it.slot))),
      it.unseen.length ? h("div", { class: "hint" }, t("skUnseen"), " ", it.unseen.map((l, i) => [i ? "; " : "", h("span", { title: l }, trMod(l))])) : null,
      mechChips(it), termChips(it.terms))))), "uniques", t("skUniquesSum", r.items.length)) : null;
  const grid = h("div", { class: "grid cards masonry" }, cards);
  DATA.skills("roles").then((rr) => fillRoles(grid, rr)).catch(() => {});
  return [links, items, grid].filter(Boolean);
}

// uniques of the whole game that go with the build's skills (mechanics, skill kinds, damage types, shared terms)
const DMG_RU = { cold: "холод", fire: "огонь", lightning: "молния", chaos: "хаос", physical: "физический" };
// the uniques linked to the build's skills (the Gear tab's card): `reload` asks again for the other range
const UNIQUE_START_LEVEL = 30;  // a unique worn from this level or lower: for the start, to level faster
const UNIQUE_DEAR_DIV = 1;  // from this price (divines) it is marked dear
function renderUniqueLinks(r, reload) {
  TERMS = r.terms || {};
  const mech = (k) => (LANG === "en" && MECH_EN[k]) || r.mechanics[k] || k;
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
    h("button", { class: (state.uniqueScope || "level") === k ? "active" : "", onclick: () => { state.uniqueScope = k; reload(); } }, label))) : null;
  const head = h("div", {}, h("div", { class: "sub" }, t("unSub", r.considered)),
    r.outweighed ? h("div", { class: "hint", style: "margin-bottom:8px" }, t("unOutweighed", r.outweighed)) : null, scopeSeg);
  if (!r.suggestions.length) return [head, h("p", { class: "muted" }, t("unNone"))];
  // its price on poe.ninja (the chosen league): in exalted orbs under one divine
  const prices = r.prices || {};
  const price = (name) => {
    const x = (prices.byName || {})[name];
    if (!x) return h("span", { class: "chip tag", title: t("unNoPriceHint") }, t("unNoPrice"));
    const rate = prices.exaltedPerDivine || 0;
    const text = x.div < 1 && rate ? `${fmt(x.div * rate, x.div * rate < 10 ? 1 : 0)} ex` : `${fmt(x.div, x.div < 10 ? 1 : 0)} div`;
    return h("span", { class: "chip " + (x.div >= UNIQUE_DEAR_DIV ? "warn" : "ok"), title: t("unPriceHint", trName(prices.league || ""), x.listings) }, "💰 ", text);
  };
  const cards = r.suggestions.map((u) => {
    return h("div", { class: "card sk-item" },
      h("div", { class: "row" }, itemIcon(u.name, u.base, "unique"), hoverTip(h("b", { class: "pk-node" }, trItem(u.name)), () => uniqueTip(u.name, u.base, u.lines)),
        h("span", { class: "muted small" }, `${slotName(u.slot)} · ${trName(u.base)}`),
        u.level ? h("span", { class: "muted small" }, t("unLevel", u.level)) : null,
        u.level && u.level <= UNIQUE_START_LEVEL ? h("span", { class: "chip ok", title: t("unStartHint") }, "🚀 ", t("unStart")) : null,
        price(u.name)),
      h("ul", { class: "un-reasons small" }, u.reasons.map((x) => h("li", {}, reason(x)))),
      h("div", { class: "small" }, h("span", { class: "muted" }, t("unWorth", slotName(u.slot))), " ",
        u.outsidePob ? h("span", { class: "chip util" }, t("unPobBlind")) : deltas(u.changes, METRIC, 0.5)),
      u.unread.length ? h("div", { class: "hint" }, t("skUnseen"), " ", u.unread.map((l, i) => [i ? "; " : "", h("span", { title: l }, trMod(l))])) : null,
      u.source ? h("div", { class: "hint" }, t("unSource"), " ", trFree(u.source)) : null,
      termChips(u.terms));
  });
  return [head, h("div", { class: "grid cards" }, cards), h("div", { class: "hint" }, t("unNote"))];
}

// Levelling, as the game shows gems: pick a level (the character's by default) and see, for each skill, what goes
// into its support sockets then - the build's own supports once they can be had, a stand-in until then (the best
// PoB finds that is not used elsewhere: a support gem goes into one skill only) - and what opens next.
function renderSkillsLeveling(r) {
  for (const p of r.plans) for (const s of p.stages) for (const o of s.options) {
    if (o.color && !GEM_INFO[o.name]) GEM_INFO[o.name] = { color: o.color, support: true };
  }
  const opens = new Map(r.timeline.flatMap((row) => row.gems.map((g) => [g.name, row.level])));
  const charLevel = state.build.info.level || 1;
  const top = Math.max(60, charLevel, ...r.timeline.map((x) => x.level), ...r.plans.flatMap((p) => p.stages.map((s) => s.level)));
  let level = Math.min(top, state.levelView && state.levelView.build === state.build.name ? state.levelView.level : charLevel);

  const shown = h("span", { class: "lv-level" });
  const slider = h("input", { type: "range", min: 1, max: top, value: level, oninput: () => set(Number(slider.value)) });
  const now = h("button", { class: "ghost small", onclick: () => { slider.value = charLevel; set(charLevel); } }, t("lvNow", charLevel));
  const body = h("div", { class: "stack" });
  const next = h("div", {});
  const set = (lv) => {
    level = lv;
    state.levelView = { build: state.build.name, level };
    shown.textContent = level;
    now.disabled = level === charLevel;
    draw();
  };

  const socketGem = (name, cls, extra, title) => gemHover(h("div", { class: "lv-socket " + cls },
    icon(name) || h("div", { class: "lv-hole" }), h("div", { class: "lv-sock-name" }, trName(name)), extra), name, title);
  const draw = () => {
    const plans = [...r.plans].sort((a, b) => b.main - a.main);
    const isOpen = (p) => p.skillAvailable === null || p.skillAvailable === undefined || p.skillAvailable <= level;
    // the supports the open skills already use at this level, then stand-ins: never the same support in two skills
    const used = new Set(plans.filter(isOpen).flatMap((p) => (stageAt(p, level) || { build: [] }).build));
    body.replaceChildren(...plans.map((p) => {
      const open = isOpen(p);
      const st = stageAt(p, level) || { build: [], later: [], options: [] };
      const sockets = [];
      let more = [];
      if (open) {
        for (const name of st.build) sockets.push(socketGem(name, "own", null, t("lvOwnTitle")));
        const spare = st.options.filter((o) => !used.has(o.name));
        for (const name of st.later) {
          const o = spare.shift();
          if (o) used.add(o.name);
          const then = h("div", { class: "lv-then", title: name }, t("lvThen", trName(name), opens.get(name)));
          sockets.push(o ? socketGem(o.name, "fill", [h("div", { class: "lv-gain", title: t("lvGainTitle") }, pct(o.dps)), then], t("lvFillTitle"))
            : h("div", { class: "lv-socket vacant" }, h("div", { class: "lv-hole" }), then));
        }
        if (!sockets.length) sockets.push(h("div", { class: "muted small" }, t("lvNoSupports")));
        more = spare.filter((o) => !used.has(o.name));
      }
      return h("div", { class: "lv-skill" + (open ? "" : " locked") },
        h("div", { class: "lv-skill-head" }, gemHover(icon(p.skill), p.skill), gemHover(h("b", { class: "pk-node" }, trName(p.skill)), p.skill),
          p.main ? chip("tag", t("skMain")) : null,
          open ? (p.skillAvailable ? null : h("span", { class: "muted small" }, t("lvFromItem")))
            : h("span", { class: "muted small" }, t("lvOpensAt", p.skillAvailable))),
        open ? h("div", { class: "stack", style: "gap:6px" }, h("div", { class: "lv-sockets" }, sockets),
          more.length ? h("details", { class: "small" }, h("summary", {}, t("lvMore", more.length)),
            h("div", { class: "lv-more" }, more.map((o) => gemHover(h("span", { class: "named pk-node" }, icon(o.name), trName(o.name),
              h("span", { class: "lv-gain" }, " " + pct(o.dps))), o.name, t("lvGainTitle"))))) : null) : null);
    }));
    const ahead = r.timeline.filter((x) => x.level > level).slice(0, 4);
    next.replaceChildren(h("h3", {}, t("lvNext")), ahead.length ? h("div", { class: "lv-next" }, ahead.map((x) => h("div", { class: "lv-mile" },
      h("b", {}, t("lvAt", x.level)), x.gems.map((g) => gemHover(h("div", { class: "named pk-node" }, icon(g.name), trName(g.name)), g.name,
        g.support ? t("lvForSkills", g.skills.map(trName).join(", ")) : null))))) : h("p", { class: "muted" }, t("lvNothingNext")));
  };
  set(level);
  const target = (state.build.profileRaw || {}).target;
  const source = target ? h("div", { class: "segmented" }, [["target", t("lvByTarget", target)], ["build", t("lvByBuild")]].map(([k, label]) =>
    h("button", { class: (r.of ? "target" : "build") === k ? "active" : "", title: k === "target" ? t("lvTargetHint") : "",
      onclick: () => { state.levelOf = k; switchTab("skills"); } }, label))) : null;
  return [
    h("div", { class: "card stack" },
      h("h3", {}, t("lvTitle")),
      source,
      h("div", { class: "lv-head" }, h("span", { class: "muted" }, t("lvLevel")), shown, slider, now),
      h("div", { class: "hint" }, t("lvHint")),
      r.guide ? h("div", { class: "hint" }, t("lvGuideLevels")) : null,
      body),
    h("div", { class: "card" }, next),
    h("div", { class: "card" }, h("details", {}, h("summary", {}, t("lvWhere")),
      h("div", { class: "sub", style: "margin-top:8px" }, t("skLevelSub")),
      h("div", { class: "small" }, t("skUncut",
        Object.entries(r.uncutSkillArea).filter(([lv]) => lv % 2 === 1 && lv <= 13).map(([lv, area]) => `${lv} — ${area}`).join(", "),
        Object.entries(r.uncutSupportArea).map(([tier, lv]) => `${tier} — ${lv}`).join(", "))))),
  ];
}
// the levelling stage in force at a level: the last one that has started
const stageAt = (plan, level) => plan.stages.filter((s) => s.level <= level).pop() || plan.stages[0];

// ---------- what PoB does not count that moves the numbers a lot, and the corrections for it (the overview) ----------
// Each line PoB ignores is read the way PoB can (poe2lab.analysis.unmodeled) and priced on the skill it belongs to;
// "count it" adds the line to the build's profile as a correction - as if it always works, the share of the fight it
// does is the player's to set - and every number counts it from then on.
const UM_METRIC = [["dps", "m_dps"], ["ehp", "m_ehp"], ["recovery", "m_recovery"]];
// "Name, Base (Slot)" / "Skill (группа N)": names through trItem, so a rare's random English name is dropped in
// Russian (the game builds it from words with several Russian variants — it cannot be recovered exactly)
function gapWhere(w) {
  const m = w.match(/^(.*) \(([^()]+)\)$/);
  if (!m) return trFree(w);
  const tail = m[2].replace(/группа (\d+)/, (_, n) => `${t("group")} ${n}`);
  return h("span", { title: w, class: "named" }, icon(m[1]), `${trItem(m[1])} (${SLOT_RU[m[2]] !== undefined ? slotName(m[2]) : trFree(tail)})`);
}
// the game's own text in the player's language (from the installed game) beats any translation of ours; in Russian
// only what has an official translation, the English original in the tooltip
const gapText = (g) => (LANG !== "en" && g.text_local ? h("div", { title: g.text }, g.text_local) : h("div", { title: g.text }, trMod(g.text)));
// raw internal stat ids ("stat_name = 20") mean nothing to a player; the English view keeps them
const gapShown = (g) => LANG === "en" || g.text_local || !/^[A-Za-z0-9_%+]+ = /.test(g.text);

// the profile's corrections changed and saved: the build is opened again with them, every number counts them
async function saveCorrections(change, msg) {
  const raw = JSON.parse(JSON.stringify(state.build.profileRaw));
  raw.corrections = raw.corrections || [];
  raw.notes = raw.notes || [];
  change(raw.corrections);
  raw.main_skill = { group: state.build.info.mainSocketGroup, skill: state.build.info.mainActiveSkill || 1, name: state.build.mainSkill };
  try {
    state.build = await api("/api/profile", { method: "PUT", body: raw });
    resetCache();
    renderHeader();
    loadBuildList();
    if (msg) toast(msg, true);
    switchTab(state.tab);
  } catch (e) { toast(e.message); }
}

function unmodeledCard() {
  const card = h("div", { class: "card stack um-card" }, h("h3", {}, t("umTitle")), h("div", { class: "sub" }, t("umSub")), loading(t("umLoading")));
  DATA.unmodeled().then((d) => {
    const head = card.querySelector("h3");
    head.append(h("span", { class: "fold-sum" }, t("umSum", d.big.length, d.corrections.length)));
    const corr = (c) => h("div", { class: "um-row on" },
      h("div", { class: "um-main" }, h("b", { title: c.mod }, trMod(c.mod)), h("div", { class: "where small" }, gapWhere(c.source.split(": ")[0]))),
      h("label", { class: "um-up small", title: t("umUptimeHint") }, t("umUptime"), " ",
        h("input", { type: "number", min: 0, max: 100, step: 5, value: Math.round(c.uptime * 100),
          onchange: (e) => saveCorrections((list) => { list[c.index].uptime = Math.max(0, Math.min(1, Number(e.target.value) / 100)); }) }), "%"),
      deltas(c.changes, UM_METRIC, 0.3),
      h("button", { class: "x", title: t("remove"), onclick: () => saveCorrections((list) => list.splice(c.index, 1), t("umRemoved")) }, "×"));
    const est = (g) => h("div", { class: "um-row" },
      h("div", { class: "um-main" }, gapText(g), h("div", { class: "where small" }, gapWhere(g.where)),
        g.stages ? h("div", { class: "muted small" }, t("umStages", g.stages)) : null),
      h("div", { class: "um-est" }, h("span", { class: "muted small" }, t("umIfAlways")), deltas(g.changes, UM_METRIC, 0.3)),
      h("button", { class: "primary small", title: trMod(g.line),
        onclick: () => saveCorrections((list) => list.push({ mod: g.line, source: g.key, uptime: 1, confirmed: false }), t("corrAdded", trMod(g.line))) }, t("umCount")));
    const unpriced = (g) => h("div", { class: "gap" },
      h("button", { class: "gap-add", title: t("addToPob"), onclick: (e) => toggleAddPanel(e.currentTarget.parentElement, g) }, "+"),
      h("div", { class: "where" }, gapWhere(g.where)), gapText(g));
    const small = d.small.filter(gapShown), rest = d.unpriced.filter(gapShown);
    card.replaceChildren(...[head, card.querySelector(".sub"),
      d.corrections.length ? h("div", { class: "section-title" }, t("umCorrections")) : null, ...d.corrections.map(corr),
      d.big.length ? h("div", { class: "section-title" }, t("umBig", d.big_pct)) : null, ...d.big.map(est),
      d.big.length ? null : h("p", { class: "muted small" }, t("umNone", d.big_pct)),
      small.length ? h("details", {}, h("summary", { class: "small" }, t("umSmall", small.length)), ...small.map(est)) : null,
      rest.length ? h("details", {}, h("summary", { class: "small" }, t("umUnpriced", rest.length)), h("div", { class: "hint" }, t("umUnpricedHint")),
        ...rest.map(unpriced)) : null].filter(Boolean));
  }).catch((e) => card.append(h("p", { class: "muted" }, e.message)));
  return card;
}

// ---------- profile ----------
TABS.profile = async () => {
  const raw = JSON.parse(JSON.stringify(state.build.profileRaw));
  raw.corrections = raw.corrections || [];
  raw.notes = raw.notes || [];
  // the build this one grows into (a guide at its end game): the assistant explains what matters now and what later
  let builds = [];
  try { builds = await api("/api/builds"); } catch (_) { /* the list is not needed to edit the rest */ }
  const targetSel = h("select", {}, h("option", { value: "" }, t("targetNone")),
    builds.filter((b) => b.name !== state.build.name).map((b) => h("option", { value: b.name, selected: raw.target === b.name }, b.name)));
  // Only ask what this build can answer: a build with no Rage must not show a Rage question.
  const ask = state.build.questions || { rage: true, mana: true };
  const rageMax = h("input", { type: "checkbox", checked: raw.rage === null || raw.rage === undefined });
  const rageVal = h("input", { type: "number", value: raw.rage ?? 0, min: 0, style: "width:90px" });
  const mana = h("input", { type: "checkbox", checked: !!raw.mana_sustained });
  const notes = h("textarea", { rows: 6 }, raw.notes.join("\n"));
  const save = h("button", { class: "primary", onclick: async () => {
    raw.rage = !ask.rage || rageMax.checked ? null : Number(rageVal.value);
    raw.mana_sustained = ask.mana && mana.checked;
    raw.notes = notes.value.split("\n").map((s) => s.trim()).filter(Boolean);
    raw.target = targetSel.value || null;
    raw.main_skill = { group: state.build.info.mainSocketGroup, skill: state.build.info.mainActiveSkill || 1, name: state.build.mainSkill };
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

  const facts = h("div", { class: "grid two" },
    h("div", { class: "card stack" }, h("h3", {}, `${t("factsTitle")} — ${state.build.name}`),
      h("div", { class: "sub" }, t("factsSub")),
      state.build.hasProfile ? null : h("div", { class: "action" }, t("noProfileYet", state.build.name)),
      ask.rage ? h("div", { class: "row" }, h("label", {}, rageMax, t("rageMax")), h("span", { class: "muted" }, t("otherwise")), rageVal) : null,
      ask.mana ? h("label", {}, mana, t("manaOk")) : null,
      ask.rage || ask.mana ? null : h("div", { class: "muted small" }, t("noQuestions")),
      h("div", { class: "hint" }, t("corrMoved")),
      h("div", { class: "section-title" }, t("targetTitle")), h("div", { class: "sub" }, t("targetSub")), targetSel,
      h("div", { class: "section-title" }, t("notes")), notes, h("div", {}, save)),
    foldedCard(h("div", { class: "card" }, h("h3", {}, t("howCounted")),
      state.build.profile.map((l) => h("div", { class: "profile-line" }, trFree(l)))), "counted", t("linesN", state.build.profile.length)));
  return h("div", { class: "stack" }, facts, questsCard());
};

// "+" on a mechanic PoB ignores: turn it into a correction of the profile. PoB cannot read the game line itself
// (that is why it is listed), so offer the line when it parses after all, the closest mods PoB does read with the
// line's numbers filled in, and a free search.
async function toggleAddPanel(box, g) {
  const open = box.querySelector(".add-panel");
  if (open) { open.remove(); return; }
  const panel = h("div", { class: "add-panel" }, loading(t("searching")));
  box.append(panel);
  const add = (line) => {
    panel.replaceChildren(loading(t("counting")));
    saveCorrections((list) => list.push({ mod: line, source: `${g.where}: ${g.text}`, uptime: 1, confirmed: false }), t("corrAdded", trMod(line)));
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

// ---------- mod picker (like the in-game trade filter): a mod found by its words in the player's language ----------
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
  nothing: "warn", old_pool: "warn" };

// A page of its own (from the sidebar), not a build tab: the journal is about the game, not about one build.
async function renderJournal() {
  state.page = "journal";
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
    h("div", { class: "row jn-grade" }, h("span", {}, t("jnGrade")), h("div", { class: "segmented small-seg" },
      [["", "jnGradeRegular"], ["greater", "jnGradeGreater"], ["perfect", "jnGradePerfect"]].map(([g, key]) =>
        h("button", { class: (j.grade || "") === g ? "active" : "", onclick: async () => {
          try { await api("/api/journal/grade", { method: "POST", body: { grade: g } }); renderJournal(); }
          catch (e) { toast(e.message); }
        } }, t(key)))), h("span", { class: "muted small" }, t("jnGradeHint"))),
    h("ol", { class: "jn-rules" }, [1, 2, 3, 4, 5].map((i) => h("li", {}, t("jnRule" + i)))),
    h("details", {}, h("summary", {}, t("jnPaste")), paste, h("div", { style: "margin-top:6px" }, addBtn))));

  // what to record next: each goal shrinks as draws come in
  const left = j.plan.filter((g) => g.left > 0);
  const className = (c) => ((j.classNames || {})[c] || {})[LANG] || slotName(c);  // the game's own names
  const goalName = (g) => (g.key === "class" ? className(g.class) : t("jnGoal_" + g.key));
  const goalWhy = (g) => t("jnWhy_" + g.key);
  body.append(h("div", { class: "card" }, h("h3", {}, t("jnPlanTitle")),
    h("div", { class: "sub" }, t("jnStats", j.total, j.draws), " ", left.length ? t("jnPlanLeft", left.length) : t("jnPlanDone")),
    h("table", { class: "jn-plan" }, h("thead", {}, h("tr", {}, h("th", {}, t("jnPlanGoal")), h("th", {}, t("jnPlanWhy")),
      h("th", { class: "num" }, t("jnPlanHave")), h("th", {}, ""), h("th", { class: "num" }, t("jnPlanLeftCol")))),
      h("tbody", {}, j.plan.map((g) => h("tr", { class: g.left ? "" : "done" },
        h("td", {}, goalName(g)), h("td", { class: "muted small" }, goalWhy(g)),
        h("td", { class: "num" }, `${g.have} / ${g.need}`),
        h("td", { class: "jn-bar" }, h("div", { class: "bar" }, h("span", { style: `width:${Math.min(100, (g.have / g.need) * 100)}%` }))),
        h("td", { class: "num" }, g.left ? h("b", {}, g.left) : chip("ok", "✓")))))),
    h("div", { class: "note small muted", style: "margin-top:8px" }, t("jnHowMany"))));

  // the estimate: how each family's chance moved from the assumption, and applying it to crafting
  const est = j.estimate;
  const estimateBtn = h("button", { class: "primary", onclick: async () => {
    estimateBtn.disabled = true;
    estimateBtn.textContent = t("jnEstimating");
    try { await api("/api/journal/estimate", { method: "POST" }); renderJournal(); }
    catch (e) { toast(e.message); estimateBtn.disabled = false; estimateBtn.textContent = t("jnEstimate"); }
  } }, t("jnEstimate"));
  // weights reach the crafting simulator only of this game version's mods and from enough draws
  const tooFew = est && !j.applied && est.draws < j.minApply;
  const applyBtn = est ? h("button", { class: "ghost", disabled: (tooFew || j.estimateOld) && !j.applied,
    title: tooFew ? t("jnApplyFew", est.draws, j.minApply) : j.estimateOld ? t("jnEstimateOld") : null, onclick: async () => {
      try { await api("/api/journal/apply", { method: j.applied ? "DELETE" : "POST" }); resetCache(); renderJournal(); }
      catch (e) { toast(e.message); }
    } }, j.applied ? t("jnUnapply") : t("jnApply")) : null;
  const seen = est ? est.families.filter((f) => f.seen > 0) : [];
  const warns = [
    j.oldRecords ? t("jnOldRecords", j.oldRecords) : null,
    j.estimateOld ? t("jnEstimateOld") : null,
    j.appliedOld ? t("jnAppliedOld") : null,
    tooFew && !j.estimateOld ? t("jnApplyFew", est.draws, j.minApply) : null].filter(Boolean);
  body.append(h("div", { class: "card" }, h("h3", {}, t("jnWeightsTitle")), h("div", { class: "sub" }, t("jnWeightsSub")),
    h("div", { class: "row", style: "gap:10px;flex-wrap:wrap;margin-bottom:10px" }, estimateBtn, applyBtn,
      j.applied ? chip("ok", t("jnApplied")) : null),
    warns.length ? h("div", { class: "hint", style: "margin-bottom:8px" }, warns.map((w) => h("div", {}, "⚠ ", w))) : null,
    est ? h("div", {},
      h("p", { class: "small" }, t("jnEstimated", est.draws, new Date(est.time * 1000).toLocaleString(locale())),
        est.kindDraws ? ["weapon", "other"].filter((k) => est.kindDraws[k]).map((k) =>
          " " + t("jnSlope_" + k, est.halfLevel[k] ? fmt(est.halfLevel[k]) : null)).join("") : ""),
      Object.entries(est.thresholds || {}).map(([g, x]) => h("p", { class: "small" },
        h("b", {}, t("jnGradeName_" + g)), " ", t("jnThreshold", x), " ",
        h("span", { class: "muted" }, t(x.lowFamilies === null ? "jnLowUnknown" : x.lowFamilies ? "jnLowYes" : "jnLowNo")),
        x.draws < 30 ? h("span", { class: "muted" }, " " + t("jnThresholdFew")) : null,
        x.regularShare >= 0.1 ? h("div", { class: "muted" }, t("jnRegularShare", Math.round(x.regularShare * 100))) : null)),
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
        e.grade ? chip("priority", t("jnGradeName_" + e.grade)) : null,
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

// ---------- the beginner's glossary: terms in our own words, linked to each other ----------
async function renderGlossary() {
  state.page = "glossary";
  hideBuildChrome();
  const view = $("#view");
  view.replaceChildren(loading(t("glLoading")));
  try {
    const r = await api(`/api/glossary?lang=${LANG}`);
    TERMS = { ...TERMS, ...r.terms };
    const body = h("div", { class: "stack" });
    if (state.build) {
      body.append(h("div", {}, h("button", { class: "ghost small", onclick: () => { renderHeader(); switchTab(state.tab); } },
        t("jnBack", state.build.name))));
    }
    body.append(h("div", { class: "card" }, h("h3", {}, t("glTitle")), h("div", { class: "sub" }, t("glSub"))));
    for (const g of r.groups) {
      body.append(h("div", { class: "card" }, h("h3", {}, g.name),
        h("div", { class: "gl-list" }, g.ids.map((id) => h("div", { class: "gl-entry", id: "gl-" + id },
          h("b", {}, termName(id)), h("div", { class: "term-text small" }, termText(r.terms[id].textLocal || r.terms[id].text)))))));
    }
    view.replaceChildren(body);
  } catch (e) {
    view.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("error")), h("p", { class: "muted" }, e.message)));
  }
}
$("#glossary-open").addEventListener("click", renderGlossary);

// ---------- assistant ----------
function aiSettingsCard(settings, onSaved) {
  let current = settings.providers.find((p) => p.id === settings.provider) || settings.providers[0];
  const provSel = h("select", {}, settings.providers.map((p) => h("option", { value: p.id }, trFree(p.name))));
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
    note.textContent = trFree(current.note || "");
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
  // no key: the prompt for any chat AI first, the key settings after it; with a key the chat, the prompt below
  const redraw = (s) => {
    wrap.replaceChildren(...(s.active.configured ? [aiSettingsCard(s, redraw), chatCard(true), promptCard(s), mcpCard()]
      : [promptCard(s), mcpCard(), aiSettingsCard(s, redraw)]));
    loadStatus();
  };
  redraw(settings);
  return wrap;
};

// The player's own AI app on this computer (Claude Desktop, Cursor, Claude Code...) with poe2lab's tools over MCP:
// the app starts poe2lab itself and every number it gives comes from PoB here - on the player's subscription, no key.
function mcpCard() {
  const card = h("div", { class: "card stack mcp-card" }, h("h3", {}, t("mcpTitle")), h("div", { class: "sub" }, t("mcpSub")),
    loading(t("counting")));
  const copyRow = (label, text) => {
    const area = h("textarea", { class: "mcp-code", rows: Math.min(10, text.split("\n").length), readonly: true, spellcheck: "false" }, text);
    return h("div", { class: "stack", style: "gap:4px" }, h("div", { class: "row" }, h("b", { class: "small" }, label),
      h("button", { class: "ghost small", onclick: async () => toast(t((await copyText(text, area)) ? "copied" : "npCopyFail"), true) }, t("copy"))), area);
  };
  const draw = (m) => {
    const cd = m.claudeDesktop;
    const head = card.querySelector("h3");
    head.querySelector(".fold-sum")?.remove();
    head.append(h("span", { class: "fold-sum" }, cd.connected ? t("mcpSumOn") : t("mcpSumOff")));
    const act = async (method) => {
      if (method === "POST" && !(await confirmInPage(t("mcpAsk"), t("mcpConnect")))) return;
      try {
        draw(await api("/api/mcp/claude-desktop", { method }));
        toast(t(method === "POST" ? "mcpDone" : "mcpRemoved"), true);
      } catch (e) { toast(e.message); }
    };
    card.replaceChildren(...[head, card.querySelector(".sub"),  // native replaceChildren would write a null out
      m.available ? null : h("div", { class: "bad small" }, t("mcpMissing")),
      h("div", { class: "row mcp-desktop" }, h("span", { class: "mcp-ico" }, "🔌"),
        !cd.found ? h("span", { class: "muted small" }, t("mcpNoDesktop"))
          : cd.connected ? [chip("ok", t("mcpConnected")), h("button", { class: "ghost small", onclick: () => act("DELETE") }, t("mcpDisconnect"))]
            : h("button", { class: "primary", disabled: !m.available, onclick: () => act("POST") }, t("mcpConnect"))),
      cd.connected ? h("div", { class: "action small" }, t("mcpRestart")) : null,
      h("details", {}, h("summary", { class: "small" }, t("mcpOther")),
        h("div", { class: "stack", style: "margin-top:8px" }, h("div", { class: "hint" }, t("mcpOtherHint")),
          copyRow(t("mcpJson"), m.json), copyRow("Claude Code", m.claudeCode)))].filter(Boolean));
  };
  api("/api/mcp").then(draw).catch((e) => card.append(h("p", { class: "muted" }, e.message)));
  return foldedCard(card, "mcp", null);
}

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

// ---- no key: the question with the build and PoB's reports as one prompt, to paste into any chat AI ----
const NP_CHATS = [["DeepSeek", "https://chat.deepseek.com"], ["ChatGPT", "https://chatgpt.com"], ["Claude", "https://claude.ai"],
  ["Gemini", "https://gemini.google.com"]];
const npState = { question: "", size: "compact", result: null };

async function copyText(text, fallbackEl) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    if (!fallbackEl) return false;
    const box = fallbackEl.closest("details");
    if (box) box.open = true;  // a text in a closed block cannot be selected
    fallbackEl.focus();
    fallbackEl.select();
    try { return document.execCommand("copy"); } catch (__) { return false; }
  }
}

function promptCard(settings) {
  const q = h("textarea", { rows: 3, placeholder: t("npPh"), oninput: () => { npState.question = q.value; } }, npState.question);
  const out = h("div", { class: "stack" });
  const seg = h("div", { class: "segmented" });
  const drawSeg = () => seg.replaceChildren(...["compact", "full"].map((k) => h("button", { class: npState.size === k ? "active" : "",
    onclick: () => { npState.size = k; drawSeg(); } }, t("npSize_" + k))));
  drawSeg();
  const show = (r) => {
    const text = h("textarea", { rows: 8, readonly: true, class: "np-text" }, r.prompt);
    const copy = async () => toast(t((await copyText(r.prompt, text)) ? "npCopied" : "npCopyFail"), true);
    const step = (n, label, ...body) => h("div", { class: "np-step" }, h("span", { class: "np-num" }, n), h("div", { class: "stack" }, h("b", {}, label), ...body));
    out.replaceChildren(
      h("div", { class: "np-steps" },
        step(1, t("npStep1"), h("button", { class: "primary", onclick: copy }, t("npCopy"))),
        step(2, t("npStep2"), h("div", { class: "row" }, NP_CHATS.map(([name, url]) =>
          h("a", { class: "np-link", href: url, target: "_blank", rel: "noopener noreferrer" }, name)))),
        step(3, t("npStep3"), h("span", { class: "muted small" }, t("npStep3Hint")))),
      h("div", { class: "muted small" }, t("npInfo", fmt(r.chars), fmt(Math.round(r.chars / 3))),
        r.topics.length ? " · " + t("npTopics") + r.topics.map((x) => t("npTopic_" + x)).join(", ") : ""),
      h("details", {}, h("summary", { class: "small" }, t("npShow")), text));
  };
  const go = h("button", { class: "primary", onclick: async () => {
    const question = q.value.trim();
    if (!question) { q.focus(); return; }
    go.disabled = true;
    out.replaceChildren(loading(t("npMaking")));
    try {
      npState.result = await api("/api/chat/prompt", { method: "POST",
        body: { question, size: npState.size, style: settings.style || "short", lang: LANG } });
      show(npState.result);
    } catch (e) { out.replaceChildren(h("p", { class: "neg" }, e.message)); }
    go.disabled = false;
  } }, t("npMake"));
  if (npState.result) show(npState.result);
  return h("div", { class: "card stack np" }, h("h3", {}, t("npTitle")), h("div", { class: "sub" }, t("npSub")), q,
    h("div", { class: "row" }, seg, go, h("span", { class: "muted small" }, t("npSizeHint"))), out);
}

const ATTR_RU = { Str: "силы", Dex: "ловкости", Int: "интеллекта" };
const attrName = (a) => (LANG === "ru" ? ATTR_RU[a] || a : a);

// ---------- feedback: the player's report with the open build, mailed to the author (poe2lab/feedback.py) ----------
const fbDraft = { message: "", contact: "", images: [], attachLog: false };  // kept while the page is open, so leaving the form loses nothing
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
  state.page = "feedback";
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

  // the end of poe2lab's log: goes when ticked; what it holds can be read first
  const logBox = h("pre", { class: "fb-log hidden" });
  const logTick = h("input", { type: "checkbox", onchange: () => { fbDraft.attachLog = logTick.checked; } });
  logTick.checked = fbDraft.attachLog;
  const logRow = h("div", { class: "small fb-log-row" }, h("label", {}, logTick, " ", t("fbLog")), " ",
    h("button", { class: "link small", onclick: async () => {
      if (!logBox.classList.contains("hidden")) { logBox.classList.add("hidden"); return; }
      try {
        const r = await api("/api/log");
        logBox.textContent = r.text || t("fbLogEmpty");
        logBox.title = r.path;
      } catch (e) { logBox.textContent = e.message; }
      logBox.classList.remove("hidden");
    } }, t("fbLogShow")));

  const blocked = status.outdated ? t("fbRestart") : !state.build ? t("fbNeedBuild") : !status.configured ? t("fbOff") : null;
  const send = h("button", { class: "primary", disabled: Boolean(blocked), onclick: async () => {
    if (fbDraft.message.trim().length < 5) { message.focus(); toast(t("fbEmpty")); return; }
    send.disabled = true;
    send.textContent = t("fbSending");
    try {
      await api("/api/feedback", { method: "POST", body: { message: fbDraft.message, contact: fbDraft.contact,
        images: fbDraft.images, tab: state.tab, mode: state.mode, lang: LANG, attachLog: fbDraft.attachLog } });
      fbDraft.message = "";
      fbDraft.images = [];
      fbDraft.attachLog = false;
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
    message, drop, picker, thumbs, contact, logRow, logBox,
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
  $("#settings-open").classList.toggle("attn", LANG === "ru" && !!st && !ruReady());
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
      await Promise.all([loadGameTexts(), loadIcons(), loadCurrency()]);
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

// ---------- the build author's constructor (poe2lab/author.py) ----------
// Every tab shows what poe2lab worked out; the build's author changes it. The "Constructor" button over the tabs
// opens the blocks for editing and a drawer with one search over everything the game has: a gem, a unique, a base,
// a rune, a passive or a term is dragged (or clicked, or typed after "@") into a note, where it stands as one piece
// - [[kind:id]] in the saved text - and shows its picture and its card on hover. A list poe2lab made (a stage's
// skills) can be replaced by the author's own; "auto" brings poe2lab's back.
const AU = { build: null, blocks: {}, edit: false, target: null, range: null, kinds: null, timers: {}, details: new Map(),
  terms: null, status: null };
const AU_KINDS = ["gem", "support", "unique", "base", "rune", "passive", "term"];
// what the drawer looks for first on each tab
const AU_TABS = { overview: null, skills: ["gem", "support"], gear: ["unique", "base", "rune"], tree: ["passive"] };
const AU_MIME = "application/x-poe2lab-token";
const AU_TOKEN = /\[\[(gem|support|unique|base|rune|passive|term):([^[\]\n]{1,200})\]\]/g;

// the open build's blocks, read once per build; another build closes the constructor
async function authorLoad() {
  if (!state.build || AU.build === state.build.name) return;
  AU.build = state.build.name;
  AU.blocks = {};
  if (AU.edit) authorToggle(false, false);
  try { AU.blocks = (await api(`/api/author?${buildQuery()}`)).blocks || {}; } catch (_) { /* no notes: poe2lab's picture alone */ }
  if (Object.keys(AU.blocks).length) loadAllGems();
}
const auBlock = (id) => AU.blocks[id] || {};

// a block changed: kept at once in the page, written to the build's profile a moment after the last keystroke
function auSave(id, patch) {
  const b = { ...auBlock(id), ...patch };
  for (const k of Object.keys(b)) if (b[k] === undefined || b[k] === "") delete b[k];
  AU.blocks[id] = b;
  clearTimeout(AU.timers[id]);
  auStatus("saving");
  AU.timers[id] = setTimeout(async () => {
    try {
      const r = await api(`/api/author/block?${buildQuery()}`, { method: "PUT", body: { id, ...AU.blocks[id] } });
      if (r.block) AU.blocks[id] = r.block; else delete AU.blocks[id];
      auStatus("saved");
    } catch (e) { toast(e.message); auStatus("error"); }
  }, 600);
}
function auStatus(s) {
  AU.status = s;
  const el = document.querySelector("#au-drawer .au-status");
  if (el) { el.textContent = t("auStatus_" + s); el.className = "au-status " + s; }
}

// ---- a token: its name, picture and card ----
const auSplit = (tok) => { const i = tok.indexOf(":"); return [tok.slice(0, i), tok.slice(i + 1)]; };
function auName(kind, id) {
  if (kind === "passive") return trName(id.split("|").slice(1).join("|") || id);
  if (kind === "term") return termName(id);
  if (kind === "unique") return trItem(id);
  return trName(id);
}
function auIcon(kind, id) {
  if (kind === "gem" || kind === "support") return icon(id);
  if (kind === "passive") return icon(id.split("|").slice(1).join("|"), "ico passive");
  if (kind === "unique") return itemIcon(id, null, "unique");
  if (kind === "base") return itemIcon(id, id, "normal");
  if (kind === "rune") return icon(id) || I("jewel", "tok-ic");
  return I("book", "tok-ic");
}
// what a token's card shows (a gem's card is the Skills tab's; the rest asked from the server once)
function auTip(kind, id) {
  if (kind === "gem" || kind === "support") { loadAllGems(); return gemTipCard(id); }
  const key = `${kind}:${id}`;
  const box = h("div", { class: "stack" }, h("b", {}, auName(kind, id)));
  const fill = (d) => {
    if (!d) return;
    if (kind === "unique") box.replaceChildren(uniqueTip(id, d.base, d.lines), h("div", { class: "muted small" }, trName(d.base), d.level ? ` · ${t("lrLv", d.level)}` : ""));
    else if (kind === "base") box.replaceChildren(linesTip(itemIcon(id, id, "normal"), trName(id),
      (Array.isArray(d.implicit) ? d.implicit : d.implicit ? [d.implicit] : []).map((l) => h("li", {}, trMod(l))), d.level ? t("lrLv", d.level) : null));
    else if (kind === "rune") box.replaceChildren(h("div", { class: "row", style: "gap:8px;align-items:center" }, auIcon(kind, id), h("b", {}, trName(id))),
      ...Object.entries(d.targets || {}).map(([k, lines]) => h("div", { class: "small" }, h("span", { class: "muted" }, t("auTarget", k), ": "),
        lines.map(trMod).join("; "))), d.level ? h("div", { class: "muted small" }, t("lrLv", d.level)) : null);
    else if (kind === "passive") box.replaceChildren(h("div", { class: "row", style: "gap:8px;align-items:center" }, auIcon(kind, id), h("b", {}, trName(d.name))),
      h("div", { class: "muted small" }, d.type === "Keystone" ? t("keystone") : d.type === "Notable" ? t("notable") : d.type, d.asc ? ` · ${trName(d.asc)}` : ""), stats(d.stats || []));
    else if (kind === "term") box.replaceChildren(h("b", {}, LANG !== "en" && d.nameLocal ? d.nameLocal : d.name),
      h("div", { class: "small" }, termText(LANG !== "en" && d.textLocal ? d.textLocal : d.text)));
  };
  if (AU.details.has(key)) fill(AU.details.get(key));
  else {
    box.append(h("div", { class: "muted small" }, t("auLoadingTip")));
    api(`/api/lookup/item?kind=${kind}&id=${encodeURIComponent(id)}&lang=${LANG}&${buildQuery()}`)
      .then((d) => { AU.details.set(key, d); fill(d); }).catch(() => {});
  }
  return box;
}
// the glossary's terms by id, for a term's name in a saved text
function auTerms() {
  if (!AU.terms) AU.terms = api(`/api/glossary?lang=${LANG}`).then((g) => { for (const [k, v] of Object.entries(g.terms)) if (!TERMS[k]) TERMS[k] = v; })
    .catch(() => { AU.terms = null; });
  return AU.terms;
}
function auChip(kind, id, inEditor = false) {
  const name = h("span", { class: "tok-n" }, auName(kind, id));
  if (kind === "term" && !TERMS[id]) auTerms()?.then(() => { name.textContent = auName(kind, id); });
  const el = h("span", { class: `tok tok-${kind}`, "data-kind": kind, "data-id": id, contenteditable: inEditor ? "false" : null },
    auIcon(kind, id), name);
  return hoverTip(el, () => auTip(kind, id));
}
const auTokChip = (tok, inEditor) => auChip(...auSplit(tok), inEditor);

// a text with tokens as the page shows it: words, line breaks, the tokens as pieces
function auRich(text, inEditor = false) {
  const out = [];
  let last = 0;
  const plain = (s) => s.split("\n").forEach((line, i) => { if (i) out.push(h("br")); if (line) out.push(document.createTextNode(line)); });
  for (const m of text.matchAll(AU_TOKEN)) {
    plain(text.slice(last, m.index));
    out.push(auChip(m[1], m[2], inEditor));
    last = m.index + m[0].length;
  }
  plain(text.slice(last));
  return out;
}

// ---- the editor: a text field the tokens go into ----
function auSerialize(ed) {
  let out = "";
  const walk = (node) => {
    for (const c of node.childNodes) {
      if (c.nodeType === 3) out += c.nodeValue.replace(/​/g, "").replace(/ /g, " ");
      else if (c.nodeName === "BR") out += "\n";
      else if (c.classList && c.classList.contains("tok")) out += `[[${c.dataset.kind}:${c.dataset.id}]]`;
      else {
        if (/^(DIV|P)$/.test(c.nodeName) && out && !out.endsWith("\n")) out += "\n";
        walk(c);
      }
    }
  };
  walk(ed);
  return out.replace(/\s+$/, "");
}
function auKeepRange(ed) {
  const sel = getSelection();
  if (sel.rangeCount && ed.contains(sel.getRangeAt(0).startContainer)) AU.range = sel.getRangeAt(0).cloneRange();
}
function auInsert(ed, nodes) {
  let r = AU.range && ed.contains(AU.range.startContainer) ? AU.range : null;
  if (!r) { r = document.createRange(); r.selectNodeContents(ed); r.collapse(false); }
  r.deleteContents();
  const frag = document.createDocumentFragment();
  nodes.forEach((n) => frag.append(n));
  const last = frag.lastChild;
  r.insertNode(frag);
  const after = document.createRange();
  after.setStartAfter(last);
  after.collapse(true);
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(after);
  AU.range = after.cloneRange();
  ed.focus();
}
// a no-break space after the piece: a plain one beside it would be swallowed by the next typing
const auInsertToken = (ed, tok) => auInsert(ed, [auTokChip(tok, true), document.createTextNode(" ")]);
function auEditor(text, onChange, placeholder) {
  const ed = h("div", { class: "au-ed", contenteditable: "true", role: "textbox", "aria-multiline": "true", "data-ph": placeholder, spellcheck: "true" },
    ...auRich(text || "", true));
  const changed = () => { ed.classList.toggle("au-empty", !auSerialize(ed)); onChange(auSerialize(ed)); };
  ed.classList.toggle("au-empty", !text);
  const target = { type: "text", el: ed, add: (tok) => { auInsertToken(ed, tok); changed(); } };
  // the field the drawer's next pick goes into: the one last typed or clicked in
  const claim = () => { if (AU.target !== target) { AU.target = target; auMarkTarget(ed); auKinds(AU_TABS[state.tab] || null); } };
  for (const ev of ["focus", "mousedown", "keydown"]) ed.addEventListener(ev, claim);
  ed.addEventListener("input", () => { claim(); auKeepRange(ed); changed(); });
  ed.addEventListener("keyup", () => auKeepRange(ed));
  ed.addEventListener("mouseup", () => auKeepRange(ed));
  ed.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); document.execCommand("insertLineBreak"); auKeepRange(ed); changed(); }
    else if (e.key === "@") { e.preventDefault(); auKeepRange(ed); auPopup(ed, (tok) => { auInsertToken(ed, tok); changed(); }); }
  });
  ed.addEventListener("paste", (e) => {
    e.preventDefault();
    auKeepRange(ed);
    const s = e.clipboardData.getData("text/plain");
    if (s) { auInsert(ed, auRich(s, true)); changed(); }
  });
  ed.addEventListener("dragover", (e) => { if (e.dataTransfer.types.includes(AU_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } });
  ed.addEventListener("drop", (e) => {
    const tok = e.dataTransfer.getData(AU_MIME);
    if (!tok) return;
    e.preventDefault();
    const pos = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY)
      : document.caretPositionFromPoint ? (() => { const p = document.caretPositionFromPoint(e.clientX, e.clientY); const r = document.createRange(); r.setStart(p.offsetNode, p.offset); return r; })() : null;
    if (pos && ed.contains(pos.startContainer)) AU.range = pos;
    auInsertToken(ed, tok);
    changed();
  });
  return ed;
}
// where a click in the drawer puts its piece: that field glows
function auMarkTarget(el) {
  document.querySelectorAll(".au-target").forEach((x) => x.classList.remove("au-target"));
  if (el) el.classList.add("au-target");
}

// "@" in a text: a small search at the caret, Enter or a click puts the piece there
function auPopup(ed, pick) {
  document.querySelector(".au-pop")?.remove();
  const at = (AU.range && AU.range.getBoundingClientRect()) || ed.getBoundingClientRect();
  const input = h("input", { class: "au-q", placeholder: t("auSearchPh") });
  const list = h("div", { class: "au-pop-list" });
  const pop = h("div", { class: "au-pop card", style: `left:${Math.min(at.left, innerWidth - 340)}px;top:${Math.min(at.bottom + 6, innerHeight - 300)}px` }, input, list);
  let rows = [], sel = 0;
  const close = () => { pop.remove(); document.removeEventListener("mousedown", outside, true); ed.focus(); };
  const outside = (e) => { if (!pop.contains(e.target)) close(); };
  const choose = (r) => { close(); pick(`${r.kind}:${r.id}`); };
  const draw = () => list.replaceChildren(...(rows.length ? rows.map((r, i) => auRow(r, () => choose(r), i === sel, input.value))
    : [h("div", { class: "muted small au-none" }, input.value.trim() ? t("auNothing") : t("auTypeHint"))]));
  const search = auSearcher((r) => { rows = r; sel = 0; draw(); });
  input.addEventListener("input", () => search(input.value, null));  // "@" looks through everything
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(rows.length - 1, sel + 1); draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); if (rows[sel]) choose(rows[sel]); }
  });
  document.body.append(pop);
  document.addEventListener("mousedown", outside, true);
  draw();
  input.focus();
}

// the search, asked a moment after the last keystroke; only the latest answer is shown
function auSearcher(show) {
  let timer = null, seq = 0;
  return (q, kinds) => {
    clearTimeout(timer);
    const my = ++seq;
    if (!q.trim()) { show([]); return; }
    timer = setTimeout(async () => {
      try {
        const r = await api(`/api/lookup?q=${encodeURIComponent(q)}&kinds=${(kinds || []).join(",")}&lang=${LANG}&limit=40&${buildQuery()}`);
        if (my === seq) show(r);
      } catch (e) { if (my === seq) show([]); }
    }, 140);
  };
}
// one search result: the piece as it will stand in the text, what it is and its tags (the ones the query found it
// by lit); dragged or clicked
function auRow(r, onPick, on = false, q = "") {
  const tok = `${r.kind}:${r.id}`;
  const sub = r.kind === "passive" ? (r.sub === "Keystone" ? t("keystone") : r.sub === "Notable" ? t("notable") : r.sub === "Socket" ? t("auSocket") : trName(r.sub))
    : r.kind === "unique" || r.kind === "base" ? trName(r.sub) : "";
  const words = q.toLowerCase().replace(/ё/g, "е").split(/\s+/).filter(Boolean);
  const hit = (tag) => words.some((w) => tag.toLowerCase().replace(/ё/g, "е").split(/\s+/).some((x) => x.startsWith(w)));
  const tags = (r.tags || []).filter((x) => x.toLowerCase() !== String(sub).toLowerCase());
  // the tags the query matched first, then the rest, a few
  const shown = [...tags.filter(hit), ...tags.filter((x) => !hit(x))].slice(0, 7);
  return h("div", { class: "au-row" + (on ? " on" : ""), draggable: "true", title: t("auRowHint"),
    ondragstart: (e) => { hideTip(); e.dataTransfer.setData(AU_MIME, tok); e.dataTransfer.setData("text/plain", `[[${tok}]]`); e.dataTransfer.effectAllowed = "copy"; },
    onmousedown: (e) => e.preventDefault(),  // the text keeps its caret
    onclick: onPick },
  auTokChip(tok), h("span", { class: "au-row-k" }, t("auKind_" + r.kind), sub ? ` · ${sub}` : ""),
  shown.length ? h("span", { class: "au-row-tags" }, shown.map((x) => h("span", { class: "au-tag" + (hit(x) ? " hit" : "") }, x))) : null);
}

// ---- the drawer: the search beside the page while the constructor is on ----
function auDrawer() {
  let d = $("#au-drawer");
  if (d) return d;
  const input = h("input", { class: "au-q", placeholder: t("auSearchPh") });
  const kinds = h("div", { class: "au-kinds" });
  const list = h("div", { class: "au-list-r" });
  const show = (rows) => list.replaceChildren(...(rows.length ? rows.map((r) => auRow(r, () => auPut(`${r.kind}:${r.id}`), false, input.value))
    : [h("div", { class: "muted small au-none" }, input.value.trim() ? t("auNothing") : t("auTypeHint"))]));
  const search = auSearcher(show);
  const drawKinds = () => kinds.replaceChildren(...[null, ...AU_KINDS].map((k) => h("button", {
    class: "au-kind" + ((k === null ? !AU.kinds : AU.kinds && AU.kinds.includes(k)) ? " on" : ""),
    onclick: () => { AU.kinds = k ? [k] : null; drawKinds(); search(input.value, AU.kinds); input.focus(); } }, t("auKind_" + (k || "all")))));
  input.addEventListener("input", () => search(input.value, AU.kinds));
  d = h("aside", { id: "au-drawer", class: "au-drawer hidden" },
    h("div", { class: "au-head" }, I("pencil", "c-gold"), h("b", {}, t("auTitle")), h("span", { class: "au-status" }),
      h("button", { class: "icon-btn sm", title: t("auClose"), onclick: () => authorToggle(false) }, I("x", "ic-s"))),
    h("div", { class: "muted small au-help" }, t("auHelp")),
    input, kinds, list);
  d.drawKinds = drawKinds;
  d.search = () => search(input.value, AU.kinds);
  d.input = input;
  document.body.append(d);
  show([]);
  return d;
}
// what the drawer looks for: a list's "+" narrows it to what the list holds, a text brings back the tab's
function auKinds(kinds) {
  const same = JSON.stringify(kinds) === JSON.stringify(AU.kinds);
  AU.kinds = kinds;
  if (!same && AU.edit) { const d = auDrawer(); d.drawKinds(); d.search(); }
}
// a piece clicked in the drawer: into the field the author was in (its caret), or the list whose "+" was pressed
function auPut(tok) {
  const tg = AU.target;
  if (!tg || !document.body.contains(tg.el)) { toast(t("auPickTarget")); return; }
  tg.add(tok);
}
// the constructor on or off: the blocks open for editing, the drawer with the tab's kinds of things first
function authorToggle(on = !AU.edit, redraw = true) {
  AU.edit = on;
  document.body.classList.toggle("au-on", on);
  const d = auDrawer();
  d.classList.toggle("hidden", !on);
  $("#author-btn")?.classList.toggle("is-on", on);
  if (on) { AU.kinds = AU_TABS[state.tab] || null; d.drawKinds(); d.search(); auStatus(AU.status || "idle"); }
  else { AU.target = null; document.querySelector(".au-pop")?.remove(); }
  if (redraw && state.build) switchTab(state.tab);
}
// the button over the tabs: only where there are blocks to change
function auButton() {
  const b = $("#author-btn");
  if (!b) return;
  b.classList.toggle("hidden", !state.build || !(state.tab in AU_TABS));
  b.classList.toggle("is-on", AU.edit);
  if (AU.edit) {
    AU.kinds = AU_TABS[state.tab] || null;
    const d = auDrawer();
    d.drawKinds();
    d.search();
  }
}

// ---- the blocks ----
// the author's note under a block: nothing when empty (until the constructor is on)
function auNote(id, ph, badge = true) {
  const text = auBlock(id).text || "";
  if (!AU.edit) return text ? h("div", { class: "au-note" }, badge ? h("span", { class: "au-badge", title: t("auByAuthor") }, I("pencil", "ic-s")) : null,
    h("div", { class: "au-text" }, ...auRich(text))) : null;
  return h("div", { class: "au-note is-edit" }, auEditor(text, (v) => auSave(id, { text: v }), ph || t("auNotePh")));
}
// a card of its own for a block with nothing else in it (the build's description, a slot's note)
function auCard(id, title, ph) {
  const note = auNote(id, ph, false);  // the card's title has the pencil
  if (!note) return null;
  return h("div", { class: "card au-card" + (AU.edit ? " is-edit" : "") }, h("h3", {}, I("pencil", "c-gold"), " ", title), note);
}
// a list poe2lab made (`auto`: tokens; `autoNodes`: how the page shows them) or the author's own instead; the
// constructor on: each piece with a cross, a "+" that takes the drawer's next pick, poe2lab's list back on "auto"
function auList(id, auto, autoNodes, kinds) {
  const own = auBlock(id).list;
  if (!AU.edit) return own ? own.map((tok) => h("span", { class: "lr-skill" }, auTokChip(tok))) : autoNodes;
  let cur = own ? [...own] : [...auto];
  const box = h("div", { class: "au-list" + (own ? " own" : "") });
  const commit = () => { auSave(id, { list: cur }); draw(); };
  const target = { type: "list", el: box, add: (tok) => { if (!cur.includes(tok)) { cur.push(tok); commit(); } } };
  const draw = () => {
    box.classList.toggle("own", !!auBlock(id).list);
    box.replaceChildren(...cur.map((tok) => h("span", { class: "au-li" }, auTokChip(tok),
      h("button", { class: "au-x", title: t("auRemove"), onclick: () => { cur = cur.filter((x) => x !== tok); commit(); } }, "×"))),
    h("button", { class: "au-add", title: t("auAddHint"), onclick: () => {
      AU.target = target; auMarkTarget(box);
      auKinds(kinds || AU.kinds);
      auDrawer().input.focus();
    } }, "+ ", t("auAdd")),
    ...(auBlock(id).list ? [h("button", { class: "au-auto", title: t("auAutoHint"), onclick: () => { cur = [...auto]; auSave(id, { list: undefined }); draw(); } }, "↺ ", t("auAuto"))] : []));
  };
  box.addEventListener("dragover", (e) => { if (e.dataTransfer.types.includes(AU_MIME)) { e.preventDefault(); box.classList.add("drop"); } });
  box.addEventListener("dragleave", () => box.classList.remove("drop"));
  box.addEventListener("drop", (e) => {
    box.classList.remove("drop");
    const tok = e.dataTransfer.getData(AU_MIME);
    if (tok) { e.preventDefault(); target.add(tok); }
  });
  draw();
  return [box];
}

// ---------- start ----------
(async function start() {
  applyStaticTexts();
  renderEmpty();
  await Promise.all([loadGameTexts(), loadIcons(), loadCurrency()]);
  loadGameDataStatus();
  const s = await loadStatus();
  const wanted = readHash();
  if (wanted && wanted !== s.build) {
    await openBuild(wanted);
  } else if (s.loaded) {
    try { state.build = await api("/api/build"); renderHeader(); switchTab(wanted ? state.tab : "overview"); } catch (_) { /* reopen from the list */ }
  }
  await loadBuildList();
  loadLeagues();
})();
