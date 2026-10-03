<script setup lang="ts">
// The author's description with the game's pieces in it: paragraphs (Enter), a piece stands whole as its picture and
// name ([[kind:key]] in the saved text; Backspace takes it in one go). "@" opens a search at the caret (Enter puts
// the piece in, Esc leaves "@" as text); a piece from the panel is dragged in (where it drops) or clicked (where the
// caret is). Pasted text comes in as plain paragraphs. The counter: grey to 1400, yellow to 1500, red past it.
import type { Card } from "~~/mock/page";
import type { GameThing } from "~~/mock/game";

const props = defineProps<{ modelValue: string; cards: Record<string, Card>; max?: number }>();
const emit = defineEmits<{ "update:modelValue": [string] }>();
const MAX = computed(() => props.max ?? 1500);
const ed = ref<HTMLDivElement | null>(null);
let range: Range | null = null;
const TOKEN = /\[\[([a-z]+:[^[\]\n]{1,200})\]\]/g;
const MIME = "application/x-poe2lab-token";

function chip(key: string) {
  const c = props.cards[key];
  const el = document.createElement("span");
  el.className = `ref ${c?.kind ?? "term"}`;
  el.contentEditable = "false";
  el.dataset.tok = key;
  if (c?.img && c.kind !== "term") { const img = document.createElement("img"); img.src = gameArt(c.img); img.alt = ""; el.append(img); }
  el.append(c?.name ?? key.split(":")[1]);
  return el;
}
function fill(text: string) {
  const root = ed.value!;
  root.replaceChildren();
  for (const para of (text || "").split(/\n+/)) {
    const p = document.createElement("p");
    let last = 0;
    for (const m of para.matchAll(TOKEN)) {
      if (m.index! > last) p.append(para.slice(last, m.index));
      p.append(chip(m[1]), " ");
      last = m.index! + m[0].length;
    }
    if (last < para.length) p.append(para.slice(last));
    if (!p.childNodes.length) p.append(document.createElement("br"));
    root.append(p);
  }
}
// the text back from the field: a paragraph a line, a piece its token
function serialize(): string {
  const lines: string[] = [];
  const walk = (node: Node, acc: string[]) => {
    for (const c of node.childNodes) {
      if (c.nodeType === 3) acc.push((c.nodeValue || "").replace(/ /g, " "));
      else if (c instanceof HTMLElement && c.dataset.tok) acc.push(`[[${c.dataset.tok}]]`);
      else if (c instanceof HTMLElement && c.tagName === "BR") acc.push("\n");
      else walk(c, acc);
    }
  };
  for (const p of ed.value!.childNodes) {
    const acc: string[] = [];
    if (p.nodeType === 3) acc.push(p.nodeValue || ""); else walk(p, acc);
    lines.push(acc.join("").replace(/\s+$/g, ""));
  }
  return lines.filter((l, i, a) => l || (i > 0 && a[i - 1])).join("\n").trim();
}
// what the reader sees counts: a piece by its name
const length = computed(() => props.modelValue.replace(TOKEN, (_, k) => props.cards[k]?.name ?? "").length);
const countCls = computed(() => (length.value > MAX.value ? "bad" : length.value > MAX.value - 100 ? "warn" : ""));
const changed = () => emit("update:modelValue", serialize());

function keep() {
  const sel = getSelection();
  if (sel?.rangeCount && ed.value?.contains(sel.getRangeAt(0).startContainer)) range = sel.getRangeAt(0).cloneRange();
}
function insertNodes(nodes: Node[]) {
  const root = ed.value!;
  let r = range && root.contains(range.startContainer) ? range : null;
  if (!r) { r = document.createRange(); r.selectNodeContents(root.lastElementChild || root); r.collapse(false); }
  r.deleteContents();
  const frag = document.createDocumentFragment();
  nodes.forEach((n) => frag.append(n));
  const last = frag.lastChild!;
  r.insertNode(frag);
  const after = document.createRange();
  after.setStartAfter(last);
  after.collapse(true);
  const sel = getSelection()!;
  sel.removeAllRanges();
  sel.addRange(after);
  range = after.cloneRange();
  root.focus();
  changed();
}
const insertToken = (key: string) => insertNodes([chip(key), document.createTextNode(" ")]);
defineExpose({ insertToken });

// "@": the search at the caret
const at = reactive({ open: false, q: "", sel: 0, x: 0, y: 0 });
const atRows = computed<GameThing[]>(() => lookup(at.q, null, 6));
const atInput = ref<HTMLInputElement | null>(null);
function openAt() {
  keep();
  const box = ed.value!.parentElement!.getBoundingClientRect();
  const rect = range?.getBoundingClientRect();
  at.x = Math.max(0, Math.min((rect?.left ?? box.left) - box.left, box.width - 380));
  at.y = (rect && rect.bottom ? rect.bottom : box.top + 60) - box.top + 6;
  at.open = true; at.q = ""; at.sel = 0;
  nextTick(() => atInput.value?.focus());
}
function closeAt(insertAt: boolean) {
  at.open = false;
  if (insertAt) insertNodes([document.createTextNode("@")]);
  else ed.value?.focus();
}
function pickAt(g?: GameThing) { if (!g) return; at.open = false; insertToken(g.key); }
function atKey(e: KeyboardEvent) {
  if (e.key === "Escape") { e.preventDefault(); closeAt(true); }
  else if (e.key === "ArrowDown") { e.preventDefault(); at.sel = Math.min(atRows.value.length - 1, at.sel + 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); at.sel = Math.max(0, at.sel - 1); }
  else if (e.key === "Enter") { e.preventDefault(); pickAt(atRows.value[at.sel]); }
}

function onKey(e: KeyboardEvent) {
  if (e.key === "@") { e.preventDefault(); openAt(); }
}
// pasted text: no headings, tables or styles - plain paragraphs (a token typed in the text stays a piece)
function onPaste(e: ClipboardEvent) {
  e.preventDefault();
  keep();
  const text = (e.clipboardData?.getData("text/plain") || "").replace(/\r/g, "");
  const nodes: Node[] = [];
  text.split("\n").forEach((line, i) => {
    if (i) nodes.push(document.createElement("br"));
    let last = 0;
    for (const m of line.matchAll(TOKEN)) {
      if (m.index! > last) nodes.push(document.createTextNode(line.slice(last, m.index)));
      nodes.push(props.cards[m[1]] ? chip(m[1]) : document.createTextNode(m[0]));
      last = m.index! + m[0].length;
    }
    if (last < line.length) nodes.push(document.createTextNode(line.slice(last)));
  });
  if (nodes.length) insertNodes(nodes);
}
// a piece dragged from the panel: in where it drops
const dropping = ref(false);
function onDragOver(e: DragEvent) { if (e.dataTransfer?.types.includes(MIME)) { e.preventDefault(); dropping.value = true; } }
function onDrop(e: DragEvent) {
  dropping.value = false;
  const key = e.dataTransfer?.getData(MIME);
  if (!key) return;
  e.preventDefault();
  const pos = (document as any).caretRangeFromPoint?.(e.clientX, e.clientY) as Range | undefined;
  if (pos && ed.value!.contains(pos.startContainer)) range = pos;
  insertToken(key);
}

onMounted(() => {
  fill(props.modelValue);
  document.execCommand("defaultParagraphSeparator", false, "p");
});
</script>

<template>
  <div class="ed" style="position: relative">
    <div class="ed-bar">
      <button class="btn btn-quiet" type="button" @mousedown.prevent @click="openAt"><Ic name="at" />Вставить иконку</button>
      <span class="hint">или набери <span class="kbd">@</span> в тексте</span>
    </div>
    <div ref="ed" :class="['ed-text', { 'is-drop': dropping }]" contenteditable="true" role="textbox" aria-multiline="true" aria-label="Описание билда"
      @input="changed" @keyup="keep" @mouseup="keep" @blur="keep" @keydown="onKey" @paste="onPaste" @dragover="onDragOver" @dragleave="dropping = false" @drop="onDrop" />
    <div v-if="at.open" class="atpop" :style="{ left: `${at.x}px`, top: `${at.y}px` }">
      <div class="atpop-q"><Ic name="search" /><input ref="atInput" v-model="at.q" class="atpop-in" placeholder="Ищу…" aria-label="Найти камень, вещь, пассивку или термин" @keydown="atKey" @blur="at.open && closeAt(false)" /></div>
      <LookupRow v-for="(g, i) in atRows" :key="g.key" :g="g" :q="at.q" :on="i === at.sel" @click="pickAt(g)"><span v-if="i === at.sel" class="kbd">Enter</span></LookupRow>
      <div v-if="at.q && !atRows.length" class="hint" style="padding: 8px">Ничего не нашлось</div>
      <div class="atpop-f"><span><span class="kbd">↑</span> <span class="kbd">↓</span></span><span><span class="kbd">Enter</span> вставить</span><span><span class="kbd">Esc</span> оставить «@»</span></div>
    </div>
    <div :class="['count', countCls]"><span>Абзацы и иконки. Заголовки и таблицы — нельзя.</span><span><b>{{ fmtInt(length) }}</b> / {{ fmtInt(MAX) }}</span></div>
  </div>
</template>
