"use strict";
// ---------- the Atlas passive tree: a page of its own (poe2lab.atlas) ----------
// The tree as the game draws it, read from the installed game, with a beginner's guide around it: how atlas points
// are earned, which nodes to take first and the way to them, when each part of the tree opens. Runs after app.js
// (its helpers are shared).

// the mechanics' trees beside the main one (the game's sub-tree ids)
const AT_PARTS = ["Main", "Breach", "Expedition", "Delirium", "Ritual", "Abyss", "Incursion"];
// how points are earned, step by step (texts: atlasHow*)
const AT_HOW = [["campaign", "flag"], ["fortress", "map"], ["arbiter", "crown"]];
// node sizes in the tree's own units, and the ring colour of each stage (the order the endgame opens them)
const AT_SIZE = { small: 30, notable: 46, keystone: 62, image: 70 };
const AT_STAGE_COLOR = ["#c9b27a", "#5fc98d", "#5b9cf0", "#5b9cf0", "#e8743f", "#b566dc", "#b566dc", "#e9d45c"];
// key groups and useful groups: the interface's own pictures for them
const AT_GROUP_IC = { fracturing: "gem", exceptional: "star", tablets: "layers", lineage: "crown",
  monsters: "skull", rarity: "coins", shrines: "spark", waystones: "map" };
const AT = { data: null, part: "Main", show: "route", focus: null, mark: null, view: null, tab: "atlas", tag: "",
  mods: null, goal: "", ttype: "", safe: false, prop: "MonsterEffectiveness", min: 30 };
// the endgame section's tabs (texts: egTab_*)
const EG_TABS = [["atlas", "map"], ["masters", "person"], ["tablets", "layers"], ["maps", "scroll"]];
// what a tablet's or a waystone's modifier is for (texts: egG_*), and the tablets' types (egType_*)
const EG_GOALS = ["rarity", "quantity", "monsters", "waystones", "experience", "gold", "content", "mechanic"];
const EG_TYPE_IC = { breach: "spark", expedition: "hammer", delirium: "eye", ritual: "skull", abyss: "drop", incursion: "keystone",
  map_boss: "crown", irradiated: "warn" };
// what a master's keystone is for (texts: atMT_*)
const AT_MASTER_TAGS = ["loot", "safety", "pinnacle", "tablets", "strongbox", "explore", "mechanics", "risky"];

async function renderAtlas() {
  state.page = "atlas";
  hideBuildChrome();
  const view = $("#view");
  if (!AT.data) view.replaceChildren(loading(t("atLoading")));
  try {
    AT.data = AT.data || await api("/api/atlas");
  } catch (e) {
    view.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("atNoData")), h("p", { class: "muted" }, e.message),
      h("p", { class: "hint" }, t("atNoDataHint"))));
    return;
  }
  if (state.page !== "atlas") return;  // the player went elsewhere while it loaded
  view.replaceChildren(endgamePage(AT.data));
}

function endgamePage(data) {
  const tabs = h("div", { class: "ws-modes eg-tabs" }, EG_TABS.map(([k, ic]) =>
    h("button", { class: "ws-mode" + (k === AT.tab ? " on" : ""), "aria-pressed": String(k === AT.tab),
      onclick: () => { AT.tab = k; renderAtlas(); } },
      h("span", { class: "ws-mode-ic" }, I(ic)), h("span", {}, h("b", {}, t("egTab_" + k)), h("span", {}, t("egTabS_" + k))))));
  return h("div", { class: "ws at-page" },
    h("div", { class: "ws-hero" }, h("span", { class: "ws-crest" }, I("map")),
      h("div", {}, h("h1", {}, t("egTitle")), h("p", {}, t("egSub")))),
    tabs, ...(AT.tab === "masters" ? mastersBody(data) : AT.tab === "tablets" || AT.tab === "maps" ? modsBody() : atlasPage(data)));
}

// ---------- tablets and waystones (poe2lab.endgame) ----------
// the modifiers load when one of the two tabs opens first
function modsBody() {
  const box = h("div", { class: "stack" });
  if (!AT.mods) {
    box.append(loading(t("egLoading")));
    api("/api/endgame/mods").then((r) => { AT.mods = r; if (state.page === "atlas") renderAtlas(); })
      .catch((e) => box.replaceChildren(h("div", { class: "card" }, h("h3", {}, t("atNoData")), h("p", { class: "muted" }, e.message))));
    return [box];
  }
  return AT.tab === "tablets" ? tabletsBody(AT.mods) : mapsBody(AT.mods);
}
const egText = (m, part = "text") => (m[part]?.[LANG] || m[part]?.en || []);
const goalChips = (goals) => h("div", { class: "row at-chips" }, goals.map((g) => h("span", { class: "chip tag" }, t("egG_" + g))));
function goalFilter() {
  return h("div", { class: "row at-chips" }, ["", ...EG_GOALS].map((g) =>
    h("button", { class: "chip mt-filter" + (g === AT.goal ? " on" : ""), onclick: () => { AT.goal = g; renderAtlas(); } },
      g ? t("egG_" + g) : t("atMTAll"))));
}
const egSec = (title, sub) => h("div", { class: "ws-sec" }, h("div", { class: "ws-sec-l" }, title), sub ? h("div", { class: "hint" }, sub) : null);
function modCard(m) {
  return h("div", { class: "mt-node eg-mod" },
    h("div", { class: "mt-name" }, h("span", { class: "chip warn" }, t("egKind_" + m.kind)),
      m.tiers > 1 ? h("span", { class: "muted small" }, t("egTiers", m.tiers)) : null),
    h("div", { class: "mt-text" }, egText(m).map((l) => h("div", {}, l))), goalChips(m.goals));
}

function tabletsBody(d) {
  const tablets = d.mods.filter((m) => m.item === "tablet");
  const types = [];
  for (const m of tablets.filter((x) => x.base && x.type)) if (!types.some((x) => x.type === m.type)) types.push(m);
  const typeTiles = h("div", { class: "ws-tiles eg-types" }, [null, ...types].map((m) => {
    const type = m ? m.type : "";
    const own = tablets.filter((x) => x.type === type && !x.base && x.kind !== "unique").length;
    return h("button", { class: "ws-tile at-st" + (type === AT.ttype ? " on" : ""), onclick: () => { AT.ttype = type; renderAtlas(); } },
      h("span", { class: "ws-ic" }, I(m ? EG_TYPE_IC[type] || "layers" : "layers")),
      h("div", {}, h("b", {}, m ? t("egType_" + type) : t("egTypeAll")), h("span", {}, m ? egText(m)[0] || "" : t("egTypeAllS")),
        m && own ? h("span", { class: "chip tag" }, t("egOwnMods", own)) : null));
  }));
  const fits = (m) => !AT.goal || m.goals.includes(AT.goal);
  const affix = (m) => !m.base && m.kind !== "unique";  // prefixes, suffixes and the implicits a type rolls
  const general = tablets.filter((m) => !m.type && affix(m) && fits(m));
  const own = AT.ttype ? tablets.filter((m) => m.type === AT.ttype && affix(m) && fits(m)) : [];
  const uniques = tablets.filter((m) => m.kind === "unique" && fits(m));
  const grid = (list) => list.length ? h("div", { class: "eg-grid" }, list.map(modCard)) : h("div", { class: "muted small" }, t("atMNone"));
  return [h("div", { class: "at-warn mt-intro" }, I("info"), h("span", {}, t("egTabletIntro"))),
    egSec(t("egTypesTitle"), t("egTypesSub")), typeTiles,
    egSec(t("egModsTitle"), t("egModsSub")), goalFilter(),
    AT.ttype ? egSec(t("egOnly", t("egType_" + AT.ttype))) : null, AT.ttype ? grid(own) : null,
    egSec(t("egGeneral")), grid(general),
    egSec(t("egUnique"), t("egUniqueSub")), grid(uniques),
    h("p", { class: "hint at-src" }, t("egSourceMods"))];
}

// numbers from n up (n < 1000) as a search pattern: 31 -> 3[1-9]|[4-9]\d|\d{3}
function egAtLeast(n) {
  n = Math.max(0, Math.min(999, Math.floor(n)));
  const s = String(n), parts = [];
  if (s.length === 1) return n === 0 ? "\\d+" : `[${n}-9]|\\d{2,3}`;
  if (s.length === 2) {
    const a = +s[0], b = +s[1];
    parts.push(b === 0 ? `${a}\\d` : b === 9 ? `${a}9` : `${a}[${b}-9]`);
    if (a < 9) parts.push(a === 8 ? "9\\d" : `[${a + 1}-9]\\d`);
    parts.push("\\d{3}");
    return parts.join("|");
  }
  const a = +s[0], b = +s[1], c = +s[2];
  parts.push(c === 9 ? `${a}${b}9` : `${a}${b}[${c}-9]`);
  if (b < 9) parts.push(b === 8 ? `${a}9\\d` : `${a}[${b + 1}-9]\\d`);
  if (a < 9) parts.push(a === 8 ? "9\\d{2}" : `[${a + 1}-9]\\d{2}`);
  return parts.join("|");
}
// a waystone modifier's danger part as a short phrase without numbers, for "!" in the stash search
function egPhrase(m) {
  const line = (egText(m, "risk")[0] || "").toLowerCase();
  const runs = line.split(/[\d%+\-–.,:()]+/).map((x) => x.trim()).filter((x) => x.length >= 8);
  const best = runs.sort((x, y) => y.length - x.length)[0] || "";
  return best.split(/\s+/).slice(0, 3).join(" ");
}

function mapsBody(d) {
  const ways = d.mods.filter((m) => m.item === "waystone");
  const deadly = ways.filter((m) => m.danger === "deadly");
  const props = d.properties || [];
  const out = h("code", { class: "eg-regex" });
  const note = h("div", { class: "hint" });
  const sync = () => {
    const prop = props.find((p) => p.id === AT.prop) || props[0];
    if (!prop) return;
    const tail = (prop.search[LANG] || prop.search.en || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    let q = `"${tail}: \\+?(${egAtLeast(AT.min)})%"`;
    if (AT.safe && deadly.length) q += ` "!${[...new Set(deadly.map(egPhrase).filter(Boolean))].join("|")}"`;
    out.textContent = q;
    note.textContent = t("egSearchNote", q.length);
  };
  const sel = h("select", { onchange: (e) => { AT.prop = e.target.value; sync(); } },
    props.map((p) => h("option", { value: p.id, selected: p.id === AT.prop ? "" : null }, p.name[LANG] || p.name.en)));
  const num = h("input", { type: "number", min: "0", max: "999", value: String(AT.min), class: "eg-min",
    oninput: (e) => { AT.min = +e.target.value || 0; sync(); } });
  const safe = h("label", { class: "eg-safe" }, h("input", { type: "checkbox", checked: AT.safe ? "" : null,
    onchange: (e) => { AT.safe = e.target.checked; sync(); } }), " ", t("egNoDeadly"));
  const copy = h("button", { class: "ghost small", onclick: async () => {
    try { await navigator.clipboard.writeText(out.textContent); toast(t("egCopied"), true); } catch (_) { toast(out.textContent); }
  } }, I("clip"), " ", t("egCopy"));
  sync();
  const fits = (m) => !AT.goal || m.goals.includes(AT.goal);
  const order = { deadly: 0, hard: 1, mild: 2 };
  const list = ways.filter(fits).sort((x, y) => (order[x.danger] ?? 3) - (order[y.danger] ?? 3));
  return [h("div", { class: "at-warn mt-intro" }, I("info"), h("span", {}, t("egMapIntro"))),
    egSec(t("egSearchTitle"), t("egSearchSub")),
    h("section", { class: "card eg-search" },
      h("div", { class: "row eg-search-row" }, h("label", {}, h("span", { class: "muted small" }, t("egProp")), sel),
        h("label", {}, h("span", { class: "muted small" }, t("egMin")), num), safe),
      h("div", { class: "row eg-search-row" }, out, copy), note),
    egSec(t("egMapsList"), t("egMapsListSub")), goalFilter(),
    h("div", { class: "eg-grid" }, list.map((m) => h("div", { class: "mt-node eg-mod eg-" + m.danger },
      h("div", { class: "mt-name" }, h("span", { class: "chip eg-d-" + m.danger, title: t("egDHint") }, t("egD_" + m.danger)),
        h("span", { class: "chip warn" }, t("egKind_" + m.kind)), m.tiers > 1 ? h("span", { class: "muted small" }, t("egTiers", m.tiers)) : null),
      h("div", { class: "mt-text eg-risk" }, egText(m, "risk").map((l) => h("div", {}, l))),
      h("div", { class: "mt-text eg-reward" }, egText(m, "reward").map((l) => h("div", {}, "+ ", l))), goalChips(m.goals)))),
    h("p", { class: "hint at-src" }, t("egSourceMods"))];
}

// The atlas masters: how each is found, and its keystones from the game files with what they are for
function mastersBody(data) {
  const masters = data.tree.masters || [];
  const filter = h("div", { class: "row at-chips" }, ["", ...AT_MASTER_TAGS].map((tag) =>
    h("button", { class: "chip mt-filter" + (tag === AT.tag ? " on" : ""), onclick: () => { AT.tag = tag; renderAtlas(); } },
      tag ? t("atMT_" + tag) : t("atMTAll"))));
  const cols = h("div", { class: "mt-cols" }, masters.map((m) => {
    const key = m.id.toLowerCase();
    const list = m.nodes.filter((n) => !AT.tag || n.tags.includes(AT.tag));
    return h("section", { class: "card mt-card" },
      h("div", { class: "mt-head" }, h("span", { class: "ws-ic" }, I("person")),
        h("div", {}, h("h3", {}, t("atM_" + key)), h("div", { class: "muted small" }, m.title[LANG] || m.title.en))),
      h("div", { class: "mt-how" }, I("key", "ic-s"), " ", t("atMS_" + key)),
      h("div", { class: "mt-list" }, list.length ? list.map((n) => h("div", { class: "mt-node" + (n.start ? " start" : "") },
        h("div", { class: "mt-name" }, n.start ? h("span", { class: "chip ok", title: t("atMStartHint") }, I("star", "ic-s"), t("atMStart")) : null,
          h("b", {}, (n.name[LANG] || n.name.en).trim())),
        h("div", { class: "mt-text" }, (n.text[LANG] || n.text.en).map((l) => h("div", {}, l))),
        h("div", { class: "row at-chips" }, n.tags.map((tag) => h("span", { class: "chip tag mt-" + tag }, t("atMT_" + tag))))))
        : h("div", { class: "muted small" }, t("atMNone"))));
  }));
  return [h("div", { class: "at-warn mt-intro" }, I("info"), h("span", {}, t("atMastersSub"))),
    filter, cols, h("p", { class: "hint at-src" }, t("atMSource"))];
}
$("#atlas-open").addEventListener("click", () => { AT.mark = null; AT.focus = null; renderAtlas(); });

const atName = (n) => (n.name[LANG] || n.name.en || "").trim();
const atText = (n) => n.text[LANG] || n.text.en || [];
function atStage(data, id) {
  const i = data.tree.stages.findIndex((s) => s.id === id);
  return { index: Math.max(0, i), label: t("atStage_" + (id || "start")) !== "atStage_" + (id || "start")
    ? t("atStage_" + (id || "start")) : (data.tree.stages[i]?.text?.[LANG] || data.tree.stages[i]?.text?.en || id) };
}
const atIcon = (n, cls = "gi") => n.img ? h("img", { src: `/icons/${n.img}`, class: cls, alt: "", loading: "lazy" }) : null;

function atlasPage(data) {
  const nodes = new Map(data.tree.nodes.map((n) => [n.id, n]));
  const route = data.route;
  const stepOf = new Map(route.steps.map((s, i) => [s.node, { ...s, n: i + 1 }]));
  const sec = (title, sub) => h("div", { class: "ws-sec" }, h("div", { class: "ws-sec-l" }, title), sub ? h("div", { class: "hint" }, sub) : null);
  const map = atlasMap(data, nodes, stepOf);
  const show = (ids, part = "Main") => { AT.part = part; AT.mark = new Set(ids); AT.focus = ids[0] ?? null; map.redraw(true); map.box.scrollIntoView({ behavior: "smooth", block: "center" }); };

  // 1. how the points come
  const how = h("div", { class: "ws-path at-how" }, AT_HOW.flatMap(([k, ic], i) => [
    i ? h("span", { class: "ws-arrow", "aria-hidden": "true" }, I("chev-r")) : null,
    h("div", { class: "ws-pstep" }, h("div", { class: "ws-phead" }, h("span", { class: "ws-n" }, String(i + 1)), I(ic, "ws-pic"),
      h("b", {}, t(`atHowT_${k}`))), h("span", {}, t(`atHowS_${k}`)), h("ul", {}, t(`atHowM_${k}`).map((x) => h("li", {}, x))))]).filter(Boolean));

  // 2. what to take first: a tile per key group, its nodes as pictures, when it opens and the points on the way
  const firstTiles = h("div", { class: "ws-tiles at-first" }, route.groups.map((g) => {
    const members = g.nodes.map((id) => nodes.get(id));
    const steps = g.nodes.map((id) => stepOf.get(id)).filter(Boolean);
    const last = steps.length ? Math.max(...steps.map((s) => s.points)) : null;
    // when the group opens: the earliest of its nodes when one is enough, else each stage its nodes need
    const stages = [...new Set(members.map((n) => n.req))].map((id) => atStage(data, id)).sort((a, b) => a.index - b.index);
    const shownStages = g.any ? stages.slice(0, 1) : stages;
    return h("div", { class: "ws-tile at-tile" }, h("span", { class: "ws-ic" }, I(AT_GROUP_IC[g.id] || "star")),
      h("div", {}, h("b", {}, t("atG_" + g.id)), h("span", {}, t("atW_" + g.id)),
        h("div", { class: "at-icons" }, members.map((n) => h("button", { class: "at-node-btn", title: atName(n), onclick: () => show([n.id]) },
          atIcon(n) || I("star"), h("span", {}, atName(n))))),
        h("div", { class: "row at-chips" },
          shownStages.map((st) => h("span", { class: "chip at-stage", style: `--st:${AT_STAGE_COLOR[st.index] || "#999"}` }, I("key", "ic-s"), st.label)),
          last !== null ? h("span", { class: "chip tag" }, t(g.any || g.nodes.length === 1 ? "atPtsOne" : "atPtsAll", last)) : null),
        h("button", { class: "ghost small ws-btn", onclick: () => show(g.nodes) }, I("eye"), t("atShowOnTree"))));
  }));
  const total = route.steps.length ? route.steps[route.steps.length - 1].points : 0;

  // 3. the tree itself
  const parts = h("div", { class: "segmented at-parts" }, AT_PARTS.filter((p) => data.tree.nodes.some((n) => n.part === p)).map((p) =>
    h("button", { class: p === AT.part ? "active" : "", onclick: () => { AT.part = p; AT.mark = null; AT.focus = null; map.redraw(true); syncBar(); } },
      t("atPart_" + p))));
  const modes = h("div", { class: "segmented small-seg at-modes" }, ["route", "stages", "plain"].map((m) =>
    h("button", { class: m === AT.show ? "active" : "", title: t(`atShowHint_${m}`), onclick: () => { AT.show = m; map.redraw(false); syncBar(); } },
      t("atShow_" + m))));
  const legend = h("div", { class: "at-legend small" });
  function syncBar() {
    parts.querySelectorAll("button").forEach((b, i) => b.classList.toggle("active", AT_PARTS.filter((p) => data.tree.nodes.some((n) => n.part === p))[i] === AT.part));
    modes.querySelectorAll("button").forEach((b, i) => b.classList.toggle("active", ["route", "stages", "plain"][i] === AT.show));
    legend.replaceChildren(...(AT.show === "stages"
      ? data.tree.stages.filter((s) => data.tree.nodes.some((n) => n.part === AT.part && n.req === s.id)).map((s) => {
        const st = atStage(data, s.id);
        return h("span", { class: "at-key" }, h("i", { style: `border-color:${AT_STAGE_COLOR[st.index] || "#999"}` }), st.label);
      })
      : AT.show === "route" && AT.part === "Main"
        ? [h("span", { class: "at-key" }, h("i", { class: "route" }), t("atLegendRoute", total)),
          h("span", { class: "at-key" }, h("i", { class: "key" }), t("atLegendKey"))]
        : [h("span", { class: "muted" }, t("atLegendPlain"))]));
  }
  syncBar();

  // 4. when the parts open, and what is good to take on the way
  const stageTiles = h("div", { class: "ws-tiles at-stages" }, data.tree.stages.map((s) => {
    const ids = data.tree.nodes.filter((n) => n.part === "Main" && n.req === s.id && n.kind !== "image").map((n) => n.id);
    if (!ids.length) return null;
    const st = atStage(data, s.id);
    return h("button", { class: "ws-tile at-st", style: `--st:${AT_STAGE_COLOR[st.index] || "#999"}`, onclick: () => show(ids) },
      h("span", { class: "ws-ic at-st-ic" }, String(st.index + 1)),
      h("div", {}, h("b", {}, st.label), h("span", {}, t("atStageS_" + (s.id || "start")) !== "atStageS_" + (s.id || "start")
        ? t("atStageS_" + (s.id || "start")) : (s.text[LANG] || s.text.en || "")), h("span", { class: "chip tag" }, t("atNodes", ids.length))));
  }).filter(Boolean));
  const usefulTiles = h("div", { class: "ws-tiles at-useful" }, (route.useful || []).map((g) =>
    h("button", { class: "ws-tile at-st", onclick: () => show(g.nodes) }, h("span", { class: "ws-ic" }, I(AT_GROUP_IC[g.id] || "star")),
      h("div", {}, h("b", {}, t("atU_" + g.id)), h("span", {}, t("atUS_" + g.id)), h("span", { class: "chip tag" }, t("atNodes", g.nodes.length))))));
  return [
    h("div", { class: "at-warn" }, I("warn"), h("span", {}, h("b", {}, t("atWarnT")), " ", t("atWarnS"))),
    sec(t("atHowTitle"), t("atHowSub")), how,
    sec(t("atFirstTitle"), t("atFirstSub", total)), firstTiles,
    sec(t("atTreeTitle"), t("atTreeSub")),
    h("section", { class: "card at-card" }, h("div", { class: "at-bar" }, parts, modes, legend), map.box),
    sec(t("atStagesTitle"), t("atStagesSub")), stageTiles,
    sec(t("atUsefulTitle"), t("atUsefulSub")), usefulTiles,
    h("p", { class: "hint at-src" }, t("atSource"))];
}

// The tree drawn in SVG: links, nodes with the game's icons, a ring coloured by the stage or the route; drag to move,
// wheel or the buttons to zoom, hover (or tap) for the node's text.
function atlasMap(data, nodes, stepOf) {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
  const svg = el("svg", { class: "at-svg" });
  const tip = h("div", { class: "tree-tip at-tip hidden" });
  const zoomBtn = (ic, label, f) => h("button", { class: "icon-btn at-zbtn", title: label, onclick: f }, typeof ic === "string" ? ic : ic);
  const box = h("div", { class: "at-map" }, svg, tip,
    h("div", { class: "at-zoom" }, zoomBtn("+", t("atZoomIn"), () => zoom(0.7)), zoomBtn("−", t("atZoomOut"), () => zoom(1.4)),
      zoomBtn(I("refresh"), t("atZoomReset"), () => { AT.focus = null; fit(); })));
  let vb = null, pinned = null;
  const stageIndex = new Map(data.tree.stages.map((s, i) => [s.id, i]));
  const onRoute = new Set(data.route.steps.flatMap((s) => s.path));
  const keyNodes = new Set(data.route.groups.flatMap((g) => g.nodes));

  function fit() {
    const part = data.tree.nodes.filter((n) => n.part === AT.part);
    const xs = part.map((n) => n.x), ys = part.map((n) => n.y), pad = 160;
    vb = [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + 2 * pad, Math.max(...ys) - Math.min(...ys) + 2 * pad];
    if (AT.focus != null && nodes.get(AT.focus)?.part === AT.part) {
      const n = nodes.get(AT.focus), w = Math.min(vb[2], 3200), hgt = w * (box.clientHeight || 600) / (box.clientWidth || 900);
      vb = [n.x - w / 2, n.y - hgt / 2, w, hgt];
    }
    setView(vb);
  }
  // the view box; the step badges and the key nodes' glow keep a size readable on screen however far it is zoomed out
  function setView(v) {
    vb = v;
    svg.setAttribute("viewBox", vb.join(" "));
    const r = svg.getBoundingClientRect();
    const perPx = r.width ? Math.max(vb[2] / r.width, vb[3] / r.height) : 1;
    const k = Math.max(1, perPx * 15 / 26);  // a badge at least ~15 px in radius
    svg.querySelectorAll(".at-badge").forEach((b) => b.setAttribute("transform", `${b.dataset.at} scale(${k})`));
    svg.querySelectorAll(".at-glow").forEach((c) => c.setAttribute("r", Math.max(+c.dataset.r, perPx * 12)));
  }
  function zoom(k, cx, cy) {
    const [x, y, w, hh] = vb;
    cx = cx ?? x + w / 2; cy = cy ?? y + hh / 2;
    setView([cx - (cx - x) * k, cy - (cy - y) * k, w * k, hh * k]);
  }
  // wheel zoom around the cursor; drag to move (a click without a move picks a node)
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = svg.getBoundingClientRect(), [x, y, w, hh] = vb;
    const scale = Math.max(w / r.width, hh / r.height);
    const ox = x + (w - r.width * scale) / 2, oy = y + (hh - r.height * scale) / 2;
    zoom(e.deltaY > 0 ? 1.15 : 0.87, ox + (e.clientX - r.left) * scale, oy + (e.clientY - r.top) * scale);
  }, { passive: false });
  let drag = null;
  svg.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, vb: [...vb], moved: false }; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const r = svg.getBoundingClientRect(), scale = Math.max(drag.vb[2] / r.width, drag.vb[3] / r.height);
    const dx = (e.clientX - drag.x) * scale, dy = (e.clientY - drag.y) * scale;
    if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) drag.moved = true;
    if (drag.moved) { setView([drag.vb[0] - dx, drag.vb[1] - dy, drag.vb[2], drag.vb[3]]); hideAtTip(); }
  });
  svg.addEventListener("pointerup", (e) => {
    const wasClick = drag && !drag.moved;
    drag = null;
    if (!wasClick) return;
    const g = e.target.closest?.("[data-node]");
    if (g) { pinned = +g.dataset.node; showAtTip(nodes.get(pinned), e); } else { pinned = null; hideAtTip(); }
  });

  function showAtTip(n, e) {
    if (!n || n.kind === "image") return;
    const st = atStage(data, n.req), step = stepOf.get(n.id);
    const group = data.route.groups.find((g) => g.nodes.includes(n.id)) || (data.route.useful || []).find((g) => g.nodes.includes(n.id));
    tip.replaceChildren(
      h("div", { class: "at-tip-head" }, atIcon(n, "tv-tip-ico"), h("div", {}, h("b", {}, atName(n) || "—"),
        h("div", { class: "muted small" }, t("atKind_" + n.kind)))),
      h("div", { class: "at-tip-lines" }, atText(n).map((l) => h("div", {}, l))),
      group ? h("div", { class: "at-tip-why" }, I(AT_GROUP_IC[group.id] || "star", "ic-s"), " ",
        t((data.route.groups.includes(group) ? "atW_" : "atUS_") + group.id)) : "",
      h("div", { class: "at-tip-stage", style: `--st:${AT_STAGE_COLOR[st.index] || "#999"}` }, I("key", "ic-s"), " ",
        n.req ? (data.tree.stages.find((s) => s.id === n.req)?.text?.[LANG] || st.label) : t("atStageS_start")),
      step ? h("div", { class: "at-tip-step" }, t("atTipStep", step.n, step.points)) : "");
    tip.classList.remove("hidden");
    const r = box.getBoundingClientRect();
    const x = Math.min(e.clientX - r.left + 16, r.width - 340), y = Math.min(e.clientY - r.top + 12, r.height - tip.offsetHeight - 8);
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }
  function hideAtTip() { tip.classList.add("hidden"); }

  function draw() {
    svg.replaceChildren();
    const part = data.tree.nodes.filter((n) => n.part === AT.part);
    const inPart = new Set(part.map((n) => n.id));
    const routeMode = AT.show === "route" && AT.part === "Main";
    const links = el("g", { class: "at-links" });
    for (const [a, b] of data.tree.links) {
      if (!inPart.has(a) || !inPart.has(b)) continue;
      const A = nodes.get(a), B = nodes.get(b);
      if (A.kind === "image" || B.kind === "image") continue;
      const lit = routeMode && (onRoute.has(a) || A.root) && (onRoute.has(b) || B.root);
      links.append(el("line", { x1: A.x, y1: A.y, x2: B.x, y2: B.y, class: lit ? "lit" : "" }));
    }
    svg.append(links);
    const layer = el("g", { class: "at-nodes" });
    for (const n of part) {
      const r = AT_SIZE[n.kind] || 30;
      const g = el("g", { "data-node": n.id, class: "at-n " + n.kind, transform: `translate(${n.x} ${n.y})` });
      if (n.kind === "image") {  // a cluster's decoration: the picture only, faint
        if (n.img) g.append(el("image", { href: `/icons/${n.img}`, x: -r, y: -r, width: 2 * r, height: 2 * r, opacity: "0.35" }));
        layer.append(g);
        continue;
      }
      const stage = stageIndex.get(n.req) ?? 0;
      const key = keyNodes.has(n.id), marked = AT.mark?.has(n.id), lit = routeMode && onRoute.has(n.id);
      const ring = AT.show === "stages" ? AT_STAGE_COLOR[stage] || "#999" : key && routeMode ? "#f0c879" : lit ? "#d6a54f" : "#4a4f5a";
      if (marked || (key && routeMode)) g.append(el("circle", { r: r + 18, "data-r": r + 18, class: marked ? "at-glow mark" : "at-glow" }));
      g.append(el("circle", { r: r + 4, class: "at-ring", stroke: ring, "stroke-width": n.kind === "small" ? 6 : 9 }));
      const clip = `at-c${n.id}`;
      const cp = el("clipPath", { id: clip }); cp.append(el("circle", { r }));
      g.append(cp);
      g.append(el("circle", { r, class: "at-bg" }));
      if (n.img) g.append(el("image", { href: `/icons/${n.img}`, x: -r, y: -r, width: 2 * r, height: 2 * r, "clip-path": `url(#${clip})`,
        opacity: routeMode && !lit && !key && !n.root ? "0.55" : "1" }));
      const step = routeMode && stepOf.get(n.id);
      if (step) {
        const at = `translate(${r * 0.75} ${-r * 0.85})`;
        const badge = el("g", { transform: at, "data-at": at, class: "at-badge" });
        badge.append(el("circle", { r: 26 }));
        const tx = el("text", { "text-anchor": "middle", "dominant-baseline": "central" }); tx.textContent = String(step.n);
        badge.append(tx);
        g.append(badge);
      }
      g.addEventListener("pointerenter", (e) => { if (pinned == null && !drag) showAtTip(n, e); });
      g.addEventListener("pointerleave", () => { if (pinned == null) hideAtTip(); });
      layer.append(g);
    }
    svg.append(layer);
  }

  function redraw(refit) { pinned = null; hideAtTip(); draw(); if (refit || !vb) fit(); else setView(vb); }
  // the box gets its size once it is in the page: fit then
  requestAnimationFrame(() => redraw(true));
  return { box, redraw };
}
