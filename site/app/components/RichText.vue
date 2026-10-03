<script setup lang="ts">
// The author's text: paragraphs, and the pieces of the game written into it as tokens ([[skill:ice-strike]]) shown
// with their pictures and cards. Everything else is plain text (the page never takes the author's HTML).
import type { Card } from "~~/shared/package";
const props = defineProps<{ text: string; cards: Record<string, Card>; inline?: boolean }>();
const TOKEN = /\[\[([a-z]+:[^[\]\n]{1,200})\]\]/g;
const paragraphs = computed(() => props.text.split(/\n+/).map((p) => {
  const parts: ({ text: string } | { card: Card; key: string })[] = [];
  let last = 0;
  for (const m of p.matchAll(TOKEN)) {
    if (m.index! > last) parts.push({ text: p.slice(last, m.index) });
    const key = m[1]!, card = props.cards[key];
    parts.push(card ? { card, key } : { text: key.split(":")[1] ?? key });
    last = m.index! + m[0].length;
  }
  if (last < p.length) parts.push({ text: p.slice(last) });
  return parts;
}));
</script>

<template>
  <template v-if="inline">
    <template v-for="(x, i) in paragraphs[0]" :key="i"><GameRef v-if="'card' in x" :card="x.card" /><template v-else>{{ x.text }}</template></template>
  </template>
  <template v-else>
    <p v-for="(p, n) in paragraphs" :key="n">
      <template v-for="(x, i) in p" :key="i"><GameRef v-if="'card' in x" :card="x.card" /><template v-else>{{ x.text }}</template></template>
    </p>
  </template>
</template>
