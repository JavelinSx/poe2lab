// ---------- the build author's constructor: a page of its own (poe2lab.constructor) ----------
// The character from PoB laid out by section - skills with their gems, gear slot by slot, the tree's keystones and
// notables, jewels, flasks and charms, reward choices, the levelling plan. Any element pressed opens its notes: a tip
// shown over it, and a note shown at once under the author's own label. Nothing is calculated here: the program's
// advice is on "check with the program", the analysis tab of the section. Runs after app.js (its helpers are shared).
// the guide's stage the page shows: the build itself (Макс) or its Мин (the same build at its start or on a budget)
const CT = { section: "character", stage: "max", data: null, all: { max: null, min: null }, hints: {}, hintsOpen: null,
  taken: new Set() };
const CT_SECTIONS = ["character", "skills", "gear", "tree", "jewels", "flasks", "quests", "leveling"];
// the analysis tab that checks a section
const CT_CHECK = { character: "overview", skills: "skills", gear: "gear", flasks: "gear", tree: "tree", jewels: "tree",
  quests: "profile", leveling: "overview" };
// what the drawer's search offers first in a section's notes
const CT_KINDS = { skills: ["gem", "support"], gear: ["unique", "base", "rune"], flasks: ["unique", "base"],
  tree: ["passive"], jewels: ["unique", "passive"] };

async function openConstructor(section) {
  if (!state.build) return;
  if (section) CT.section = section;
  hideTip();
  state.page = "ctor";
  switchTab.token = Symbol();  // a tab still being worked out is not drawn over the page
  hideBuildChrome();
  await authorLoad();
  authorToggle(true, false);  // the drawer: game things to put into a note
  const view = $("#view");
  view.replaceChildren(loading(t("ctLoading")));
  if (CT.build !== state.build.name) { CT.build = state.build.name; CT.hints = {}; CT.hintsOpen = null; CT.taken = new Set(); }
  try {
    CT.data = await ctLayout(CT.stage);
  } catch (e) {
    if (CT.stage === "max") { view.replaceChildren(errorCard(e)); return; }
    CT.stage = "max";  // the Мин was taken off meanwhile
    try { CT.data = await ctLayout("max"); } catch (e2) { view.replaceChildren(errorCard(e2)); return; }
  }
  CT.all = { max: null, min: null, [CT.stage]: CT.data };
  ctDraw();
  ctOtherStage();
}
// the other stage laid out in the background (the notes without their element are looked for in both)
async function ctOtherStage() {
  const other = CT.stage === "max" ? "min" : "max";
  if (CT.all[other] || (other === "min" && !(CT.data.stages || {}).min)) return;
  try { CT.all[other] = await ctLayout(other); ctDraw(); } catch (_) { /* the stage is gone: nothing to compare with */ }
}
const ctLayout = (stage) => cached(`ctor-layout:${stage}`, () => api(`/api/constructor/layout?stage=${stage}&${buildQuery()}`));

// ---- the build's two stages: Макс (the build) and Мин, loaded from PoB ----
async function ctStage(stage) {
  CT.stage = stage;
  hideTip();
  $("#view").replaceChildren(loading(t("ctLoading")));
  try { CT.data = await ctLayout(stage); } catch (e) { toast(e.message); CT.stage = "max"; CT.data = await ctLayout("max"); }
  CT.all[CT.stage] = CT.data;
  ctDraw();
  ctOtherStage();
}
function ctCodeDialog(stage) {
  const code = h("textarea", { rows: 6, placeholder: t("ctMinPh"), spellcheck: "false" });
  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) back.remove(); } });
  const go = h("button", { class: "primary", onclick: async () => {
    go.disabled = true;
    try {
      const r = await api(`/api/constructor/${stage}?${buildQuery()}`, { method: "POST", body: { code: code.value } });
      back.remove();
      if (stage === "max") {  // the build itself changed: every tab's numbers too
        state.build = r;
        resetCache();
        loadBuildList();
        toast(t("ctMaxLoaded"), true);
      } else {
        delete state.cache["ctor-layout:min"];
        delete state.cache["ctor-layout:max"];  // its answer says whether a Мин is there
        toast(t("ctMinLoaded", `${trName(r.class)} / ${r.ascendancy ? trName(r.ascendancy) : t("noAscendancy")} · ${t("level", r.level)}`), true);
      }
      CT.hints = {};
      CT.stage = stage;
      openConstructor();
    } catch (e) { toast(e.message); go.disabled = false; }
  } }, t("ctMinLoad"));
  back.append(h("div", { class: "ask card stack ct-editor", role: "dialog", "aria-modal": "true" },
    h("div", { class: "ct-title" }, t(stage === "max" ? "ctMaxTitle" : "ctMinTitle")), h("div", { class: "hint" }, t(stage === "max" ? "ctMaxSub" : "ctMinSub")), code,
    h("div", { class: "row" }, go, h("button", { class: "ghost", onclick: () => back.remove() }, t("cancel")))));
  document.body.append(back);
  code.focus();
}
async function ctMinRemove() {
  if (!(await confirmInPage(t("ctMinAsk"), t("ctMinRemove")))) return;
  try {
    await api(`/api/constructor/min?${buildQuery()}`, { method: "DELETE" });
    delete state.cache["ctor-layout:min"];
    delete state.cache["ctor-layout:max"];
    toast(t("ctMinRemoved"), true);
    ctStage("max");
  } catch (e) { toast(e.message); }
}
function ctStageBar() {
  const has = CT.data.stages && CT.data.stages.min;
  const btn = (stage) => h("button", { class: CT.stage === stage ? "is-on" : "", onclick: () => { if (CT.stage !== stage) ctStage(stage); } },
    t("ctStage_" + stage));
  return h("div", { class: "row ct-stages" }, h("span", { class: "muted small" }, t("ctStage")),
    h("div", { class: "ct-tabs" }, btn("max"), has ? btn("min") : null),
    h("button", { class: "ghost small", title: t("ctMaxHint"), onclick: () => ctCodeDialog("max") }, t("ctMaxUpdate")),
    h("button", { class: "ghost small", onclick: () => ctCodeDialog("min") }, t(has ? "ctMinReplace" : "ctMinAdd")),
    has ? h("button", { class: "ghost small", onclick: ctMinRemove }, t("ctMinRemove")) : null,
    CT.stage === "min" ? h("span", { class: "hint" }, t("ctMinHint")) : null);
}

// back to the build's tabs (the one that checks the section, or the one left)
function ctLeave(tab) {
  hideTip();
  authorToggle(false, false);
  renderHeader();
  switchTab(tab || state.tab);
}

// ---- an element: pressed, its notes open; over it, the author's tip and the game's card ----
function ctEl(id, body, opts = {}) {
  const b = auBlock(id);
  const el = h("button", { class: "ct-el " + (opts.cls || "") + (b.tip ? " has-tip" : "") + (b.text ? " has-note" : ""),
    onclick: (e) => { e.stopPropagation(); ctEdit(id, opts.title || "", opts.card); } },
  body, b.tip || b.text ? h("span", { class: "ct-mark", title: t("ctMarked") }, b.text ? "📌" : "💬") : null);
  return hoverTip(el, () => h("div", { class: "stack" }, b.tip ? h("div", { class: "ct-tip" }, ...auRich(b.tip)) : null,
    opts.card ? opts.card() : null, h("div", { class: "muted small" }, t("ctClickHint"))));
}

// the note shown at once: the author's label, the text
function ctNote(id, title) {
  const b = auBlock(id);
  if (!b.text) return null;
  return h("div", { class: "ct-note" }, h("div", { class: "ct-note-head" }, b.label ? h("b", {}, b.label) : null,
    title ? h("span", { class: "muted small" }, title) : null), h("div", { class: "au-text" }, ...auRich(b.text)));
}

// an element's notes: the tip and the note with its label, each kept as it is typed
function ctEdit(id, title, card) {
  hideTip();
  const b = auBlock(id);
  const back = h("div", { class: "ask-back", onclick: (e) => { if (e.target === back) close(); } });
  const onKey = (e) => { if (e.key === "Escape" && !document.querySelector(".au-pop")) { e.preventDefault(); close(); } };
  const close = () => { back.remove(); document.removeEventListener("keydown", onKey, true); AU.target = null; ctDraw(); };
  const label = h("input", { type: "text", value: b.label || "", maxlength: 60, placeholder: t("ctLabelPh"), class: "ct-label",
    oninput: (e) => auSave(id, { label: e.target.value }) });
  back.append(h("div", { class: "ask card stack ct-editor", role: "dialog", "aria-modal": "true" },
    h("div", { class: "ct-title" }, I("pencil", "c-gold"), " ", title),
    card ? h("div", { class: "ct-ed-card" }, card()) : null,
    h("div", { class: "section-title" }, t("ctTip")), h("div", { class: "hint" }, t("ctTipHint")),
    auEditor(b.tip || "", (v) => auSave(id, { tip: v }), t("ctTipPh")),
    h("div", { class: "section-title" }, t("ctNote")), h("div", { class: "hint" }, t("ctNoteHint")),
    label, auEditor(b.text || "", (v) => auSave(id, { text: v }), t("ctNotePh")),
    h("div", { class: "row" }, h("button", { class: "primary", onclick: close }, t("ctDone")),
      h("button", { class: "ghost", onclick: () => { auSave(id, { tip: "", text: "", label: "" }); close(); } }, t("ctClear")))));
  document.body.append(back);
  document.addEventListener("keydown", onKey, true);
}

// ---- the sections ----
function ctItem(row) {
  const it = row.item;
  const lines = () => [...(it.implicit || []), ...(it.explicit || []), ...(it.runes || [])].map((m) => h("li", { title: m.line }, trMod(m.line)));
  const card = () => linesTip(itemIcon(it.name, it.baseName, it.rarity), itemTitle(it), lines());
  return h("div", { class: "card ct-slot r-" + (it.rarity || "normal").toLowerCase() },
    ctEl(row.id, [h("span", { class: "muted small" }, slotName(row.slot)), itemIcon(it.name, it.baseName, it.rarity),
      h("span", { class: "ct-item-name" }, itemTitle(it))], { cls: "ct-item", title: `${slotName(row.slot)} · ${itemTitle(it)}`, card }),
    (it.runes || []).length ? h("div", { class: "muted small" }, it.runes.map((m) => trMod(m.line)).join(" · ")) : null,
    ctNote(row.id));
}

const CT_DRAW = {
  character: (d) => {
    const c = d.character;
    return h("div", { class: "card stack" },
      h("div", { class: "row ct-who" }, h("b", {}, `${trName(c.class)} / ${c.ascendancy ? trName(c.ascendancy) : t("noAscendancy")} · ${t("level", c.level)}`),
        c.mainSkill ? h("span", { class: "muted" }, t("ctMainSkill"), " ", gemName(c.mainSkill)) : null),
      h("div", { class: "section-title" }, t("ctAbout")), h("div", { class: "hint" }, t("ctAboutHint")),
      auEditor(auBlock("ov:about").text || "", (v) => auSave("ov:about", { text: v }), t("auAboutPh")));
  },
  skills: (d) => d.skills.map((g) => {
    const name = g.actives.map((x) => trName(x)).join(" + ");
    const gems = g.gems.map((x) => h("span", { class: "ct-gem" + (x.support ? " sup" : "") + (x.enabled ? "" : " off") },
      ctEl(x.id, [icon(x.name), h("span", {}, trName(x.name))], { title: trName(x.name), card: () => gemTipCard(x.name, null, false) }),
      h("span", { class: "muted small" }, t("ctGemLv", x.level, x.quality))));
    return h("div", { class: "card stack ct-group" + (g.enabled ? "" : " off") },
      ctEl(g.id, [h("span", { class: "ct-title" }, name), g.main ? h("span", { class: "chip ok" }, t("ctMain")) : null], { cls: "ct-head", title: name }),
      ctNote(g.id), h("div", { class: "ct-gems" }, gems), ...g.gems.map((x) => ctNote(x.id, trName(x.name))));
  }),
  gear: (d) => h("div", { class: "ct-grid" }, d.gear.map(ctItem)),
  flasks: (d) => (d.flasks.length ? h("div", { class: "ct-grid" }, d.flasks.map(ctItem)) : h("p", { class: "muted" }, t("ctNone"))),
  tree: (d) => {
    const node = (n) => ctEl(n.id, [icon(n.name, "ico passive"), h("span", {}, trName(n.name))],
      { cls: "ct-chip", title: trName(n.name), card: () => auTip("passive", `${n.node}|${n.name}`) });
    const part = (key, list) => (list.length ? h("div", { class: "card stack" }, h("div", { class: "section-title" }, t("ctTree_" + key)),
      h("div", { class: "ct-chips" }, list.map(node)), ...list.map((n) => ctNote(n.id, trName(n.name)))) : null);
    return [part("ascendancy", d.tree.ascendancy), part("keystones", d.tree.keystones), part("notables", d.tree.notables),
      h("div", { class: "muted small" }, t("ctSmall", d.tree.small))];
  },
  jewels: (d) => (d.jewels.length ? h("div", { class: "ct-grid" }, d.jewels.map((j) => {
    const it = j.item, gist = jewelGist({ item: it, effect: j.effect });
    const card = () => h("div", { class: "stack" }, h("b", { class: "r-" + (it.rarity || "normal").toLowerCase() }, itemTitle(it)),
      h("ul", { class: "item-lines small" }, it.lines.map((l) => h("li", {}, trMod(l)))), jewelEffect(j.effect));
    return h("div", { class: "card ct-slot r-" + (it.rarity || "normal").toLowerCase() },
      ctEl(j.id, [itemIcon(it.name, it.baseName, it.rarity), h("span", { class: "ct-item-name" }, itemTitle(it)),
        gist ? h("span", { class: "jw-gist small" }, gist) : null, h("span", { class: "muted small" }, t("jwNear", trName(j.near)))],
      { cls: "ct-item", title: itemTitle(it), card }), ctNote(j.id));
  })) : h("p", { class: "muted" }, t("ctNone"))),
  quests: (d) => h("div", { class: "ct-grid" }, d.quests.map((q) => {
    const chosen = q.options.length && q.value && q.value !== "None" ? q.value : null;
    const what = q.options.length ? (chosen ? chosen.split("\n").map((l) => trMod(l.trim())).join(" · ") : t("qNotChosen")) : trMod(q.stat || "");
    const taken = q.options.length ? !!chosen : !!q.value;
    return h("div", { class: "card ct-slot" + (taken ? "" : " off") },
      ctEl(q.id, [h("span", { class: "ct-item-name" }, what),
        h("span", { class: "muted small" }, `${questName(q)} · ${lrStageName(QUEST_ACT[q.act] || "maps")} · ${questArea(q.area)}`)],
      { cls: "ct-item", title: questName(q) }), ctNote(q.id));
  })),
  // the levelling plan with the author's own lists and notes of each stage (the blocks the overview shows)
  leveling: () => [h("div", { class: "hint" }, t("ctLevelingHint")), levelingCard()],
};

// ---- the program's advice, on a button: each hint taken into an element's note becomes the author's own words ----
// Worked out by PoB on the build as it is open (the Макс; with the player's character in it, the character), from
// the analysis tabs' own answers.
// damage, effective life and recovery: what a note needs (the hit by hit numbers stay in the analysis tabs)
const ctDelta = (changes) => UM_METRIC.filter(([k]) => Math.abs(changes[k] || 0) >= 0.3).map(([k, l]) => `${t(l)} ${pct(changes[k])}`).join(", ");
async function ctHints(section, d) {
  const out = [];
  const add = (target, where, text) => { if (text) out.push({ target, where, text }); };
  if (section === "character") {
    const r = await report();
    for (const g of r.gates || []) add("sec:character", t("ctSec_character"), `${LANG === "en" ? g.title_en || g.title : g.title}: ${LANG === "en" ? g.detail_en || g.detail : g.detail}`);
    for (const m of (r.ranking || []).slice(0, 3)) add("sec:character", t("ctSec_character"), t("ctHintMod", trMod(m.mod)));
  } else if (section === "skills") {
    for (const x of (await DATA.skills("supports")).skills) {
      const g = d.skills.find((y) => y.index === x.group);
      if (g && x.better.length) add(g.id, g.actives.map((a) => trName(a)).join(" + "), t("ctHintSupport", trName(x.weakest), x.better.slice(0, 2).map((b) => trName(b.name)).join(", ")));
    }
  } else if (section === "gear" || section === "flasks") {
    for (const sl of (await DATA.gear()).slots) {
      const row = d[section].find((r) => r.slot === sl.slot);
      if (!row) continue;
      const top = [...sl.affixes].sort((a, b) => b.score - a.score)[0];
      if (top && top.score > 0) add(row.id, slotName(sl.slot), t("ctHintHolds", trMod(top.lines[0])));
      for (const a of sl.actions || []) add(row.id, slotName(sl.slot), a);
    }
  } else if (section === "tree") {
    const tr = await DATA.tree();
    for (const n of (tr.growth || []).slice(0, 5)) add("sec:tree", t("ctSec_tree"), `${t("ctHintTake", trName(n.name), n.points)} ${ctDelta(n.changes)}`);
    for (const n of (tr.respec || []).slice(0, 3)) {
      const id = `node:${n.id}`;
      add(d.tree.notables.some((x) => x.id === id) ? id : "sec:tree", trName(n.name), t("ctHintRespec", trName(n.name), n.points));
    }
  } else if (section === "jewels") {
    for (const sk of (await DATA.jewels()).sockets || []) {
      const row = d.jewels.find((j) => j.node === sk.node);
      if (row && sk.without) add(row.id, itemTitle(row.item), `${t("ctHintWithout")} ${ctDelta(sk.without) || t("noEffect")}`);
    }
  } else if (section === "quests") {
    for (const q of (await questsData()).choices) {
      const best = q.options.find((o) => o.best);
      if (best) add(`qst:${q.var}`, questName(q), `${t("ctHintQuest", optionTitle(q, q.options.indexOf(best)) || optionText(best))} ${ctDelta(best.changes)}`);
    }
  } else if (section === "leveling") {
    const sw = ((await DATA.leveling()).roadmap || {}).switch;
    if (sw && sw.level) add("sec:leveling", t("ctSec_leveling"), t("lrSwitchAt", sw.level, lrStageName(sw.stage)));
  }
  return out;
}
// a hint into the element's note (the text shown at once) or its tip, after what the author has written
function ctTake(id, field, text) {
  const b = auBlock(id);
  auSave(id, { [field]: b[field] ? `${b[field]}\n${text}` : text });
  CT.taken.add(`${id}|${field}|${text}`);
  toast(t("ctTaken"), true);
  ctDraw();
}
function ctHintsPanel(s) {
  if (CT.stage !== "max") return h("div", { class: "hint" }, t("ctHintsOnlyMax"));
  const box = h("div", { class: "card stack ct-hints" }, h("div", { class: "ct-title" }, "🔍 ", t("ctHints")), h("div", { class: "hint" }, t("ctHintsSub")));
  const rows = CT.hints[s];
  if (!rows) {
    box.append(loading(t("ctHintsLoading")));
    ctHints(s, CT.data).then((r) => { CT.hints[s] = r; ctDraw(); })
      .catch((e) => { CT.hints[s] = []; box.append(h("p", { class: "muted" }, e.message)); });
    return box;
  }
  if (!rows.length) box.append(h("p", { class: "muted small" }, t("ctHintsNone")));
  for (const r of rows) {
    const done = (field) => CT.taken.has(`${r.target}|${field}|${r.text}`);
    box.append(h("div", { class: "ct-hint" }, h("div", { class: "ct-hint-t" }, h("span", { class: "muted small" }, r.where), h("div", {}, r.text)),
      h("button", { class: "ghost small", disabled: done("text"), onclick: () => ctTake(r.target, "text", r.text) }, done("text") ? "✓" : t("ctToNote")),
      h("button", { class: "ghost small", disabled: done("tip"), onclick: () => ctTake(r.target, "tip", r.text) }, done("tip") ? "✓" : t("ctToTip"))));
  }
  return box;
}

// ---- the notes whose element is gone (the build updated from PoB: a gem, an item, a passive changed) ----
const CT_ELEMENT = /^(gem|sk|gear|node|jwl|qst):/;
// every element of both stages: id -> its name as the page shows it
function ctElements() {
  const out = new Map();
  for (const [stage, d] of Object.entries(CT.all)) {
    if (!d) continue;
    const tag = stage === "min" ? ` (${t("ctStage_min")})` : "";
    for (const g of d.skills) {
      out.set(g.id, g.actives.map((a) => trName(a)).join(" + "));
      for (const x of g.gems) out.set(x.id, trName(x.name));
    }
    for (const r of [...d.gear, ...d.flasks]) out.set(r.id, `${slotName(r.slot)} · ${itemTitle(r.item)}${tag}`);
    for (const n of [...d.tree.ascendancy, ...d.tree.keystones, ...d.tree.notables]) out.set(n.id, trName(n.name));
    for (const j of d.jewels) out.set(j.id, `${itemTitle(j.item)}${tag}`);
    for (const q of d.quests) out.set(q.id, questName(q));
  }
  return out;
}
// a gone element named by its id: what the author knew it as
function ctIdName(id) {
  const [kind, rest] = [id.slice(0, id.indexOf(":")), id.slice(id.indexOf(":") + 1)];
  const [what, stage] = rest.split("@");
  const tag = stage ? ` (${t("ctStage_" + stage)})` : "";
  if (kind === "gem") return trName(what);
  if (kind === "sk") return what.split("+").map((a) => trName(a)).join(" + ");
  if (kind === "gear") return slotName(what) + tag;
  if (kind === "node") return t("ctNodeId", what);
  if (kind === "jwl") return t("ctJewelId", what) + tag;
  return what;
}
function ctOrphans() {
  if ((CT.data.stages || {}).min && !CT.all.min) return [];  // the Мин is still being laid out
  if (!CT.all.max) return [];
  const els = ctElements();
  return Object.keys(AU.blocks).filter((id) => CT_ELEMENT.test(id) && !els.has(id)
    && (AU.blocks[id].text || AU.blocks[id].tip || AU.blocks[id].list));
}
const ctJoin = (a, b) => [a, b].filter(Boolean).join("\n");
// a note moved to an element of the same kind (after what that one has); the old place emptied
function ctMove(from, to) {
  const a = auBlock(from), b = auBlock(to);
  auSave(to, { text: ctJoin(b.text, a.text), tip: ctJoin(b.tip, a.tip), label: b.label || a.label });
  auSave(from, { text: "", tip: "", label: "", list: undefined });
  toast(t("ctMoved"), true);
  ctDraw();
}
async function ctDrop(id) {
  if (!(await confirmInPage(t("ctDropAsk"), t("ctDrop")))) return;
  auSave(id, { text: "", tip: "", label: "", list: undefined });
  ctDraw();
}
function ctOrphanCard() {
  const orphans = ctOrphans();
  if (!orphans.length) return null;
  const els = [...ctElements()];
  return h("div", { class: "card stack ct-orphans" }, h("div", { class: "ct-title" }, "⚠ ", t("ctOrphans", orphans.length)),
    h("div", { class: "hint" }, t("ctOrphansSub")), ...orphans.map((id) => {
      const b = AU.blocks[id], kind = id.slice(0, id.indexOf(":"));
      const sel = h("select", {}, h("option", { value: "" }, t("ctMoveTo")),
        els.filter(([k]) => k.startsWith(kind + ":")).map(([k, name]) => h("option", { value: k }, name)));
      return h("div", { class: "ct-hint" }, h("div", { class: "ct-hint-t" }, h("b", {}, ctIdName(id)),
        h("div", { class: "small" }, b.label ? h("b", {}, b.label + ": ") : null, ...auRich((b.text || b.tip || "").slice(0, 200)))),
      sel, h("button", { class: "ghost small", onclick: () => { if (sel.value) ctMove(id, sel.value); else toast(t("ctMoveTo")); } }, t("ctMove")),
      h("button", { class: "ghost small", onclick: () => ctDrop(id) }, t("ctDrop")));
    }));
}

function ctDraw() {
  if (state.page !== "ctor" || !CT.data) return;
  auKinds(CT_KINDS[CT.section] || null);
  const s = CT.section, sec = auBlock("sec:" + s);
  const head = h("div", { class: "card stack" },
    h("div", { class: "ct-title" }, I("pencil", "c-gold"), " ", t("ctTitle", state.build.name)), h("div", { class: "hint" }, t("ctSub")),
    h("div", { class: "row" }, h("button", { class: "ghost", onclick: () => ctLeave() }, "← ", t("ctBack")),
      h("button", { class: "ghost", title: t("ctCheckHint"), onclick: () => ctLeave(CT_CHECK[s]) }, "🔍 ", t("ctCheck"))),
    ctStageBar());
  const tabs = h("div", { class: "ct-tabs" }, CT_SECTIONS.map((x) => h("button", { class: x === s ? "is-on" : "",
    onclick: () => { CT.section = x; hideTip(); ctDraw(); } }, t("ctSec_" + x))));
  // the section's own notes, at its top
  const notes = h("div", { class: "stack" }, ctNote("sec:" + s, null),
    h("div", { class: "row" }, h("button", { class: "ghost small", onclick: () => ctEdit("sec:" + s, t("ctSec_" + s)) },
      sec.text || sec.tip ? t("ctSecEdit") : t("ctSecAdd")),
    h("button", { class: "ghost small" + (CT.hintsOpen === s ? " is-on" : ""), title: t("ctHintsHint"),
      onclick: () => { CT.hintsOpen = CT.hintsOpen === s ? null : s; ctDraw(); } }, "🔍 ", t("ctHints"))),
    CT.hintsOpen === s ? ctHintsPanel(s) : null);
  $("#view").replaceChildren(h("div", { class: "stack ct-page" }, ...[head, ctOrphanCard(), tabs, notes,
    ...[CT_DRAW[s](CT.data)].flat()].filter(Boolean)));
}
