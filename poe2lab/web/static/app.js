"use strict";

// ---------- helpers ----------
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style") el.setAttribute("style", v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const fmt = (n, d = 0) => (n === null || n === undefined || Number.isNaN(n)) ? "—"
  : Number(n).toLocaleString("ru-RU", { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v) => (v > 0 ? "+" : "") + fmt(v, 1) + "%";

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json" },
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
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (ok ? " ok" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.add("hidden"), 6000);
}

function loading(text) {
  return h("div", { class: "loading" }, h("div", { class: "spinner" }), text);
}

const DMG = {
  Physical: { ru: "Физ", color: "var(--phys)" },
  Fire: { ru: "Огонь", color: "var(--fire)" },
  Cold: { ru: "Холод", color: "var(--cold)" },
  Lightning: { ru: "Молния", color: "var(--lightning)" },
  Chaos: { ru: "Хаос", color: "var(--chaos)" },
};
const METRIC = [
  ["dps", "DPS"], ["phys_hit", "физ-удар"], ["fire_hit", "огонь"], ["cold_hit", "холод"],
  ["lightning_hit", "молния"], ["chaos_hit", "хаос-удар"], ["recovery", "лечение"],
];

function deltas(changes, keys = METRIC, min = 0.3) {
  const items = keys.filter(([k]) => Math.abs(changes[k] || 0) >= min)
    .map(([k, label]) => h("span", { class: "delta " + (changes[k] > 0 ? "pos" : "neg") }, `${label} ${pct(changes[k])}`));
  return h("div", { class: "deltas" }, items.length ? items : h("span", { class: "muted small" }, "почти без эффекта"));
}

function scoreBar(score, max) {
  const w = Math.max(3, Math.min(100, (score / (max || 1)) * 100));
  return h("div", { class: "score" }, h("div", { class: "bar" }, h("span", { style: `width:${w}%` })), fmt(score, 1));
}

// ---------- state ----------
const state = { build: null, mode: "balanced", tab: "overview", cache: {}, chat: [] };

function resetCache() { state.cache = {}; }

async function cached(key, fn) {
  if (!(key in state.cache)) state.cache[key] = await fn();
  return state.cache[key];
}

// ---------- sidebar ----------
async function loadBuildList() {
  const box = $("#builds");
  try {
    const builds = await api("/api/builds");
    box.replaceChildren();
    if (!builds.length) box.append(h("div", { class: "muted small" }, "билдов нет"));
    for (const b of builds) {
      box.append(h("button", {
        class: "build-item" + (state.build && state.build.name === b.name ? " active" : ""),
        onclick: () => openBuild(b.name),
      },
      h("div", { class: "bi-name" }, b.name),
      h("div", { class: "bi-kind" }, (b.kind === "pob" ? "сохранён в PoB" : "PoB-код") + (b.hasProfile ? " · профиль" : ""))));
    }
  } catch (e) { box.replaceChildren(h("div", { class: "muted small" }, e.message)); }
}

async function loadStatus() {
  const s = await api("/api/status");
  $("#llm-status").textContent = s.llm.configured ? `ИИ: ${s.llm.model}` : "ИИ не настроен";
  return s;
}

// ---------- build ----------
async function openBuild(name, group, skill) {
  $("#view").replaceChildren(loading("Открываю билд в Path of Building…"));
  try {
    state.build = await api("/api/load", { method: "POST", body: { name, group, skill } });
    state.chat = [];
    resetCache();
    renderHeader();
    loadBuildList();
    switchTab(state.tab);
  } catch (e) {
    $("#view").replaceChildren(h("div", { class: "empty" }, h("h2", {}, "Не удалось открыть билд"), h("p", { class: "muted" }, e.message)));
  }
}

function renderHeader() {
  const b = state.build;
  $("#build-header").classList.remove("hidden");
  $("#tabs").classList.remove("hidden");
  $("#bh-name").textContent = b.name;
  $("#bh-sub").textContent = `${b.info.class} / ${b.info.ascendancy} · ${b.info.level} уровень`;
  const sel = $("#main-skill");
  sel.replaceChildren();
  for (const g of b.groups) {
    g.skills.forEach((s, i) => {
      const opt = h("option", { value: `${g.index}:${i + 1}` }, `${g.index}. ${s}`);
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
    if (switchTab.token === token) view.replaceChildren(h("div", { class: "card" }, h("h3", {}, "Ошибка"), h("p", { class: "muted" }, e.message)));
  }
}

const report = () => cached(`report:${state.mode}`, () => api(`/api/report?mode=${state.mode}`));

// ---------- overview ----------
TABS.overview = async (view) => {
  view.replaceChildren(loading("Считаю отчёт (~5 с)…"));
  const r = await report();
  const b = r.baseline;
  const rng = r.damageRange;
  const hits = Object.entries(b.survivableHit);
  const maxHit = Math.max(...hits.map(([, v]) => v.normal));

  const kpi = h("div", { class: "grid kpi" },
    h("div", { class: "card kpi" }, h("div", { class: "label" }, "DPS"),
      h("div", { class: "value" }, fmt(rng.low), rng.high > rng.low ? h("span", { class: "to" }, ` … ${fmt(rng.high)}`) : null),
      h("div", { class: "note" }, rng.high > rng.low ? "без дебаффов на враге … со всеми" : r.build.mainSkill)),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, "Жизнь"), h("div", { class: "value" }, fmt(b.life))),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, "Попадание"), h("div", { class: "value" }, fmt(b.hitChance) + "%")),
    h("div", { class: "card kpi" }, h("div", { class: "label" }, "Лечение"), h("div", { class: "value" }, fmt(b.recoveryPerSecond), h("span", { class: "to" }, " /с")),
      h("div", { class: "note" }, "пока атакуешь")));

  const hitCard = h("div", { class: "card" },
    h("h3", {}, "Какой удар монстра ты переживёшь"),
    h("div", { class: "sub" }, `С полной жизни. Моб ${r.profile.enemy_level} ур.; «сочная» карта: +${r.profile.damage_pct}% урона и +${r.profile.crit_bonus}% к криту монстров.`),
    h("div", { class: "hits" }, hits.map(([type, v]) => {
      const c = DMG[type].color;
      const seg = (cls, val) => h("div", { class: "seg " + cls, style: `width:${(val / maxHit) * 100}%;background:${c}` });
      return h("div", { class: "hit-row" },
        h("div", { class: "hit-name", style: `color:${c}` }, DMG[type].ru),
        h("div", { class: "hit-bar" }, seg("normal", v.normal), seg("crit", v.crit), seg("juiced", v.juiced)),
        h("div", { class: "hit-vals" }, `${fmt(v.normal)} · ${fmt(v.crit)} · ${fmt(v.juiced)}`));
    })),
    h("div", { class: "legend" }, h("span", {}, h("i", { style: "opacity:.35" }), "обычный"),
      h("span", {}, h("i", { style: "opacity:.6" }), "крит"), h("span", {}, h("i", {}), "крит на сочной карте")));

  const order = { must: 0, priority: 1, warn: 2 };
  const label = { must: "сломано", priority: "главное", warn: "учесть" };
  const issues = h("div", { class: "card" }, h("h3", {}, "Что сломано и где дыры"),
    h("div", { class: "sub" }, "«Сломано» — в игре не работает, хотя PoB считает."),
    h("div", { class: "issues" }, [...r.gates].sort((a, c) => order[a.level] - order[c.level]).map((g) =>
      h("div", { class: "issue" }, h("div", {}, h("span", { class: "chip " + g.level }, label[g.level])),
        h("div", {}, h("div", { class: "t" }, g.title), h("div", { class: "d" }, g.detail))))));

  const supports = r.attributes.supportsAtRisk || {};
  for (const [, list] of Object.entries(supports)) {
    issues.append(h("div", { class: "sub", style: "margin-top:12px" }, "Один из этих саппортов в игре выключен — цена, если это он:"),
      h("table", {}, h("tbody", {}, list.map((s) => h("tr", {}, h("td", {}, s.name), h("td", { class: "muted" }, s.skill),
        h("td", { class: "num" }, pct(s.skill_dps_pct)))))));
  }

  const path = h("div", { class: "card" }, h("h3", {}, "Путь апгрейда"),
    h("div", { class: "sub" }, "Каждый шаг пересчитан с учётом предыдущих. Один мод ≈ один средний аффикс."),
    h("div", { class: "steps" }, r.path.map((s) => h("div", { class: "step" }, h("div", {},
      h("div", { class: "what mod" }, s.mod),
      deltas({ dps: s.dps, phys_hit: s.defence.Physical, chaos_hit: s.defence.Chaos, recovery: s.recovery }))))));

  return h("div", { class: "stack" }, kpi, h("div", { class: "grid two" }, hitCard, issues), path);
};

// ---------- damage ----------
TABS.damage = async (view) => {
  view.replaceChildren(loading("Считаю отчёт (~5 с)…"));
  const r = await report();
  const blocks = [];

  const core = r.core;
  if (core.resources.length || core.exchange.length) {
    const res = core.resources.map((x) => h("p", {}, `Свирепость: считаю ${fmt(x.assumed)} из ${fmt(x.maximum)}. Без неё DPS ${fmt(x.dps_without)}, с ней ${fmt(x.dps_with)} (×${fmt(x.dps_with / x.dps_without, 2)}).`,
      x.set_in_build ? null : h("span", { class: "muted" }, " В самом PoB поле Rage пустое — его левая панель показывает DPS без свирепости.")));
    blocks.push(h("div", { class: "card" }, h("h3", {}, "Ядро урона"), res,
      core.unit ? h("div", { class: "sub" }, `Курс: 1 ед. «${core.unit.name}» = ${pct(core.unit.dps_pct_per_point)} DPS`) : null,
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "мод"), h("th", { class: "num" }, "DPS"), h("th", { class: "num" }, "в единицах"))),
        h("tbody", {}, core.exchange.slice(0, 12).map((x) => h("tr", {}, h("td", { class: "mod" }, x.mod), h("td", { class: "num" }, pct(x.dps)), h("td", { class: "num" }, fmt(x.points, 1))))))));
  }

  const rng = r.damageRange;
  const off = r.conditions.filter((c) => !c.checked);
  const on = r.conditions.filter((c) => c.checked);
  const condRow = (c) => h("tr", {}, h("td", {}, c.label), h("td", {}, deltas({ dps: c.dps_pct, phys_hit: c.phys_hit_pct, chaos_hit: c.chaos_hit_pct, recovery: c.recovery_pct }, METRIC, 0.5)));
  blocks.push(h("div", { class: "card" }, h("h3", {}, "Условия боя"),
    rng.conditions.length ? h("p", {}, "Вилка урона: ", h("b", {}, fmt(rng.low)), " без дебаффов на враге … ", h("b", {}, fmt(rng.high)), ` (×${fmt(rng.high / rng.low, 2)}) со всеми сразу.`) : null,
    off.length ? h("div", { class: "sub" }, "Выключены в PoB — если в игре это обычно правда, урон выше:") : null,
    off.length ? h("table", {}, h("tbody", {}, off.map(condRow))) : null,
    on.length ? h("div", { class: "sub", style: "margin-top:12px" }, "Включены — PoB считает выполненными:") : null,
    on.length ? h("table", {}, h("tbody", {}, on.map(condRow))) : null));

  const max = Math.max(...r.ranking.map((x) => x.score), 1);
  blocks.push(h("div", { class: "card" }, h("h3", {}, "Куда вкладываться"),
    h("div", { class: "sub" }, "Ценность одного типичного аффикса для выбранной цели."),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "мод"), h("th", {}, "эффект"), h("th", { class: "num" }, "очки"))),
      h("tbody", {}, r.ranking.map((x) => h("tr", {}, h("td", { class: "mod" }, x.mod),
        h("td", {}, deltas({ dps: x.dps, phys_hit: x.physHit, chaos_hit: x.chaosHit, recovery: x.recovery })),
        h("td", { class: "num" }, scoreBar(x.score, max))))))));

  return h("div", { class: "grid two" }, blocks);
};

// ---------- gear ----------
TABS.gear = async (view) => {
  view.replaceChildren(loading("Разбираю аффиксы, путь крафта и сокеты (~20 с, дальше из кэша)…"));
  const g = await cached(`gear:${state.mode}`, () => api(`/api/gear?mode=${state.mode}`));

  const path = h("div", { class: "card" }, h("h3", {}, "Путь крафта по всем слотам"),
    h("div", { class: "sub" }, "Только предметы без порчи. Целевой набор аффиксов, не процедура крафта."),
    g.craftPath.length ? h("div", { class: "steps" }, g.craftPath.map((s) => h("div", { class: "step" }, h("div", {},
      h("div", { class: "what" }, h("span", { class: "chip tag" }, s.slot), " ",
        s.removed.length ? h("span", {}, h("span", { class: "mod muted" }, s.removed.join(" / ")), " → ") : "докрафтить ",
        h("span", { class: "mod" }, s.added.join(" / "))),
      deltas(s.changes),
      s.sources.length ? h("div", { class: "src" }, "откуда: " + s.sources.join(" · ")) : null)))) : h("p", { class: "muted" }, "Улучшать крафтом нечего."));

  const socketCard = h("div", { class: "card" }, h("h3", {}, "Руны и соул-коры"),
    h("div", { class: "sub" }, "Предметы с порчей пропущены." + (g.prices ? ` Цены: poe.ninja, ${g.prices.league}.` : "")),
    g.sockets.length ? g.sockets.map((s) => h("div", { style: "margin-bottom:12px" },
      h("div", {}, h("span", { class: "chip tag" }, s.slot), ` сокет ${s.index}: сейчас `, h("b", {}, s.current), h("span", { class: "muted" }, ` (даёт ${fmt(s.current_score, 1)})`)),
      s.best.length ? h("table", {}, h("tbody", {}, s.best.map((o) => h("tr", {},
        h("td", {}, h("div", {}, o.name), h("div", { class: "mod muted" }, o.lines.join(" / "))),
        h("td", {}, deltas(o.changes)), h("td", { class: "num" }, o.price || "")))))
        : h("div", { class: "muted small" }, "лучше текущей вставки ничего нет")))
      : h("p", { class: "muted" }, "Сокетов на предметах, которые можно менять, нет."));

  const cards = g.slots.map((p) => {
    const max = Math.max(...p.affixes.map((a) => a.score), 1);
    return h("div", { class: "card" },
      h("div", { class: "slot-head" }, h("div", {}, h("div", { class: "slot" }, p.slot), h("h3", {}, p.item)),
        h("span", { class: "chip " + (p.corrupted ? "must" : "tag") }, p.corrupted ? "с порчей" : "можно крафтить")),
      h("div", { class: "sub" }, `${p.base}, ур. ${p.item_level} · префиксы ${p.prefixes}/${p.limit}, суффиксы ${p.suffixes}/${p.limit}` + (p.uncertain ? " (приблизительно)" : "")),
      p.affixes.map((a) => h("div", { class: "affix" },
        h("div", { class: "kind" }, a.type === "Prefix" ? "преф" : "суфф"),
        h("div", {}, h("span", { class: "mod" }, a.lines.join(" / ")), h("span", { class: "tier" }, `T${a.tier}/${a.tiers}`),
          a.holds.length ? h("div", {}, h("span", { class: "chip hold" }, "держит: " + a.holds.join(", "))) : null,
          a.utility ? h("div", {}, h("span", { class: "chip util" }, "утилити — PoB не оценивает")) : null),
        scoreBar(a.score, max))),
      p.actions.length ? h("div", { class: "actions" }, p.actions.map((x) => h("div", { class: "action" }, x))) : null);
  });

  return h("div", { class: "stack" }, h("div", { class: "grid two" }, path, socketCard),
    h("div", { class: "section-title" }, "Слоты"), h("div", { class: "grid cards" }, cards));
};

// ---------- compare ----------
TABS.compare = async () => {
  const slots = state.build.items.filter((i) => !["Flask", "Charm", "Jewel"].includes(i.type)).map((i) => i.slot);
  const slotSel = h("select", {}, slots.map((s) => h("option", { value: s }, s)));
  const text = h("textarea", { rows: 16, placeholder: "Вставьте предмет из игры (Ctrl+C на предмете) или отредактируйте текущий…" });
  const be = h("input", { type: "text", placeholder: "строка мода кандидата, например: Adds 26 to 42 Physical Damage", style: "width:100%" });
  const out = h("div", {});
  const run = h("button", { class: "primary", onclick: async () => {
    run.disabled = true;
    out.replaceChildren(loading("Считаю…"));
    try {
      const r = await api("/api/compare", { method: "POST", body: { slot: slotSel.value, text: text.value, breakeven: be.value.trim() || null } });
      const ch = { dps: r.dps_pct, phys_hit: r.hit_pct.Physical, fire_hit: r.hit_pct.Fire, cold_hit: r.hit_pct.Cold, lightning_hit: r.hit_pct.Lightning, chaos_hit: r.hit_pct.Chaos, recovery: r.recovery_pct };
      const verdict = r.dps_pct > 0.5 ? "лучше по урону" : r.dps_pct < -0.5 ? "хуже по урону" : "по урону примерно так же";
      out.replaceChildren(h("div", { class: "card" }, h("h3", {}, `Кандидат против надетого: ${verdict}`),
        deltas(ch, METRIC, 0.05), r.life_pct ? h("p", {}, `Жизнь ${pct(r.life_pct)}`) : null,
        Object.entries(r.unmet_requirements).map(([a, [have, need]]) => h("p", { class: "chip must" }, `не хватит ${a}: ${have} из ${need}`)),
        r.breakeven !== undefined ? h("p", {}, r.breakeven ? `Не хуже надетого, пока строка не ниже «${r.breakeven.line}» (${fmt(r.breakeven.factor * 100)}% от указанной).` : "Хуже надетого даже с полной строкой.") : null));
    } catch (e) { out.replaceChildren(h("div", { class: "card" }, h("p", { class: "muted" }, e.message))); }
    run.disabled = false;
  } }, "Сравнить");
  const current = h("button", { class: "ghost", onclick: async () => { text.value = (await api(`/api/item/${encodeURIComponent(slotSel.value)}`)).text; } }, "Вставить надетый для правки");
  return h("div", { class: "grid two" },
    h("div", { class: "card stack" }, h("h3", {}, "Предмет-кандидат"),
      h("label", { class: "field" }, h("span", {}, "Слот"), slotSel), text,
      h("label", { class: "field" }, h("span", {}, "Точка безубыточности (необязательно)"), be),
      h("div", { class: "row" }, run, current)),
    out);
};

// ---------- mechanics ----------
TABS.mechanics = async (view) => {
  view.replaceChildren(loading("Собираю механики из данных игры…"));
  const m = await cached("mechanics", () => api("/api/mechanics"));
  const impact = m.gaps.filter((g) => g.likely_impact);
  const rest = m.gaps.filter((g) => !g.likely_impact);
  const gap = (g) => h("div", { class: "gap" }, h("div", { class: "where" }, g.where), h("div", {}, g.text),
    g.what !== g.text ? h("div", { class: "stat" }, g.what) : null);
  return h("div", { class: "grid two" },
    h("div", { class: "card" }, h("h3", {}, "Что PoB не считает"),
      h("div", { class: "sub" }, "Статы и строки есть в данных игры, но в расчёт PoB не попадают. Важное — учесть поправкой в профиле."),
      impact.map(gap),
      rest.length ? h("details", {}, h("summary", {}, `Прочее (${rest.length})`), rest.map(gap)) : null),
    h("div", { class: "card" }, h("h3", {}, "Скиллы и уникальные предметы"),
      h("div", { class: "sub" }, "Описания из данных игры — то, что получает ИИ-ассистент."),
      m.skills.filter((s) => !s.support).map((s) => h("details", {}, h("summary", {}, `${s.group}. ${s.name}`),
        s.description ? h("p", { class: "muted small" }, s.description) : null, h("ul", {}, s.lines.map((l) => h("li", {}, l))))),
      m.uniques.map((u) => h("details", {}, h("summary", {}, u.name), h("ul", {}, u.lines.map((l) => h("li", {}, l)))))));
};

// ---------- profile ----------
TABS.profile = async () => {
  const raw = JSON.parse(JSON.stringify(state.build.profileRaw));
  raw.corrections = raw.corrections || [];
  raw.notes = raw.notes || [];
  const rageMax = h("input", { type: "checkbox", checked: raw.rage === null || raw.rage === undefined });
  const rageVal = h("input", { type: "number", value: raw.rage ?? 0, min: 0, style: "width:90px" });
  const mana = h("input", { type: "checkbox", checked: !!raw.mana_sustained });
  const corrBox = h("div", {});
  const drawCorr = () => corrBox.replaceChildren(...raw.corrections.map((c, i) => h("div", { class: "corr" },
    h("input", { type: "text", value: c.mod, oninput: (e) => { c.mod = e.target.value; }, title: c.source || "" }),
    h("input", { type: "number", value: c.uptime ?? 1, step: 0.05, min: 0, max: 1, oninput: (e) => { c.uptime = Number(e.target.value); } }),
    h("label", { class: "small" }, h("input", { type: "checkbox", checked: !!c.confirmed, onchange: (e) => { c.confirmed = e.target.checked; } }), " подтверждено"),
    h("button", { class: "x", title: "убрать", onclick: () => { raw.corrections.splice(i, 1); drawCorr(); } }, "×"))));
  drawCorr();
  const notes = h("textarea", { rows: 6 }, raw.notes.join("\n"));
  const save = h("button", { class: "primary", onclick: async () => {
    raw.rage = rageMax.checked ? null : Number(rageVal.value);
    raw.mana_sustained = mana.checked;
    raw.notes = notes.value.split("\n").map((s) => s.trim()).filter(Boolean);
    raw.main_skill = { group: state.build.info.mainSocketGroup, skill: 1, name: state.build.mainSkill };
    save.disabled = true;
    try {
      state.build = await api("/api/profile", { method: "PUT", body: raw });
      resetCache();
      renderHeader();
      loadBuildList();
      toast("Профиль сохранён, билд пересчитан", true);
      switchTab("profile");
    } catch (e) { toast(e.message); }
    save.disabled = false;
  } }, "Сохранить и пересчитать");

  return h("div", { class: "grid two" },
    h("div", { class: "card stack" }, h("h3", {}, "Факты об игре"),
      h("div", { class: "sub" }, "То, что игрок знает, а PoB — нет. Применяется ко всем расчётам."),
      h("div", { class: "row" }, h("label", {}, rageMax, " свирепость всегда в максимуме"), h("span", { class: "muted" }, "иначе:"), rageVal),
      h("label", {}, mana, " мана держится в игре (не проверять дефицит маны)"),
      h("div", { class: "section-title", style: "margin-top:10px" }, "Поправки на механики, которых нет в PoB"),
      h("div", { class: "corr small muted" }, h("span", {}, "строка мода (как в PoB)"), h("span", {}, "аптайм 0…1"), h("span", {}), h("span", {})),
      corrBox,
      h("button", { class: "ghost small", onclick: () => { raw.corrections.push({ mod: "", source: "добавлено вручную", uptime: 1, confirmed: false }); drawCorr(); } }, "+ поправка"),
      h("div", { class: "section-title" }, "Заметки"), notes, h("div", {}, save)),
    h("div", { class: "card" }, h("h3", {}, "Как сейчас считается"),
      state.build.profile.map((l) => h("div", { class: "profile-line" }, l))));
};

// ---------- assistant ----------
TABS.assistant = async () => {
  const status = await loadStatus();
  if (!status.llm.configured) {
    return h("div", { class: "card", style: "max-width:760px" }, h("h3", {}, "ИИ-ассистент не настроен"),
      h("p", {}, "Ассистент работает через API в формате OpenAI, по умолчанию DeepSeek. Ключ хранится только у вас в переменной окружения:"),
      h("p", {}, h("code", {}, "setx DEEPSEEK_API_KEY \"ваш-ключ\""), " — затем перезапустите интерфейс."),
      h("p", { class: "muted small" }, "Другой провайдер: POE2LAB_LLM_BASE_URL, POE2LAB_LLM_MODEL, POE2LAB_LLM_API_KEY. Все цифры ассистент берёт из движка PoB; механики — из вкладки «Механики» и профиля."));
  }
  const log = h("div", { class: "chat-log" });
  const draw = () => {
    log.replaceChildren(...state.chat.map((m) => h("div", { class: "msg " + m.role }, m.text,
      m.tools && m.tools.length ? h("div", { class: "tools" }, "посчитано: " + m.tools.map((t) => t.tool).join(", ")) : null)));
    log.scrollTop = log.scrollHeight;
  };
  if (!state.chat.length) state.chat.push({ role: "bot", text: "Спросите о билде: что улучшить, стоит ли брать предмет, почему умираете. Механику билда я уже знаю из данных игры и вашего профиля." });
  draw();
  const input = h("textarea", { rows: 3, placeholder: "Например: что даст больше урона за дешёво?" });
  const send = h("button", { class: "primary", onclick: async () => {
    const q = input.value.trim();
    if (!q) return;
    state.chat.push({ role: "user", text: q });
    input.value = "";
    draw();
    send.disabled = true;
    log.append(loading("Думаю и считаю…"));
    try {
      const r = await api("/api/chat", { method: "POST", body: { message: q } });
      state.chat.push({ role: "bot", text: r.answer, tools: r.tools });
      if (r.proposals.length) toast("Ассистент предложил поправку профиля — посмотрите вкладку «Профиль»", true);
    } catch (e) { state.chat.push({ role: "bot", text: "Ошибка: " + e.message }); }
    send.disabled = false;
    draw();
  } }, "Спросить");
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send.click(); });
  return h("div", { class: "card chat" }, log, h("div", { class: "chat-input" }, input, send));
};

// ---------- start ----------
(async function start() {
  const s = await loadStatus();
  if (s.loaded) {
    try { state.build = await api("/api/build"); renderHeader(); switchTab("overview"); } catch (_) { /* reopen from the list */ }
  }
  await loadBuildList();
})();
