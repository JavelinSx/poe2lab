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
  mods: null, goal: "", ttype: "", farm: null, strats: null, strat: null, income: null,
  // the stash search builder: header lines with their minimum, all of them or any one, the waystone's least tier,
  // and modifiers the waystone must have (need) or must not have (skip), by mod id
  q: { props: { Pack: 20, RareMonsterQuantityBonus: 20 }, any: false, tier: 0, need: new Set(), skip: new Set() },
  // the tablet search: its type, modifiers it must have (id -> least value, 0 for any) and must not have
  tq: { type: "", any: false, need: new Map(), skip: new Set() } };
// ready-made tablet searches: the type and the modifiers wanted (any one of them is enough)
const EG_TPRESETS = [
  ["ritual", "ritual", ["TowerRitualTributeIncrease", "TowerRitualAdditionalReroll", "TowerRitualOmenChance"], true],
  ["delirium_fog", "delirium", ["TowerDeliriumDifficultyIncrease", "TowerMonsterEffectiveness"], false],
  ["delirium", "delirium", ["TowerDeliriumMonsterSplinterIncrease", "TowerDeliriumFogDissipationDelayNew", "TowerDeliriumRareMonsterPause"], true],
  ["fractures", "", ["TowerMapAdditionalModifier", "TowerMonsterRarityIncrease"], false],
  ["circles", "", ["TowerAdditionalStoneCircle", "TowerMonsterEffectiveness"], false],
  ["strongboxes", "map_boss", ["TowerAdditionalStrongbox", "TowerRareChestCount", "TowerMapBossAdditionalStrongbox",
    "TowerMapBossAdditionalSpirit", "TowerAdditionalAzmeriWisp", "TowerRarePackIncrease"], true],
  ["expedition", "irradiated", ["TowerMonsterEffectiveness", "TowerRarePackIncrease", "TowerDroppedItemRarityIncrease"], true],
  ["breach", "breach", ["TowerBreachMonsterSplinterIncrease", "TowerBreach3AdditionalChance", "TowerBreachAdditionalChance"], true],
  ["wombgifts", "breach", ["TowerBreachWombgiftQuantity", "TowerBreachHivebloodQuantity"], true],
  ["monsters", "", ["TowerRarePackIncrease", "TowerMagicPackIncrease", "TowerPackSizeIncrease"], true],
  ["abyss", "abyss", ["TowerAbyssExtraModifiers", "TowerDroppedItemRarityIncrease"], false],
  ["waystones", "", ["TowerMapDroppedMapsIncrease"], false]];
// ready-made searches: header lines and minimums, and whether to leave out the deadly modifiers
const EG_PRESETS = [
  ["ritual", { Pack: 20, RareMonsterQuantityBonus: 20 }, true],
  ["rarity", { ItemRarity: 50 }, true],
  ["waystones", { WaystoneDropChance: 100 }, false],
  ["effect", { MonsterEffectiveness: 30 }, false],
  ["exp", { ExperienceGained: 20 }, true],
  ["monsters", { MonsterRarity: 100 }, false],
  ["juiced", { MonsterEffectiveness: 80 }, false]];
// a ready-made search put into the search state (the waystone or the tablet one)
function egMapPreset(id) {
  const p = EG_PRESETS.find((x) => x[0] === id);
  if (!p) return;
  const ways = (AT.mods?.mods || []).filter((m) => m.item === "waystone");
  Object.assign(AT.q, { props: { ...p[1] }, any: false, need: new Set(),
    skip: new Set(p[2] ? ways.filter((m) => m.danger === "deadly").map((m) => m.id) : []) });
}
function egTabletPreset(id) {
  const p = EG_TPRESETS.find((x) => x[0] === id);
  if (p) Object.assign(AT.tq, { type: p[1], any: p[3], need: new Map(p[2].map((x) => [x, 0])), skip: new Set() });
}
// the endgame section's tabs (texts: egTab_*)
const EG_TABS = [["atlas", "map"], ["masters", "person"], ["tablets", "layers"], ["maps", "scroll"], ["farm", "coins"]];
const EG_FARM_IC = { breach: "spark", delirium: "eye", ritual: "skull", expedition: "hammer", abyss: "drop", essence: "gem",
  bosses: "crown", currency: "coins", leveling: "run" };
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

// game art for the endgame pages: tablet types, the waystone, the masters' icons (an icon of ours without the files)
const egImg = (file, cls = "eg-art") => file ? h("img", { src: `/icons/${file}`, class: cls, alt: "", loading: "lazy" }) : null;
const egTabletArt = (type) => AT.mods?.art?.tablets?.[type] || "";
const egMasterArt = (id, kind = "icon") => (AT.data?.tree?.masters || []).find((m) => m.id === id)?.art?.[kind] || "";
const EG_TAB_ART = { masters: () => egMasterArt("Jado"), tablets: () => AT.mods?.art?.tablet || egTabletArt("ritual"),
  maps: () => AT.mods?.art?.waystone || "", farm: () => egTabletArt("map_boss") };
function endgamePage(data) {
  const tabs = h("div", { class: "ws-modes eg-tabs" }, EG_TABS.map(([k, ic]) =>
    h("button", { class: "ws-mode" + (k === AT.tab ? " on" : ""), "aria-pressed": String(k === AT.tab),
      onclick: () => { AT.tab = k; renderAtlas(); } },
      h("span", { class: "ws-mode-ic" }, egImg(EG_TAB_ART[k]?.(), "eg-art eg-art-tab") || I(ic)),
      h("span", {}, h("b", {}, t("egTab_" + k)), h("span", {}, t("egTabS_" + k))))));
  return h("div", { class: "ws at-page" },
    h("div", { class: "ws-hero" }, h("span", { class: "ws-crest" }, I("map")),
      h("div", {}, h("h1", {}, t("egTitle")), h("p", {}, t("egSub")))),
    tabs, ...(AT.tab === "masters" ? mastersBody(data) : AT.tab === "tablets" || AT.tab === "maps" || AT.tab === "farm" ? modsBody() : atlasPage(data)));
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
  return AT.tab === "tablets" ? tabletsBody(AT.mods) : AT.tab === "maps" ? mapsBody(AT.mods) : farmBody(AT.data, AT.mods);
}

// ---------- farming options by poe.ninja's prices now (poe2lab.endgame.farm) ----------
const EG_WHAT_IC = { waystone: "scroll", tablets: "layers", atlas: "map", master: "person", other: "info" };
function farmBody(data, mods) {
  if (!AT.strats || AT.strats.lang !== LANG) {
    AT.strats = { lang: LANG, list: null };
    api("/api/endgame/strategies?lang=" + LANG).then((r) => { AT.strats.list = r.strategies; if (state.page === "atlas" && AT.tab === "farm") renderAtlas(); })
      .catch(() => { AT.strats.list = []; });
  }
  if (!AT.income || AT.income.lang !== LANG) {
    const box = AT.income = { lang: LANG, data: null };
    const done = (d) => { box.data = d; if (state.page === "atlas" && AT.tab === "farm") renderAtlas(); };
    api("/api/endgame/income?lang=" + LANG).then(done).catch((e) => done({ error: e.message }));
  }
  if (AT.farm === null) {
    AT.farm = "loading";
    api("/api/endgame/farm").then((r) => { AT.farm = r; if (state.page === "atlas" && AT.tab === "farm") renderAtlas(); })
      .catch((e) => { AT.farm = { error: e.message }; if (state.page === "atlas" && AT.tab === "farm") renderAtlas(); });
  }
  const go = (tab, set) => { AT.tab = tab; Object.assign(AT, set); renderAtlas(); window.scrollTo(0, 0); };
  const list = AT.strats.list;
  const strat = list ? stratSection(list, data, go) : [loading(t("egStratLoading"))];
  const f = AT.farm;
  const prices = f === "loading" ? [loading(t("egFarmLoading"))]
    : f.error ? [h("div", { class: "card" }, h("h3", {}, t("egFarmNoPrices")), h("p", { class: "muted" }, f.error))]
    : priceCards(f, data, mods, go);
  return [egSec(t("egStratTitle"), t("egStratSub")), ...strat,
    egSec(t("egPriceTitle")), ...prices];
}

// a strategy: what it farms and why, where, what to set up (each with a button into the program's own tools), how
function stratSection(list, data, go) {
  const tiles = h("div", { class: "eg-strat-grid" }, list.map((s) =>
    h("button", { class: "ws-tile at-st eg-strat" + (AT.strat === s.id ? " on" : ""),
      onclick: () => { AT.strat = AT.strat === s.id ? null : s.id; renderAtlas(); } },
      h("span", { class: "ws-ic eg-ic-art" }, egImg(s.img) || I(s.icon || "coins")),
      h("div", {}, h("b", {}, s.name), h("span", {}, s.goal),
        h("span", { class: "row eg-strat-tags" }, egIncomeBadge(s.id),
          h("span", { class: "chip tag eg-lv" + s.budget }, I("coins", "ic-s"), " ", s.budgetText),
          h("span", { class: "chip tag eg-lv" + s.build }, I("sword", "ic-s"), " ", s.buildText))))));
  const s = list.find((x) => x.id === AT.strat);
  return s ? [tiles, stratCard(s, data, go)] : [tiles];
}
function stratArt(x) {
  const l = x.link || {};
  if (l.tablets) return egTabletArt(EG_TPRESETS.find((p) => p[0] === l.tablets)?.[1]) || AT.mods?.art?.tablet || "";
  if (x.what === "waystone") return AT.mods?.art?.waystone || "";
  if (l.master) return egMasterArt(l.master);
  return "";
}
function stratLink(link, data, go) {
  if (!link) return null;
  const btn = (ic, text, onclick) => h("button", { class: "chip mt-filter", onclick }, I(ic, "ic-s"), " ", text);
  if (link.maps) return btn("search", t("egStratMaps"), () => { egMapPreset(link.maps); go("maps", {}); });
  if (link.tablets) return btn("search", t("egStratTablets"), () => { egTabletPreset(link.tablets); go("tablets", {}); });
  if (link.part) return btn("map", t("egFBranch", t("atPart_" + link.part)), () => go("atlas", { part: link.part, mark: null, focus: null }));
  if (link.master) return btn("person", t("egStratMaster", t("atM_" + link.master.toLowerCase())), () => go("masters", { tag: "" }));
  if (link.atlas) {
    const nodes = data.tree.nodes.filter((n) => link.atlas.includes(n.name.en));
    if (!nodes.length) return null;
    return btn("eye", t("egFAtlas", nodes.length), () => go("atlas", { part: nodes[0].part, mark: new Set(nodes.map((n) => n.id)), focus: nodes[0].id }));
  }
  return null;
}
function stratCard(s, data, go) {
  const block = (ic, title, ...body) => h("div", { class: "eg-sblock" }, h("div", { class: "eg-sblock-h" }, I(ic, "ic-s"), " ", title), ...body);
  const opt = AT.farm && AT.farm.options ? AT.farm.options.find((o) => o.id === s.option) : null;
  const rate = AT.farm?.exaltedPerDivine || 0;
  const price = (div) => div >= 1 || !rate ? `${fmt(div, div < 10 ? 1 : 0)} div` : `${fmt(div * rate, 0)} ex`;
  const income = incomeBlock(s, block);
  return h("section", { class: "card eg-scard" },
    h("div", { class: "mt-head" }, h("span", { class: "ws-ic eg-ic-art" }, egImg(s.img) || I(s.icon || "coins")),
      h("div", {}, h("h3", {}, s.name), h("div", { class: "muted small" }, s.goal))),
    income,
    h("div", { class: "eg-scols" },
      h("div", { class: "stack" },
        block("help", t("egStratWhy"), h("p", {}, s.why)),
        block("map", t("egStratWhere"), h("p", {}, s.where)),
        s.setup.length ? block("gear", t("egStratSetup"), h("div", { class: "eg-setup" }, s.setup.map((x) =>
          h("div", { class: "eg-setup-row" }, h("span", { class: "eg-setup-ic" }, egImg(stratArt(x)) || I(EG_WHAT_IC[x.what] || "info")),
            h("div", {}, h("div", {}, x.text), stratLink(x.link, data, go)))))) : null),
      h("div", { class: "stack" },
        s.steps.length ? block("flag", t("egStratSteps"), h("ol", { class: "eg-steps" }, s.steps.map((x) => h("li", {}, x)))) : null,
        s.tips.length ? block("warn", t("egStratTips"), h("ul", { class: "eg-tips" }, s.tips.map((x) => h("li", {}, x)))) : null,
        income ? null : block("coins", t("egStratProfit"), h("p", {}, s.profit),
          opt && opt.drops.length ? h("div", { class: "eg-drops" }, h("div", { class: "muted small" }, t("egFDrops")),
            opt.drops.map(egDrop(price))) : null))));
}

// what a strategy brings and costs at poe.ninja's prices now (poe2lab.farmguide.income): the author's loot by item
// priced today, what a map takes, what the strategy hunts for; the author's own words under it
const egMoney = (rate) => (div) => div === null || div === undefined ? "—"
  : Math.abs(div) >= 1 || !rate ? `${fmt(div, Math.abs(div) < 10 ? 1 : 0)} div` : `${fmt(div * rate, 0)} ex`;
function egIncomeBadge(id) {
  const inc = AT.income?.data, ses = inc?.strategies?.[id]?.session;
  if (!ses) return null;
  const money = egMoney(inc.exaltedPerDivine);
  const [v, key] = ses.perHour !== null ? [ses.perHour, "egIBHour"] : ses.perMap !== null ? [ses.perMap, "egIBMap"] : [ses.net, "egIBEvening"];
  return h("span", { class: "chip tag eg-inc-badge" + (v < 0 ? " bad" : "") }, I("coins", "ic-s"), " ", t(key, money(v)));
}
function incomeBlock(s, block) {
  const inc = AT.income?.data, x = inc?.strategies?.[s.id];
  if (!x) return null;
  const money = egMoney(inc.exaltedPerDivine), art = inc.art || {};
  const item = (r) => h("div", { class: "eg-drop" },
    h("span", { class: "eg-drop-n" }, egImg(art[r.name], "eg-art eg-art-drop"), trName(r.name),
      r.qty !== 1 ? h("span", { class: "muted" }, ` ×${fmt(r.qty, 0)}`) : null,
      r.via ? h("span", { class: "muted small" }, " " + t("egIVia", fmt(r.via.qty, 0), trName(r.via.name))) : null),
    h("b", {}, money(r.sum)));
  const other = (o) => h("div", { class: "eg-drop" },
    h("span", { class: "eg-drop-n" }, I("info", "ic-s"), o.text, h("span", { class: "muted small" }, " " + t("egIAuthor"))), h("b", {}, money(o.div)));
  const list = (title, rows, extra = []) => h("div", { class: "eg-drops" }, h("div", { class: "muted small" }, title), rows.map(item), extra.map(other));
  const stat = (value, label, cls = "") => h("div", { class: "eg-inc-stat " + cls }, h("b", {}, value), h("span", {}, label));
  const parts = [];
  const ses = x.session;
  if (ses) {
    parts.push(h("div", { class: "eg-inc-stats" },
      stat(money(ses.net), ses.evening ? t("egIEvening") : t("egIMaps", ses.maps), ses.net >= 0 ? "good" : "bad"),
      ses.perHour !== null ? stat(money(ses.perHour), t("egIHour")) : null,
      ses.perMap !== null && ses.maps > 1 ? stat(money(ses.perMap), t("egIMap")) : null),
    h("div", { class: "eg-inc-cols" },
      list(t("egIDrops", money(ses.income)), ses.drops, ses.other),
      ses.costs.length || ses.costsOther.length ? list(t("egICosts", money(ses.cost)), ses.costs, ses.costsOther) : null),
    ses.costsUnknown ? h("div", { class: "hint" }, t("egIUnknown", ses.costsUnknown)) : null);
  } else {
    for (const r of x.recipes || []) parts.push(list(t("egIRecipe", r.text, r.per, money(r.div)), r.rows));
  }
  const chips = (title, rows) => h("div", { class: "eg-drops" }, h("div", { class: "muted small" }, title),
    h("div", { class: "eg-inc-hunt" }, rows.map((r) => h("span", { class: "eg-inc-chip" },
      egImg(art[r.name], "eg-art eg-art-drop"), h("span", {}, trName(r.name)), h("b", {}, money(r.div))))));
  if (x.hunt) parts.push(chips(t("egIHunt"), x.hunt));
  if (x.inputs) parts.push(chips(t("egIInputs"), x.inputs));
  parts.push(h("div", { class: "hint" }, I("person", "ic-s"), " ", t("egIAuthorSaid"), " ", s.profit));
  return h("div", { class: "eg-income" }, block("coins", t("egIncome", inc.league), ...parts));
}

const egDrop = (price) => (d) => h("div", { class: "eg-drop" },
  h("span", { class: "eg-drop-n" }, egImg(d.img, "eg-art eg-art-drop"), trName(d.name)), h("b", {}, price(d.div)));
// a price card's picture: the tablet of its mechanic, else its first drop's
const egOptArt = (o) => (o.tablet && egTabletArt(o.tablet)) || o.drops.find((d) => d.img)?.img || AT.mods?.art?.waystone || "";
// what each mechanic's loot trades for now on poe.ninja (poe2lab.endgame.farm)
function priceCards(f, data, mods, go) {
  const rate = f.exaltedPerDivine || 0;
  const price = (div) => div >= 1 || !rate ? `${fmt(div, div < 10 ? 1 : 0)} div` : `${fmt(div * rate, 0)} ex`;
  const masters = data.tree.masters || [];
  const mainNodes = data.tree.nodes.filter((n) => n.part === "Main" && n.kind !== "image");
  const cards = f.options.map((o) => {
    const re = new RegExp(o.stats);
    const mNodes = masters.flatMap((m) => m.nodes.filter((n) => (n.stats || []).some((x) => re.test(x))).map((n) => ({ m, n })));
    const aNodes = mainNodes.filter((n) => n.stats.some((x) => re.test(x)));
    const tMods = mods.mods.filter((m) => m.item === "tablet" && !m.base && m.kind !== "unique"
      && (o.tablet ? m.type === o.tablet : !m.type && (m.stats || []).some((x) => re.test(x))));
    const setup = [
      o.tablet ? h("button", { class: "chip mt-filter", onclick: () => go("tablets", { ttype: o.tablet, goal: "" }) },
        egImg(egTabletArt(o.tablet), "eg-art eg-art-chip") || I("layers", "ic-s"), " ", t("egFTablet", t("egType_" + o.tablet))) : null,
      o.part ? h("button", { class: "chip mt-filter", onclick: () => go("atlas", { part: o.part, mark: null, focus: null }) },
        I("map", "ic-s"), " ", t("egFBranch", t("atPart_" + o.part))) : null,
      aNodes.length ? h("button", { class: "chip mt-filter", onclick: () => go("atlas", { part: "Main", mark: new Set(aNodes.map((n) => n.id)), focus: aNodes[0].id }) },
        I("eye", "ic-s"), " ", t("egFAtlas", aNodes.length)) : null,
      mNodes.length ? h("button", { class: "chip mt-filter", onclick: () => go("masters", { tag: "" }) },
        I("person", "ic-s"), " ", t("egFMasters", mNodes.map(({ m, n }) => `${t("atM_" + m.id.toLowerCase())}: ${(n.name[LANG] || n.name.en).trim()}`).slice(0, 3).join(", "))) : null];
    return h("section", { class: "card eg-farm" },
      h("div", { class: "mt-head" }, h("span", { class: "ws-ic eg-ic-art" }, egImg(egOptArt(o)) || I(EG_FARM_IC[o.id] || "coins")),
        h("div", {}, h("h3", {}, t("egF_" + o.id)), h("div", { class: "muted small" }, t("egFS_" + o.id)))),
      o.types.length ? h("div", { class: "eg-score" }, h("div", { class: "bar" }, h("span", { style: `width:${Math.max(3, o.score * 100)}%` })),
        h("span", { class: "small muted" }, t("egFVolume", fmt(o.volume, 0)))) : h("div", { class: "hint" }, t("egFNoPrice")),
      o.drops.length ? h("div", { class: "eg-drops" }, h("div", { class: "muted small" }, t("egFDrops")),
        o.drops.map(egDrop(price))) : null,
      tMods.length ? h("div", { class: "eg-drops" }, h("div", { class: "muted small" }, t("egFMods")),
        tMods.slice(0, 3).map((m) => h("div", { class: "small" }, "• ", egText(m)[0] || ""))) : null,
      h("div", { class: "row at-chips" }, setup.filter(Boolean)));
  });
  return [h("div", { class: "hint" }, t("egFarmIntro", f.league)),
    h("div", { class: "eg-farm-grid" }, cards), h("p", { class: "hint at-src" }, t("egFarmSource"))];
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

// a tablet modifier as a search term: its own phrase, with the number next to it at least `min` when asked
// (a range written high to low, "30–20% less", is a "less is better" number: then only the phrase)
function egModTerm(m, pool, min) {
  const lines = egText(m);
  let phrase = "", line = "";
  for (const l of lines) { const x = egPhrase(m, pool, [], "text", l); if (x && (!phrase || /\d/.test(l) && !/\d/.test(line))) { phrase = x; line = l; } }
  if (!phrase) return "";
  const low = line.toLowerCase(), num = low.match(/(\d+)(?:–(\d+))?/);
  if (!min || !num || (num[2] && +num[1] > +num[2])) return egEsc(phrase);
  const n = `\\b(${egAtLeast(min)})\\b`;
  return num.index < low.indexOf(phrase) ? `${n}\\D*${egEsc(phrase)}` : `${egEsc(phrase)}\\D*${n}`;
}
function egTabletQuery(q, all) {
  const terms = [], tablets = all.filter((m) => m.kind !== "unique");  // a unique tablet is known by its own name
  const base = tablets.find((m) => m.base && m.type === q.type && m.kind !== "unique");
  if (base) terms.push(`"${egEsc(egPhrase(base, tablets.filter((m) => m.base), [], "text"))}"`);
  const need = [...q.need].map(([id, min]) => egModTerm(tablets.find((m) => m.id === id) || {}, tablets, min)).filter(Boolean);
  if (q.any && need.length > 1) terms.push(`"(${need.join("|")})"`);
  else terms.push(...need.map((x) => `"${x}"`));
  const skip = [...q.skip].map((id) => egModTerm(tablets.find((m) => m.id === id) || {}, tablets, 0)).filter(Boolean);
  if (skip.length) terms.push(`"!${[...new Set(skip)].join("|")}"`);
  return terms.join(" ");
}
function tabletSearch(tablets, types) {
  const q = AT.tq;
  const out = h("code", { class: "eg-regex" });
  const note = h("div", { class: "hint" });
  const sync = () => {
    const text = egTabletQuery(q, tablets);
    out.textContent = text || t("egTQEmpty");
    note.className = "hint" + (text.length > 250 ? " eg-long" : "");
    note.textContent = text ? t("egSearchNote", text.length) + (text.length > 250 ? " " + t("egQLong") : "") : "";
  };
  const presets = h("div", { class: "row at-chips" }, EG_TPRESETS.map(([id]) =>
    h("button", { class: "chip mt-filter", onclick: () => { egTabletPreset(id); renderAtlas(); } }, t("egTQP_" + id))));
  const typeChips = h("div", { class: "row at-chips" }, [null, ...types].map((m) => {
    const type = m ? m.type : "";
    return h("button", { class: "chip mt-filter" + (type === q.type ? " on" : ""), onclick: () => {
      q.type = type;  // the other type's own modifiers do not fit it any more
      for (const id of [...q.need.keys(), ...q.skip]) {
        const x = tablets.find((y) => y.id === id);
        if (x && x.type && x.type !== type) { q.need.delete(id); q.skip.delete(id); }
      }
      renderAtlas();
    } }, m ? egImg(egTabletArt(type), "eg-art eg-art-chip") : null, m ? t("egType_" + type) : t("egTQAnyType"));
  }));
  const plain = tablets.filter((m) => m.kind !== "unique");
  const list = tablets.filter((m) => !m.base && m.kind !== "unique" && (!m.type || m.type === q.type))
    .sort((x, y) => (y.type ? 1 : 0) - (x.type ? 1 : 0));
  const modChips = h("div", { class: "eg-q-mods" }, list.map((m) => {
    const st = q.need.has(m.id) ? "need" : q.skip.has(m.id) ? "skip" : "";
    const line = egText(m).find((l) => /\d/.test(l)) || "";
    const num = line.match(/(\d+)(?:–(\d+))?/);
    const ranged = num && !(num[2] && +num[1] > +num[2]);
    const min = st === "need" && ranged ? h("label", { class: "eg-q-minbox", onclick: (e) => e.stopPropagation() }, "≥ ",
      h("input", { type: "number", min: "0", max: "999", class: "eg-min", value: String(q.need.get(m.id) || ""), placeholder: num[1],
        oninput: (e) => { q.need.set(m.id, +e.target.value || 0); sync(); } })) : null;
    const re = new RegExp(egModTerm(m, plain, 0), "i");
    const alike = plain.filter((x) => x !== m && re.test(egText(x).join("\n").toLowerCase()));
    return h("div", { class: `eg-q-mod` + (m.type ? " eg-own" : "") + (st ? " " + st : ""), title: egText(m).join("\n"),
      onclick: () => {  // nothing -> must have -> must not have -> nothing
        if (st === "") q.need.set(m.id, 0); else if (st === "need") { q.need.delete(m.id); q.skip.add(m.id); } else q.skip.delete(m.id);
        renderAtlas();
      } },
    h("span", { class: "eg-q-st" }, st === "need" ? "✓" : st === "skip" ? "✕" : "·"),
    h("span", {}, egText(m).join(" / ")),
    h("span", { class: "muted small" }, m.type ? t("egOnly", t("egType_" + m.type)) : t("egKind_" + m.kind), min ? " " : "", min,
      alike.length ? h("span", { class: "eg-alike", title: alike.map((x) => egText(x).join(" / ")).join("\n") }, " · ", t("egTQAlike", alike.length)) : null));
  }));
  const anyBox = h("label", { class: "eg-safe" }, h("input", { type: "checkbox", checked: q.any ? "" : null,
    onchange: (e) => { q.any = e.target.checked; sync(); } }), " ", t("egTQAny"));
  const clear = h("button", { class: "chip mt-filter", onclick: () => { q.need = new Map(); q.skip = new Set(); renderAtlas(); } }, t("egQClear"));
  const copy = h("button", { class: "ghost small", onclick: async () => {
    try { await navigator.clipboard.writeText(out.textContent); toast(t("egCopied"), true); } catch (_) { toast(out.textContent); }
  } }, I("clip"), " ", t("egCopy"));
  sync();
  return [egSec(t("egTSearchTitle"), t("egTSearchSub")),
    h("section", { class: "card eg-search" },
      h("div", { class: "row eg-search-row eg-q-out" }, out, copy), note,
      h("div", { class: "muted small" }, t("egQPresets")), presets,
      h("div", { class: "eg-q-block eg-q-own" },
        h("div", { class: "eg-q-bh" }, h("span", { class: "eg-q-num" }, "1"), h("div", {}, h("b", {}, t("egTQType")), h("div", { class: "muted small" }, t("egTQTypeS")))),
        typeChips),
      h("div", { class: "eg-q-block eg-q-rolled" },
        h("div", { class: "eg-q-bh" }, h("span", { class: "eg-q-num" }, "2"), h("div", {}, h("b", {}, t("egTQMods")), h("div", { class: "muted small" }, t("egTQModsS")))),
        h("div", { class: "row at-chips" }, anyBox, clear), modChips))];
}

function tabletsBody(d) {
  const tablets = d.mods.filter((m) => m.item === "tablet");
  const types = [];
  for (const m of tablets.filter((x) => x.base && x.type)) if (!types.some((x) => x.type === m.type)) types.push(m);
  const typeTiles = h("div", { class: "ws-tiles eg-types" }, [null, ...types].map((m) => {
    const type = m ? m.type : "";
    const own = tablets.filter((x) => x.type === type && !x.base && x.kind !== "unique").length;
    return h("button", { class: "ws-tile at-st" + (type === AT.ttype ? " on" : ""), onclick: () => { AT.ttype = type; renderAtlas(); } },
      h("span", { class: "ws-ic eg-ic-art" }, egImg(m ? egTabletArt(type) : AT.mods?.art?.tablet) || I(m ? EG_TYPE_IC[type] || "layers" : "layers")),
      h("div", {}, h("b", {}, m ? t("egType_" + type) : t("egTypeAll")), h("span", {}, m ? egText(m)[0] || "" : t("egTypeAllS")),
        m && own ? h("span", { class: "chip tag" }, t("egOwnMods", own)) : null));
  }));
  const fits = (m) => !AT.goal || m.goals.includes(AT.goal);
  const affix = (m) => !m.base && m.kind !== "unique";  // prefixes, suffixes and the implicits a type rolls
  const general = tablets.filter((m) => !m.type && affix(m) && fits(m));
  const own = AT.ttype ? tablets.filter((m) => m.type === AT.ttype && affix(m) && fits(m)) : [];
  const uniques = tablets.filter((m) => m.kind === "unique" && fits(m));
  const grid = (list) => list.length ? h("div", { class: "eg-grid" }, list.map(modCard)) : h("div", { class: "muted small" }, t("atMNone"));
  return [h("div", { class: "at-warn mt-intro eg-intro-art" }, egImg(AT.mods?.art?.tablet, "eg-art eg-art-intro") || I("info"), h("span", {}, t("egTabletIntro"))),
    ...tabletSearch(tablets, types),
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
// a waystone modifier's danger part as a short phrase without numbers for the stash search: the shortest run of its
// words that no other modifier's danger line and no header line has, so it finds this modifier only
function egPhrase(m, ways = [], props = [], part = "risk", line = null) {
  const low = (x) => egText(x, part).join("\n").toLowerCase();
  line = (line ?? egText(m, part)[0] ?? "").toLowerCase();
  const others = [...ways.filter((x) => x !== m && x.id !== m.id).map(low),
    ...ways.flatMap((x) => egText(x, "reward")), ...egText(m, part).filter((l) => l.toLowerCase() !== line),
    ...props.map((p) => p.name[LANG] || p.name.en || "")].map((x) => x.toLowerCase());
  const runs = line.split(/[\d%+\-–.,:()]+/).map((x) => x.trim()).filter(Boolean);
  const pick = (min) => {
    let best = "";
    for (const run of runs) {
      const words = run.split(/\s+/);
      for (let n = 1; n <= Math.min(8, words.length); n++)
        for (let i = 0; i + n <= words.length; i++) {
          const c = words.slice(i, i + n).join(" ");
          if (c.length >= min && line.includes(c) && !others.some((o) => o.includes(c)) && (!best || c.length < best.length)) best = c;
        }
    }
    return best;
  };
  const best = pick(10) || pick(8);
  // no piece is its own (its whole line is inside another one): the longest run, the closest it gets
  return best || runs.sort((x, y) => y.length - x.length)[0] || "";
}

const egEsc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// the stash search line: every header line at its minimum ("all"), or any one of them; the tier; modifiers wanted
// each as its own term, the unwanted ones in one "!a|b" term (quoted terms must all match in the game's search)
function egQuery(q, props, ways, lang) {
  const terms = [];
  const lines = props.filter((p) => q.props[p.id] !== undefined)
    .map((p) => `${egEsc(p.search[lang] || p.search.en || "")}: \\+?(${egAtLeast(q.props[p.id])})%`);
  if (lines.length) {
    if (q.any && lines.length > 1) terms.push(`"(${lines.join("|")})"`);
    else terms.push(...lines.map((l) => `"${l}"`));
  }
  if (q.tier > 1) terms.push(`"${lang === "ru" ? "\\(ур\\. " : "\\(tier "}(${egAtLeast(q.tier)})\\)"`);
  const phrase = (id) => egPhrase(ways.find((m) => m.id === id) || {}, ways, props);
  for (const id of q.need) { const x = phrase(id); if (x) terms.push(`"${egEsc(x)}"`); }
  const skip = [...new Set([...q.skip].map(phrase).filter(Boolean))];
  if (skip.length) terms.push(`"!${skip.map(egEsc).join("|")}"`);
  return terms.join(" ");
}

function mapsBody(d) {
  const ways = d.mods.filter((m) => m.item === "waystone");
  const props = d.properties || [];
  const q = AT.q;
  const out = h("code", { class: "eg-regex" });
  const note = h("div", { class: "hint" });
  const sync = () => {
    const text = egQuery(q, props, ways, LANG);
    out.textContent = text || t("egQEmpty");
    note.className = "hint" + (text.length > 250 ? " eg-long" : "");
    note.textContent = text ? t("egSearchNote", text.length) + (text.length > 250 ? " " + t("egQLong") : "") : "";
  };
  const redraw = () => { renderAtlas(); };
  const presets = h("div", { class: "row at-chips" }, EG_PRESETS.map(([id]) =>
    h("button", { class: "chip mt-filter", onclick: () => { egMapPreset(id); redraw(); } }, t("egQP_" + id))));
  const rows = h("div", { class: "eg-q-props" }, props.map((p) => {
    const on = q.props[p.id] !== undefined;
    const num = h("input", { type: "number", min: "0", max: "999", class: "eg-min", value: String(on ? q.props[p.id] : 20),
      disabled: on ? null : "", oninput: (e) => { q.props[p.id] = +e.target.value || 0; sync(); } });
    return h("label", { class: "eg-q-prop" + (on ? " on" : "") },
      h("input", { type: "checkbox", checked: on ? "" : null, onchange: (e) => {
        if (e.target.checked) q.props[p.id] = +num.value || 0; else delete q.props[p.id];
        redraw();
      } }),
      h("span", {}, p.name[LANG] || p.name.en), h("span", { class: "muted small" }, "≥"), num, h("span", { class: "muted small" }, "%"));
  }));
  const anyBox = h("label", { class: "eg-safe" }, h("input", { type: "checkbox", checked: q.any ? "" : null,
    onchange: (e) => { q.any = e.target.checked; sync(); } }), " ", t("egQAny"));
  const tier = h("label", { class: "eg-safe" }, t("egQTier"), " ",
    h("input", { type: "number", min: "0", max: "16", class: "eg-min", value: String(q.tier || ""), placeholder: "—",
      oninput: (e) => { q.tier = +e.target.value || 0; sync(); } }));
  const order = { deadly: 0, hard: 1, mild: 2 };
  const modChips = h("div", { class: "eg-q-mods" }, [...ways].sort((x, y) => (order[x.danger] ?? 3) - (order[y.danger] ?? 3)).map((m) => {
    const st = q.need.has(m.id) ? "need" : q.skip.has(m.id) ? "skip" : "";
    return h("button", { class: `eg-q-mod eg-d-${m.danger}` + (st ? " " + st : ""), title: [...egText(m, "risk"), ...egText(m, "reward").map((l) => "+ " + l)].join("\n"),
      onclick: () => {  // nothing -> must have -> must not have -> nothing
        if (st === "") q.need.add(m.id); else if (st === "need") { q.need.delete(m.id); q.skip.add(m.id); } else q.skip.delete(m.id);
        redraw();
      } },
    h("span", { class: "eg-q-st" }, st === "need" ? "✓" : st === "skip" ? "✕" : "·"),
    h("span", {}, egText(m, "risk")[0] || ""),
    h("span", { class: "muted small" }, egText(m, "reward").map((l) => "+ " + l).join(", ")));
  }));
  const allDeadly = h("button", { class: "chip mt-filter", onclick: () => {
    ways.filter((m) => m.danger === "deadly").forEach((m) => { q.need.delete(m.id); q.skip.add(m.id); }); redraw();
  } }, t("egNoDeadly"));
  const clear = h("button", { class: "chip mt-filter", onclick: () => { q.need = new Set(); q.skip = new Set(); redraw(); } }, t("egQClear"));
  const copy = h("button", { class: "ghost small", onclick: async () => {
    try { await navigator.clipboard.writeText(out.textContent); toast(t("egCopied"), true); } catch (_) { toast(out.textContent); }
  } }, I("clip"), " ", t("egCopy"));
  sync();
  const fits = (m) => !AT.goal || m.goals.includes(AT.goal);
  const list = ways.filter(fits).sort((x, y) => (order[x.danger] ?? 3) - (order[y.danger] ?? 3));
  return [h("div", { class: "at-warn mt-intro eg-intro-art" }, egImg(d.art?.waystone, "eg-art eg-art-intro") || I("info"), h("span", {}, t("egMapIntro"))),
    h("button", { class: "eg-craft-btn", onclick: () => { AT.tab = "farm"; AT.strat = "craft_waystones"; renderAtlas();
      setTimeout(() => document.querySelector(".eg-scard")?.scrollIntoView({ block: "start", behavior: "smooth" }), 400); } },
      egImg(d.art?.waystone, "eg-art eg-art-craft") || I("scroll"),
      h("span", {}, h("b", {}, t("egQCraft")), h("span", {}, t("egQCraftS"))), I("arrow-r")),
    egSec(t("egSearchTitle"), t("egSearchSub")),
    h("section", { class: "card eg-search" },
      h("div", { class: "row eg-search-row eg-q-out" }, out, copy), note,
      h("div", { class: "muted small" }, t("egQPresets")), presets,
      h("div", { class: "hint eg-omens" }, I("info", "ic-s"), " ", t("egQOmens")),
      // the waystone's own header lines (the totals) and its rolled modifiers are two different things: kept apart
      h("div", { class: "eg-q-block eg-q-own" },
        h("div", { class: "eg-q-bh" }, h("span", { class: "eg-q-num" }, "1"), h("div", {}, h("b", {}, t("egQOwn")), h("div", { class: "muted small" }, t("egQLines")))),
        rows, h("div", { class: "row eg-search-row" }, anyBox, tier)),
      h("div", { class: "eg-q-block eg-q-rolled" },
        h("div", { class: "eg-q-bh" }, h("span", { class: "eg-q-num" }, "2"), h("div", {}, h("b", {}, t("egQRolled")), h("div", { class: "muted small" }, t("egQMods")))),
        h("div", { class: "row at-chips" }, allDeadly, clear), modChips)),
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
    return h("section", { class: "card mt-card" + (m.art?.portrait ? " mt-has-art" : "") },
      m.art?.portrait ? h("div", { class: "mt-portrait", style: `background-image:url(/icons/${m.art.portrait})` }) : null,
      h("div", { class: "mt-head" }, h("span", { class: "ws-ic eg-ic-art" }, egImg(m.art?.icon) || I("person")),
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
