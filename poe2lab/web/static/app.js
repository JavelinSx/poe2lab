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
const icon = (name, cls = "ico") => (name && ICONS[name]
  ? h("img", { class: cls, src: `/icons/${ICONS[name]}`, alt: "" }) : null);

const loading = (text) => h("div", { class: "loading" }, h("div", { class: "spinner" }), text);

const DMG_COLOR = { Physical: "var(--phys)", Fire: "var(--fire)", Cold: "var(--cold)", Lightning: "var(--lightning)", Chaos: "var(--chaos)" };
const METRIC = [["dps", "m_dps"], ["phys_hit", "m_phys"], ["fire_hit", "m_fire"], ["cold_hit", "m_cold"],
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
  document.querySelectorAll("#lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === LANG));
}

$("#lang").addEventListener("click", async (e) => {
  const l = e.target.dataset.lang;
  if (!l || l === LANG) return;
  LANG = l;
  try { localStorage.setItem("poe2lab.lang", l); } catch (_) { /* storage blocked */ }
  applyStaticTexts();
  await loadGameTexts();
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
  $("#build-header").classList.add("hidden");
  $("#tabs").classList.add("hidden");
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
  setBuildNames(b);
  $("#build-header").classList.remove("hidden");
  $("#tabs").classList.remove("hidden");
  $("#bh-name").textContent = b.name;
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
$("#refresh-builds").addEventListener("click", loadBuildList);

const TABS = {};

async function switchTab(tab) {
  state.tab = tab;
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
        h("th", { class: "num" }, t("hitCrit")), h("th", { class: "num" }, t("hitJuiced")))),
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

  const path = h("div", { class: "card" }, h("h3", {}, t("craftTitle")), h("div", { class: "sub" }, t("craftSub")),
    g.craftPath.length ? h("div", { class: "steps" }, g.craftPath.map((s) => h("div", { class: "step" }, h("div", {},
      h("div", { class: "what" }, chip("tag", slotName(s.slot)), " ",
        s.removed.length ? h("span", {}, h("span", { class: "mod muted" }, trMod(s.removed.join(" / "))), " → ") : t("craftAdd"),
        h("span", { class: "mod" }, trMod(s.added.join(" / ")))),
      deltas(s.changes),
      s.sources.length ? h("div", { class: "src" }, t("from") + s.sources.map(trSource).join(" · ")) : null)))) : h("p", { class: "muted" }, t("nothingToCraft")));

  const socketCard = h("div", { class: "card" }, h("h3", {}, t("socketsTitle")),
    h("div", { class: "sub" }, t("socketsSub") + (g.prices ? t("prices", trName(g.prices.league)) : "")),
    g.sockets.length ? g.sockets.map((s) => h("div", { style: "margin-bottom:12px" },
      h("div", {}, chip("tag", slotName(s.slot)), t("socketNow", s.index), h("b", {}, trName(s.current)), h("span", { class: "muted" }, t("gives", fmt(s.current_score, 1)))),
      s.best.length ? h("table", {}, h("tbody", {}, s.best.map((o) => h("tr", {},
        h("td", {}, h("div", {}, trName(o.name)), h("div", { class: "mod muted" }, trMod(o.lines.join(" / ")))),
        h("td", {}, deltas(o.changes)), h("td", { class: "num" }, trFree(o.price || ""))))))
        : h("div", { class: "muted small" }, t("nothingBetter"))))
      : h("p", { class: "muted" }, t("noSockets")));

  const cards = g.slots.map((p) => {
    const max = Math.max(...p.affixes.map((a) => a.score), 1);
    return h("div", { class: "card" },
      h("div", { class: "slot-head" }, h("div", {}, h("div", { class: "slot" }, slotName(p.slot)), h("h3", { title: p.item }, trItem(p.item))),
        chip(p.corrupted ? "must" : "tag", p.corrupted ? t("corrupted") : t("craftable"))),
      h("div", { class: "sub" }, t("affixCount", { ...p, base: trName(p.base) }) + (p.uncertain ? t("approx") : "")),
      p.affixes.map((a) => h("div", { class: "affix" },
        h("div", { class: "kind" }, a.type === "Prefix" ? t("prefix") : t("suffix")),
        h("div", {}, h("span", { class: "mod", title: a.lines.join(" / ") }, trMod(a.lines.join(" / "))), h("span", { class: "tier" }, `${LANG === "ru" ? "тир " : "T"}${a.tier}/${a.tiers}`),
          a.holds.length ? h("div", {}, chip("hold", t("holds") + a.holds.map(trFree).join(", "))) : null,
          a.utility ? h("div", {}, chip("util", t("utility"))) : null),
        scoreBar(a.score, max))),
      p.actions.length ? h("div", { class: "actions" }, p.actions.map((x) => h("div", { class: "action" }, trFree(x)))) : null);
  });

  return h("div", { class: "stack" }, h("div", { class: "grid two" }, path, socketCard),
    h("div", { class: "section-title" }, t("slots")), h("div", { class: "grid cards" }, cards));
};

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
  const itemName = (it) => (it ? h("span", { title: it.name }, trItem(it.name)) : h("span", { class: "muted" }, "—"));
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
      h("thead", {}, h("tr", {}, h("th", {}, t("node")), h("th", { class: "num" }, t("points")), h("th", {}, t("perPoint")), h("th", {}, t("treeGives")))),
      h("tbody", {}, r.growth.map((g) => h("tr", {},
        h("td", {}, h("div", {}, nodeName(g), " ", typeChip(g.type)), stats(g.stats),
          g.via.length ? h("div", { class: "hint" }, t("via", [...new Set(g.via.map(trName))].join(", "))) : null),
        h("td", { class: "num" }, g.points),
        h("td", {}, scoreBar(g.perPoint, maxValue)),
        h("td", {}, deltas(g.changes, METRIC, 0.3))))))
      : h("p", { class: "muted" }, t("treeNothing")));

  const branchRow = (b) => h("tr", {},
    h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type)), stats(b.stats)),
    h("td", { class: "num" }, b.points), h("td", {}, deltas(b.changes, METRIC, 0.3)));
  const respec = h("div", { class: "card" }, h("h3", {}, t("treeRespec")), h("div", { class: "sub" }, t("treeRespecSub")),
    r.respec.length ? h("table", { class: "versus-items" },
      h("thead", {}, h("tr", {}, h("th", {}, t("branch")), h("th", { class: "num" }, t("freed")), h("th", {}, t("youLose")))),
      h("tbody", {}, r.respec.map(branchRow)))
      : h("p", { class: "muted" }, t("treeNoRespec")));

  const listCard = (title, sub, list) => list.length ? h("div", { class: "card" },
    h("details", {}, h("summary", {}, `${title} (${list.length})`), h("div", { class: "sub", style: "margin-top:8px" }, sub),
      h("table", { class: "versus-items" }, h("tbody", {}, list.map((b) => h("tr", {},
        h("td", {}, h("div", {}, nodeName(b), " ", typeChip(b.type)), stats(b.stats)), h("td", { class: "num" }, t("pointsN", b.points)))))))) : null;

  return h("div", { class: "stack" },
    h("div", { class: "sub" }, t("treeIntro", r.allocated)),
    growth, respec,
    listCard(t("treeUnseen"), t("treeUnseenSub"), r.unseen),
    listCard(t("treeAttributes"), t("treeAttributesSub"), r.attributes));
};

// ---------- mechanics ----------
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

// ---------- start ----------
(async function start() {
  applyStaticTexts();
  renderEmpty();
  await Promise.all([loadGameTexts(), loadIcons()]);
  const s = await loadStatus();
  if (s.loaded) {
    try { state.build = await api("/api/build"); renderHeader(); switchTab("overview"); } catch (_) { /* reopen from the list */ }
  }
  await loadBuildList();
})();
