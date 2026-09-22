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
    const builds = await api("/api/builds");
    box.replaceChildren();
    if (!builds.length) box.append(h("div", { class: "muted small" }, t("noBuilds")));
    for (const b of builds) {
      box.append(h("button", {
        class: "build-item" + (state.build && state.build.name === b.name ? " active" : ""),
        onclick: () => openBuild(b.name),
      },
      h("div", { class: "bi-name" }, b.name),
      h("div", { class: "bi-kind" }, (b.kind === "pob" ? t("savedInPob") : t("pobCode")) + (b.hasProfile ? " · " + t("withProfile") : ""))));
    }
  } catch (e) { box.replaceChildren(h("div", { class: "muted small" }, e.message)); }
}

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
  const sel = $("#main-skill");
  sel.replaceChildren();
  for (const g of b.groups) {
    g.skills.forEach((s, i) => {
      const opt = h("option", { value: `${g.index}:${i + 1}` }, `${g.index}. ${trName(s)}`);
      if (b.info.mainSocketGroup === g.index && b.mainSkill === s) opt.selected = true;
      sel.append(opt);
    });
  }
}

$("#main-skill").addEventListener("change", (e) => {
  const [g, s] = e.target.value.split(":").map(Number);
  openBuild(state.build.name, g, s);
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
  const maxHit = Math.max(...hits.map(([, v]) => v.normal));

  const kpi = h("div", { class: "grid kpi" },
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("dps")),
      h("div", { class: "value" }, fmt(rng.low), rng.high > rng.low ? h("span", { class: "to" }, ` … ${fmt(rng.high)}`) : null),
      h("div", { class: "note" }, rng.high > rng.low ? t("dpsRangeNote") : trName(r.build.mainSkill))),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("life")), h("div", { class: "value" }, fmt(b.life))),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("hitChance")), h("div", { class: "value" }, fmt(b.hitChance) + "%")),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, t("recovery")),
      h("div", { class: "value" }, fmt(b.recoveryPerSecond), h("span", { class: "to" }, t("perSec"))),
      h("div", { class: "note" }, t("whileAttacking"))));

  const hitCard = h("div", { class: "card" },
    h("h3", {}, t("hitsTitle")), h("div", { class: "sub" }, t("hitsSub", r.profile)),
    h("div", { class: "hits" }, hits.map(([type, v]) => {
      const c = DMG_COLOR[type];
      const seg = (cls, val) => h("div", { class: "seg " + cls, style: `width:${(val / maxHit) * 100}%;background:${c}` });
      return h("div", { class: "hit-row" },
        h("div", { class: "hit-name", style: `color:${c}` }, t("dmg_" + type)),
        h("div", { class: "hit-bar" }, seg("normal", v.normal), seg("crit", v.crit), seg("juiced", v.juiced)),
        h("div", { class: "hit-vals" }, `${fmt(v.normal)} · ${fmt(v.crit)} · ${fmt(v.juiced)}`));
    })),
    h("div", { class: "legend" }, h("span", {}, h("i", { style: "opacity:.35" }), t("hitNormal")),
      h("span", {}, h("i", { style: "opacity:.6" }), t("hitCrit")), h("span", {}, h("i", {}), t("hitJuiced"))));

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
    h("div", { class: "sub" }, t("socketsSub") + (g.prices ? t("prices", g.prices.league) : "")),
    g.sockets.length ? g.sockets.map((s) => h("div", { style: "margin-bottom:12px" },
      h("div", {}, chip("tag", slotName(s.slot)), t("socketNow", s.index), h("b", {}, trName(s.current)), h("span", { class: "muted" }, t("gives", fmt(s.current_score, 1)))),
      s.best.length ? h("table", {}, h("tbody", {}, s.best.map((o) => h("tr", {},
        h("td", {}, h("div", {}, trName(o.name)), h("div", { class: "mod muted" }, trMod(o.lines.join(" / ")))),
        h("td", {}, deltas(o.changes)), h("td", { class: "num" }, o.price || "")))))
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
TABS.compare = async () => {
  const slots = state.build.items.filter((i) => !["Flask", "Charm", "Jewel"].includes(i.type)).map((i) => i.slot);
  const slotSel = h("select", {}, slots.map((s) => h("option", { value: s }, slotName(s))));
  const text = h("textarea", { rows: 16, placeholder: t("candidatePh") });
  const be = h("input", { type: "text", placeholder: t("breakevenPh"), style: "width:100%" });
  const out = h("div", {});
  const run = h("button", { class: "primary", onclick: async () => {
    run.disabled = true;
    out.replaceChildren(loading(t("counting")));
    try {
      const r = await api("/api/compare", { method: "POST", body: { slot: slotSel.value, text: text.value, breakeven: be.value.trim() || null } });
      const ch = { dps: r.dps_pct, phys_hit: r.hit_pct.Physical, fire_hit: r.hit_pct.Fire, cold_hit: r.hit_pct.Cold, lightning_hit: r.hit_pct.Lightning, chaos_hit: r.hit_pct.Chaos, recovery: r.recovery_pct };
      const verdict = r.dps_pct > 0.5 ? t("better") : r.dps_pct < -0.5 ? t("worse") : t("same");
      out.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("verdict", verdict)),
        deltas(ch, METRIC, 0.05), r.life_pct ? h("p", {}, t("lifeDelta", pct(r.life_pct))) : null,
        Object.entries(r.unmet_requirements).map(([a, [have, need]]) => h("p", {}, chip("must", t("reqShort", attrName(a), have, need)))),
        r.breakeven !== undefined ? h("p", {}, r.breakeven ? t("beOk", trMod(r.breakeven.line), fmt(r.breakeven.factor * 100)) : t("beBad")) : null));
    } catch (e) { out.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
    run.disabled = false;
  } }, t("compare"));
  const current = h("button", { class: "ghost", onclick: async () => { text.value = (await api(`/api/item/${encodeURIComponent(slotSel.value)}`)).text; } }, t("insertCurrent"));
  return h("div", { class: "grid two" },
    h("div", { class: "card stack" }, h("h3", {}, t("candidate")),
      h("label", { class: "field" }, h("span", {}, t("slot")), slotSel), text,
      h("label", { class: "field" }, h("span", {}, t("breakeven")), be),
      h("div", { class: "row" }, run, current)),
    out);
};

// ---------- mechanics ----------
TABS.mechanics = async (view) => {
  view.replaceChildren(loading(t("collecting")));
  const m = await cached("mechanics", () => api(`/api/mechanics?${buildQuery()}`));
  const where = (w) => trFree(w.replace(/группа (\d+)/, (_, n) => `${t("group")} ${n}`))
    .replace(/\(([^()]+)\)$/, (all, s) => (SLOT_RU[s] !== undefined ? `(${slotName(s)})` : all));
  // in Russian mode show only what has an official translation; the English original stays in the tooltip
  const line = (text) => h("div", { title: text }, trMod(text));
  const gap = (g) => h("div", { class: "gap" }, h("div", { class: "where" }, where(g.where)), line(g.text),
    LANG === "en" && g.what !== g.text ? h("div", { class: "stat" }, g.what) : null);
  // raw internal stat ids ("stat_name = 20") mean nothing to a player; the English view keeps them
  const shown = m.gaps.filter((g) => LANG === "en" || !/^[a-z0-9_%+]+ = /.test(g.text));
  const impact = shown.filter((g) => g.likely_impact);
  const rest = shown.filter((g) => !g.likely_impact);
  return h("div", { class: "grid two" },
    h("div", { class: "card" }, h("h3", {}, t("gapsTitle")), h("div", { class: "sub" }, t("gapsSub")),
      impact.map(gap), rest.length ? h("details", {}, h("summary", {}, t("other", rest.length)), rest.map(gap)) : null),
    h("div", { class: "card" }, h("h3", {}, t("skillsTitle")), h("div", { class: "sub" }, t("skillsSub")),
      m.skills.filter((s) => !s.support).map((s) => h("details", {}, h("summary", {}, `${s.group}. ${trName(s.name)}`),
        s.description && LANG === "en" ? h("p", { class: "muted small" }, s.description) : null,
        h("ul", {}, s.lines.map((l) => h("li", { title: l }, trMod(l)))))),
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
    h("div", { class: "hint" }, h("button", { class: "link", onclick: () => { c.mod = ""; redraw(); } }, t("changeMod")),
      LANG !== "en" ? h("span", { title: c.mod }, " · " + c.mod) : null));
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
      }, h("div", {}, m.text), LANG !== "en" ? h("div", { class: "hint" }, m.en) : null)) : [h("div", { class: "suggest-item muted" }, t("modNothing"))]));
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
    api_key: keyInput.value.trim() || null });
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
  await loadGameTexts();
  const s = await loadStatus();
  if (s.loaded) {
    try { state.build = await api("/api/build"); renderHeader(); switchTab("overview"); } catch (_) { /* reopen from the list */ }
  }
  await loadBuildList();
})();
