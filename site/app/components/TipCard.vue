<script setup lang="ts">
// A thing's card as the game shows it: its name and kind, tags, numbers, mods, runes, a quote; and where the text
// comes from when it is the game's own data.
import type { Card } from "~~/shared/package";
const props = defineProps<{ card: Card }>();
const head = computed(() => (props.card.kind === "support" ? "skill" : props.card.kind));
</script>

<template>
  <span class="tipcard" style="display: block">
    <span :class="['tc-h', head]" style="display: block"><b>{{ card.name }}</b><small v-if="card.sub">{{ card.sub }}</small></span>
    <span class="tc-b">
      <span v-if="card.tags?.length" class="tc-tags"><span v-for="t in card.tags" :key="t">{{ t }}</span></span>
      <template v-if="card.kv?.length">
        <span v-for="[k, v] in card.kv" :key="k" class="kv">{{ k }}: <b>{{ v }}</b></span>
        <span v-if="card.mods?.length" class="tc-sep" />
      </template>
      <span v-for="m in card.mods || []" :key="m" class="tc-mod">{{ m }}</span>
      <template v-if="card.runes?.length">
        <span class="tc-sep" />
        <span v-for="r in card.runes" :key="r.text" class="tc-rune"><img :src="gameArt(r.img)" alt="" />{{ r.text }}</span>
      </template>
      <template v-if="card.desc">
        <span v-if="card.mods?.length || card.kv?.length" class="tc-sep" />
        <span :class="card.kind === 'term' ? '' : 'tc-desc'" :style="card.kind === 'term' ? 'text-align: left' : undefined">{{ card.desc }}</span>
      </template>
    </span>
    <span v-if="card.game" class="tc-site"><Ic name="info" />Описание из данных игры · патч 0.5.5</span>
  </span>
</template>
