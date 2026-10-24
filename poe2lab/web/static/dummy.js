// ---------- the dummy: the build's damage per second on dummies laid out by hand (poe2lab.analysis.dummy) ----------
// The field is in metres: the character at 0,0, the dummies, each skill's target point (its area, or the way its
// projectiles fly), the curses' zones and the Mirrors of Refraction - all dragged by hand. Each skill is used the way
// the player sets it: spammed for a share of the time, on its cooldown, every N seconds, at a rate of its own.
const DM_FIELD = { x0: -4, x1: 22, y0: -9, y1: 9 };  // metres shown
const DM_KIND_COLOR = { normal: "#9aa3ad", rare: "#e8c547", boss: "#e0803a", pinnacle: "#d9534f", uber: "#b04ad9" };
const DM_SKILL_COLORS = ["#5fb4ff", "#5fc98d", "#ffb347", "#c38bff", "#ff7aa8", "#7fe0e0", "#e0e070", "#ff8f5f"];
const DM_STATES = ["shock", "freeze", "chill", "ignite", "armourBreak", "coldExposure", "fireExposure", "lightningExposure", "electrocute"];
const DM = { cat: null, build: null, sc: null, res: null, timer: 0, token: 0 };

const dmKey = () => "poe2lab.dummy:" + (state.build ? state.build.name : "");
function dmSave() { try { localStorage.setItem(dmKey(), JSON.stringify(DM.sc)); } catch (_) { /* storage blocked */ } }

// the dummies of a preset: one target, or a pack spread in a circle (always the same: the layout is the player's)
function dmPreset(kind, n, boss) {
  if (n === 1) return [{ id: "d1", x: 9, y: 0, kind }];
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = i * 2.39996, r = 0.6 * Math.sqrt(i + 0.5) * 1.15;  // a sunflower: even spacing
    out.push({ id: "d" + (i + 1), x: +(9 + r * Math.cos(a)).toFixed(2), y: +(r * Math.sin(a)).toFixed(2), kind });
  }
  if (boss) out[0].kind = boss;
  return out;
}

// a new scenario for the build: the dummies at the pack, the strongest spammable skill spammed, the ones with a
// cooldown on it, the triggered ones at a rate of one a second
function dmDefault(cat) {
  const dmg = cat.filter((s) => s.kind === "damage");
  const spam = dmg.filter((s) => !s.cooldown && !s.triggered && !s.travel && !s.sustained).sort((a, b) => b.dps - a.dps)[0];
  const skills = {};
  dmg.forEach((s) => {
    skills[s.id] = { on: true, x: 9, y: 0, states: [], split: !!s.sustained, sim: true, speed: 4, range: 12, width: 0.3, critPerPierce: 0,
      mode: s.triggered ? "rate" : s.sustained ? "sustain" : s.cooldown ? "cooldown" : "spam", share: s === spam ? 100 : 0, rate: 1, interval: 4 };
  });
  const curses = {};
  cat.filter((s) => s.kind === "curse").forEach((s) => { curses[s.id] = { on: true, x: 9, y: 0 }; });
  // the mirrors' spots: in your Presence (4 m) around you, as many as can be at once
  const mirrors = cat.some((s) => s.kind === "mirror") ? dmMirrorRing() : [];
  return { level: 83, dummies: dmPreset("normal", 20), skills, curses, mirrors, always: [] };
}
function dmMirrorRing() {
  // one on the way to the dummies (you aim through it in the game), the others around you
  return [0, 1, 2, 3].map((i) => ({ x: +(3 * Math.cos(i * Math.PI / 2)).toFixed(2), y: +(3 * Math.sin(i * Math.PI / 2)).toFixed(2) }));
}

TABS.dummy = async (view) => {
  view.replaceChildren(loading(t("dmLoading")));
  const r = await cached("dummy-skills", () => api(`/api/dummy/skills?${buildQuery()}`));
  DM.cat = r.skills;
  if (DM.build !== state.build.name || !DM.sc) {
    DM.build = state.build.name;
    try { DM.sc = JSON.parse(localStorage.getItem(dmKey()) || "null"); } catch (_) { DM.sc = null; }
    if (!DM.sc || !DM.sc.dummies) DM.sc = dmDefault(DM.cat);
    // skills added to the build since: default placements
    const fresh = dmDefault(DM.cat);
    for (const [k, v] of Object.entries(fresh.skills)) if (!DM.sc.skills[k]) DM.sc.skills[k] = { ...v, share: 0 };
    for (const [k, v] of Object.entries(fresh.curses)) if (!DM.sc.curses[k]) DM.sc.curses[k] = v;
  }
  const root = h("div", { class: "stack dm" });
  const draw = () => root.replaceChildren(dmHead(draw), h("div", { class: "dm-main" }, dmField(draw), dmPanel(draw)), dmResult());
  DM.redraw = draw;
  draw();
  dmCalc();
  return root;
};

// recount after a change (the last one wins)
function dmChanged(redraw = true) {
  dmSave();
  if (redraw && DM.redraw) DM.redraw();
  clearTimeout(DM.timer);
  DM.timer = setTimeout(dmCalc, 250);
}
async function dmCalc() {
  const token = ++DM.token;
  try {
    const res = await api(`/api/dummy/calc?${buildQuery()}`, { method: "POST", body: { scenario: DM.sc } });
    if (token !== DM.token) return;
    DM.res = res;
  } catch (e) { DM.res = { error: e.message }; }
  const box = document.querySelector(".dm-result");
  if (box) box.replaceWith(dmResult());
  dmDrawCrystals();
  document.querySelectorAll(".dm-dummy").forEach((el) => {
    const d = DM.res && DM.res.dummies ? DM.res.dummies.find((x) => x.id === el.dataset.id) : null;
    el.querySelector("title").textContent = d ? t("dmDummyTip", fmt(d.dps), d.states.map((x) => t("dmSt_" + x)).join(", ") || "—") : "";
  });
}

// the crystals one use of each ice-crystal skill puts (the server lays them out from the gems)
function dmDrawCrystals() {
  const g = document.querySelector(".dm-crystals"), m = DM.fieldMap;
  if (!g || !m) return;
  const spots = (DM.res && DM.res.crystalSpots) || {};
  g.replaceChildren(...Object.values(spots).flat().map(([x, y]) => m.el("circle", { cx: m.X(x), cy: m.Y(y), r: 3, class: "dm-crystal" })));
}

// how wide a dummy is: the player's, else its kind's (a pinnacle boss is a big target)
const DM_KIND_RADIUS = { normal: 0.6, rare: 0.8, boss: 2.0, pinnacle: 2.5, uber: 2.5 };
const dmRadius = (d) => d.r || DM_KIND_RADIUS[d.kind] || 0.6;

// presets, the dummies' kind, the enemy's level
function dmHead(draw) {
  const sc = DM.sc;
  const preset = (label, fn) => h("button", { class: "chip mt-filter", onclick: () => { sc.dummies = fn(); dmChanged(); } }, label);
  const kind = h("select", { onchange: (e) => { sc.dummies.forEach((d) => { d.kind = e.target.value; delete d.r; }); dmChanged(); } },
    ["normal", "rare", "boss", "pinnacle", "uber"].map((k) => h("option", { value: k, selected: sc.dummies.every((d) => d.kind === k) }, t("dmKind_" + k))));
  const level = h("input", { type: "number", min: 1, max: 100, value: sc.level, style: "width:64px",
    onchange: (e) => { sc.level = Math.max(1, Math.min(100, +e.target.value || 83)); dmChanged(false); } });
  const always = h("div", { class: "row at-chips" }, h("span", { class: "muted small" }, t("dmAlways")),
    DM_STATES.map((k) => h("button", { class: "chip mt-filter" + (sc.always.includes(k) ? " on" : ""),
      onclick: () => { sc.always = sc.always.includes(k) ? sc.always.filter((x) => x !== k) : [...sc.always, k]; dmChanged(); } }, t("dmSt_" + k))));
  return h("div", { class: "card stack" }, h("div", { class: "row" }, h("h3", {}, I("target"), " ", t("dmTitle")),
    preset(t("dmOne"), () => dmPreset("pinnacle", 1)), preset(t("dmPack", 20), () => dmPreset("normal", 20)),
    preset(t("dmPackRare"), () => dmPreset("normal", 20, "rare")),
    h("label", { class: "row small" }, t("dmKind"), kind),
    h("label", { class: "row small", title: t("dmRadiusHint") }, t("dmRadius"), h("input", { type: "number", min: 0.2, max: 10, step: 0.1,
      value: sc.dummies.length ? dmRadius(sc.dummies[0]) : 0.6, style: "width:60px",
      onchange: (e) => { const r = Math.max(0.2, Math.min(10, +e.target.value || 0.6)); sc.dummies.forEach((d) => { d.r = r; }); dmChanged(); } })),
    h("label", { class: "row small" }, t("dmLevel"), level)),
    h("div", { class: "sub" }, t("dmSub")), always);
}

// the field: metres to the SVG, everything draggable
function dmField(draw) {
  const sc = DM.sc, W = 620, H = Math.round(W * (DM_FIELD.y1 - DM_FIELD.y0) / (DM_FIELD.x1 - DM_FIELD.x0));
  const k = W / (DM_FIELD.x1 - DM_FIELD.x0);
  const X = (m) => (m - DM_FIELD.x0) * k, Y = (m) => (m - DM_FIELD.y0) * k;
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, ...kids) => { const e = document.createElementNS(NS, tag); for (const [a, v] of Object.entries(attrs)) e.setAttribute(a, v); kids.forEach((c) => c && e.append(c)); return e; };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "dm-field" });
  DM.fieldMap = { X, Y, el };
  for (let m = Math.ceil(DM_FIELD.x0); m <= DM_FIELD.x1; m++) svg.append(el("line", { x1: X(m), y1: 0, x2: X(m), y2: H, class: m % 5 ? "dm-grid" : "dm-grid5" }));
  for (let m = Math.ceil(DM_FIELD.y0); m <= DM_FIELD.y1; m++) svg.append(el("line", { x1: 0, y1: Y(m), x2: W, y2: Y(m), class: m % 5 ? "dm-grid" : "dm-grid5" }));
  // drag: the point follows the pointer (in metres); the field is drawn anew and the damage counted on release
  const drag = (node, get, set) => {
    node.style.cursor = "grab";
    node.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      node.setPointerCapture(e.pointerId);
      const rect = svg.getBoundingClientRect(), scale = W / rect.width;
      const move = (ev) => {
        const mx = DM_FIELD.x0 + (ev.clientX - rect.left) * scale / k, my = DM_FIELD.y0 + (ev.clientY - rect.top) * scale / k;
        set(+mx.toFixed(2), +my.toFixed(2));
        if (node.tagName === "rect") {
          node.setAttribute("x", X(mx) - 6); node.setAttribute("y", Y(my) - 6);
          node.setAttribute("transform", `rotate(45 ${X(mx)} ${Y(my)})`);
        } else { node.setAttribute("cx", X(mx)); node.setAttribute("cy", Y(my)); }
      };
      const up = () => {
        node.removeEventListener("pointermove", move);
        node.removeEventListener("pointerup", up);
        dmChanged();
      };
      node.addEventListener("pointermove", move);
      node.addEventListener("pointerup", up);
    });
  };
  const dmg = DM.cat.filter((s) => s.kind === "damage");
  // curses: their zone (around the character when Blasphemy carries them)
  DM.cat.filter((s) => s.kind === "curse").forEach((s) => {
    const p = sc.curses[s.id];
    if (!p || !p.on) return;
    const cx = s.inAura ? 0 : p.x, cy = s.inAura ? 0 : p.y;
    svg.append(el("circle", { cx: X(cx), cy: Y(cy), r: (s.radius || 2) * k, class: "dm-curse" }, el("title", {}, `${trName(s.name)} · ${fmt(s.radius, 1)} м`)));
    if (!s.inAura) {
      const c = el("circle", { cx: X(cx), cy: Y(cy), r: 6, class: "dm-curse-pin" }, el("title", {}, trName(s.name)));
      drag(c, () => p, (x, y) => { p.x = x; p.y = y; });
      svg.append(c);
    }
  });
  // each skill: its area at its target, or its projectiles' way from the character
  dmg.forEach((s, i) => {
    const p = sc.skills[s.id];
    if (!p || !p.on) return;
    const color = DM_SKILL_COLORS[i % DM_SKILL_COLORS.length];
    if (s.projectile) {
      const a = Math.atan2(p.y, p.x), len = 12;
      svg.append(el("line", { x1: X(0), y1: Y(0), x2: X(len * Math.cos(a)), y2: Y(len * Math.sin(a)), stroke: color, class: "dm-ray" }));
    } else {
      svg.append(el("circle", { cx: X(p.x), cy: Y(p.y), r: (s.radius || s.radius2 || 1) * k, stroke: color, fill: color, class: "dm-area" },
        el("title", {}, `${trName(s.name)} · ${fmt(s.radius || s.radius2 || 1, 1)} м`)));
    }
    const pin = el("circle", { cx: X(p.x), cy: Y(p.y), r: 7, fill: color, class: "dm-pin" }, el("title", {}, trName(s.name)));
    drag(pin, () => p, (x, y) => { p.x = x; p.y = y; });
    svg.append(pin);
  });
  // the ice crystals of one use of each crystal skill (where the last count put them)
  svg.append(el("g", { class: "dm-crystals" }));
  // mirrors
  sc.mirrors.forEach((m, i) => {
    const d = el("rect", { x: X(m.x) - 6, y: Y(m.y) - 6, width: 12, height: 12, transform: `rotate(45 ${X(m.x)} ${Y(m.y)})`, class: "dm-mirror" },
      el("title", {}, t("dmMirror")));
    d.addEventListener("dblclick", () => { sc.mirrors.splice(i, 1); dmChanged(); });
    drag(d, () => m, (x, y) => { m.x = x; m.y = y; });
    svg.append(d);
  });
  // the dummies
  sc.dummies.forEach((d) => {
    const c = el("circle", { cx: X(d.x), cy: Y(d.y), r: dmRadius(d) * k, fill: DM_KIND_COLOR[d.kind] || "#999", class: "dm-dummy", "data-id": d.id }, el("title", {}, ""));
    drag(c, () => d, (x, y) => { d.x = x; d.y = y; });
    svg.append(c);
  });
  svg.append(el("circle", { cx: X(0), cy: Y(0), r: 8, class: "dm-player" }, el("title", {}, t("dmYou"))));
  return h("div", { class: "card dm-field-card" }, svg, h("div", { class: "hint" }, t("dmFieldHint")));
}

// a projectile skill flown tick by tick: its speed and range (PoB knows only the speed's modifier), the crit chance
// a pierce adds (from gear), and the gem's "more damage after piercing"
function dmFlight(s, p) {
  const num = (key, step, title) => h("input", { type: "number", min: 0, step, value: p[key] ?? "", title, style: "width:60px",
    onchange: (e) => { p[key] = +e.target.value; dmChanged(false); } });
  return h("div", { class: "dm-flight stack" },
    h("label", { class: "row small" }, h("input", { type: "checkbox", checked: p.sim !== false, onchange: (e) => { p.sim = e.target.checked; dmChanged(); } }), t("dmSim")),
    p.sim !== false && DM.cat.some((x) => x.crystal) ? h("label", { class: "row small", title: t("dmCrystalPierceHint") },
      h("input", { type: "checkbox", checked: p.crystalPierce !== false, onchange: (e) => { p.crystalPierce = e.target.checked; dmChanged(false); } }), t("dmCrystalPierce")) : null,
    p.sim !== false && DM.cat.some((x) => x.kind === "mirror") ? h("label", { class: "row small", title: t("dmMirrorPierceHint") },
      h("input", { type: "checkbox", checked: p.mirrorPierce !== false, onchange: (e) => { p.mirrorPierce = e.target.checked; dmChanged(false); } }), t("dmMirrorPierce")) : null,
    p.sim !== false ? h("div", { class: "row small" },
      t("dmBaseSpeed"), num("speed", 0.5, t("dmBaseSpeedHint")), h("span", { class: "muted" }, `×${fmt(s.speedMod, 2)}`),
      ...(s.duration > 0 ? [h("span", { class: "muted", title: t("dmLifeHint") }, t("dmLife", fmt(s.duration, 2)))] : [t("dmRange"), num("range", 1)]), t("dmWidth"), num("width", 0.1, t("dmWidthHint")), t("dmCritPierce"), num("critPerPierce", 5, t("dmCritPierceHint"))) : null,
    p.sim !== false && (s.flight || []).length ? h("div", { class: "stack dm-beyond" }, h("div", { class: "muted small" }, t("dmFlightCounted")),
      s.flight.map((f) => h("div", { class: "small" }, h("b", {}, t("dmWhen_" + f.when)), " ", f.local || f.text,
        h("span", { class: "muted" }, ` — ${f.item ? trItem(f.from) : trName(f.from)}${f.scale !== 1 ? ` ×${fmt(f.scale, 2)} → ${f.line}` : ""}`)))) : null);
}

// what PoB leaves out of the skill (its gems' stats, its weapon set's gear lines) and the dummy cannot count either
function dmNotCounted(s) {
  const rows = s.notCounted || [];
  if (!rows.length) return null;
  return h("details", { class: "dm-beyond" }, h("summary", { class: "muted small" }, t("dmNotCounted", rows.length)),
    rows.map((n) => h("div", { class: "small" }, n.local || n.text, h("span", { class: "muted" }, ` — ${n.item ? trItem(n.from) : trName(n.from)}`))));
}

// the panel: each skill's use and what it puts on the dummies in its area, the curses, the mirrors
function dmPanel(draw) {
  const sc = DM.sc;
  const dmg = DM.cat.filter((s) => s.kind === "damage");
  const card = (s, i) => {
    const p = sc.skills[s.id];
    const color = DM_SKILL_COLORS[i % DM_SKILL_COLORS.length];
    const mode = h("select", { onchange: (e) => { p.mode = e.target.value; dmChanged(); } },
      ["spam", "cooldown", "interval", "rate", "sustain"].map((m) => h("option", { value: m, selected: p.mode === m }, t("dmMode_" + m))));
    const field = p.mode === "spam" ? h("input", { type: "number", min: 0, max: 100, value: p.share, title: t("dmShareHint"), onchange: (e) => { p.share = +e.target.value; dmChanged(false); } })
      : p.mode === "interval" ? h("input", { type: "number", min: 0.1, step: 0.1, value: p.interval, onchange: (e) => { p.interval = +e.target.value; dmChanged(false); } })
        : p.mode === "rate" ? h("input", { type: "number", min: 0, step: 0.1, value: p.rate, onchange: (e) => { p.rate = +e.target.value; dmChanged(false); } }) : null;
    const unit = { spam: "%", interval: t("dmSec"), rate: t("dmPerSec") }[p.mode] || "";
    const states = h("div", { class: "row at-chips" }, DM_STATES.slice(0, 5).map((k) => h("button", { class: "chip mt-filter small" + ((p.states || []).includes(k) ? " on" : ""),
      onclick: () => { p.states = (p.states || []).includes(k) ? p.states.filter((x) => x !== k) : [...(p.states || []), k]; dmChanged(); } }, t("dmSt_" + k))));
    const facts = [s.projectile ? t("dmProj", s.projectiles, s.pierce >= 100 ? t("dmPierceAll") : s.pierce ? t("dmPierceN", s.pierce) : "") : t("dmArea", fmt(s.radius || s.radius2 || 1, 1)),
      s.returns ? t("dmReturns") : null, s.cooldown ? t("dmCd", fmt(s.cooldown, 2)) : t("dmSpeed", fmt(s.speed, 2)), t("dmPerUse", fmt(s.perUse))].filter(Boolean).join(" · ");
    return h("div", { class: "dm-skill" + (p.on ? "" : " off") },
      h("div", { class: "row" }, h("input", { type: "checkbox", checked: p.on, onchange: (e) => { p.on = e.target.checked; dmChanged(); } }),
        h("span", { class: "dm-dot", style: `background:${color}` }), gemName(s.name), s.triggered ? h("span", { class: "chip tag small" }, t("dmTriggered")) : null,
        weaponSetPicker(s.group, s.boundSet, s.fixedSet)),
      h("div", { class: "muted small" }, facts),
      s.crystal ? h("div", { class: "muted small", title: t("dmCrystalHint") }, t("dmCrystals", s.crystal.perUse, fmt(s.crystal.life),
        fmt(s.crystal.explosionRadius, 1), fmt(s.crystal.duration, 1))) : null,
      p.on ? h("div", { class: "row small" }, mode, field, unit,
        h("label", { class: "row small", title: t("dmSplitHint") }, h("input", { type: "checkbox", checked: !!p.split, onchange: (e) => { p.split = e.target.checked; dmChanged(false); } }), t("dmSplit"))) : null,
      p.on ? states : null,
      p.on && s.projectile && !s.sustained ? dmFlight(s, p) : null,
      dmNotCounted(s));
  };
  const curses = DM.cat.filter((s) => s.kind === "curse").map((s) => {
    const p = sc.curses[s.id];
    return h("div", { class: "dm-skill" + (p.on ? "" : " off") }, h("div", { class: "row" },
      h("input", { type: "checkbox", checked: p.on, onchange: (e) => { p.on = e.target.checked; dmChanged(); } }), gemName(s.name),
      h("span", { class: "muted small" }, s.inAura ? t("dmAura", fmt(s.radius, 1)) : t("dmZone", fmt(s.radius, 1)))));
  });
  const mirror = DM.cat.find((s) => s.kind === "mirror");
  const mirrors = mirror ? h("div", { class: "dm-skill" }, h("div", { class: "row" }, gemName(mirror.name),
    h("span", { class: "muted small" }, t("dmMirrorRate", fmt(mirror.cooldown, 2), sc.mirrors.length))),
  h("label", { class: "row small", title: t("dmMirrorCopiesHint", mirror.copies) }, t("dmMirrorCopies"),
    h("input", { type: "number", min: 1, max: 20, value: sc.mirrorCopies || mirror.copies, style: "width:56px",
      onchange: (e) => { sc.mirrorCopies = Math.max(1, Math.min(20, +e.target.value || mirror.copies)); dmChanged(false); } }),
    h("span", { class: "muted" }, t("dmMirrorCopiesGem", mirror.copies))),
  h("div", { class: "row" }, h("button", { class: "ghost small", onclick: () => { sc.mirrors.push({ x: 4 + sc.mirrors.length, y: 0.2 * (sc.mirrors.length % 2 ? -1 : 1) }); dmChanged(); } }, "+ ", t("dmAddMirror")),
    h("button", { class: "ghost small", onclick: () => { sc.mirrors = dmMirrorRing(); dmChanged(); } }, t("dmMirrorRing")),
    sc.mirrors.length ? h("button", { class: "ghost small", onclick: () => { sc.mirrors = []; dmChanged(); } }, t("dmNoMirrors")) : null),
  h("div", { class: "hint" }, t("dmMirrorHint"))) : null;
  const reset = h("button", { class: "ghost small", onclick: () => { DM.sc = dmDefault(DM.cat); dmChanged(); } }, t("dmReset"));
  return h("div", { class: "card stack dm-panel" }, h("div", { class: "row" }, h("h3", {}, t("dmLinks")), reset), ...dmg.map(card),
    curses.length ? h("div", { class: "section-title" }, t("dmCurses")) : null, ...curses, mirrors);
}

// the answer: in all, the best single dummy, each skill
function dmResult() {
  const r = DM.res;
  if (!r) return h("div", { class: "card dm-result" }, loading(t("dmCounting")));
  if (r.error) return h("div", { class: "card dm-result" }, h("p", { class: "bad" }, r.error));
  const top = Math.max(1, ...r.skills.map((s) => s.dps));
  return h("div", { class: "card stack dm-result" },
    h("div", { class: "row dm-kpis" }, h("div", { class: "dm-kpi" }, h("b", {}, fmt(r.total)), h("span", {}, t("dmTotal", r.dummies.length))),
      h("div", { class: "dm-kpi" }, h("b", {}, fmt(r.best)), h("span", {}, t("dmBest"))),
      r.mirrorShare !== null && r.mirrorShare !== undefined ? h("div", { class: "dm-kpi" }, h("b", {}, `${fmt(r.mirrorShare * 100)}%`), h("span", {}, t("dmMirrorShare"))) : null),
    h("div", { class: "stack" }, r.skills.map((s) => h("div", { class: "dm-bar" }, h("span", { class: "dm-bar-n" }, gemName(s.name), s.explosions ? ` — ${t("dmExplosions")}` : ""),
      h("span", { class: "dm-bar-v" }, h("i", { style: `width:${Math.max(1, s.dps / top * 100)}%` })),
      h("b", {}, fmt(s.dps)), h("span", { class: "muted small" }, t("dmUses", fmt(s.uses, 2), s.hit),
        s.sim ? h("div", { class: "small" }, t("dmSimStats", fmt(s.sim.shattered, 1), fmt(s.sim.copiesPerCast, 1), fmt(s.sim.hitsPerCast, 1), fmt(s.sim.avgPierced, 1), s.sim.maxPierced, Math.max(0, ...(s.sim.inAir || [0])))) : null,
        s.sim && s.sim.crystalsPierced ? h("div", { class: "small" }, t("dmCrystalsPierced", fmt(s.sim.crystalsPierced, 1))) : null,
        s.crystals ? h("div", { class: "small" }, t("dmCrystalStats", s.crystals.perUse, fmt(s.crystals.broken, 1), s.crystals.alive)) : null)))),
    h("div", { class: "hint" }, t("dmHonest")));
}
