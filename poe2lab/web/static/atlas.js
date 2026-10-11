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
const AT = { data: null, part: "Main", show: "route", focus: null, mark: null, view: null };

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
  view.replaceChildren(atlasPage(AT.data));
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
  const masters = h("div", { class: "ws-tiles three" }, ["hilda", "doryani", "jado"].map((k) =>
    h("div", { class: "ws-tile" }, h("span", { class: "ws-ic" }, I("person")), h("div", {}, h("b", {}, t("atM_" + k)), h("span", {}, t("atMS_" + k))))));

  return h("div", { class: "ws at-page" },
    h("div", { class: "ws-hero" }, h("span", { class: "ws-crest" }, I("map")),
      h("div", {}, h("h1", {}, t("atTitle")), h("p", {}, t("atSub")))),
    h("div", { class: "at-warn" }, I("warn"), h("span", {}, h("b", {}, t("atWarnT")), " ", t("atWarnS"))),
    sec(t("atHowTitle"), t("atHowSub")), how,
    sec(t("atFirstTitle"), t("atFirstSub", total)), firstTiles,
    sec(t("atTreeTitle"), t("atTreeSub")),
    h("section", { class: "card at-card" }, h("div", { class: "at-bar" }, parts, modes, legend), map.box),
    sec(t("atStagesTitle"), t("atStagesSub")), stageTiles,
    sec(t("atUsefulTitle"), t("atUsefulSub")), usefulTiles,
    sec(t("atMastersTitle"), t("atMastersSub")), masters,
    h("p", { class: "hint at-src" }, t("atSource")));
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
