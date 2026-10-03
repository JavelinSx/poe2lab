<script setup lang="ts">
// The main skill's picture; until it is there, its frame with the damage type's glyph.
import type { BuildCard } from "~~/mock/builds";
defineProps<{ b: Pick<BuildCard, "icon" | "dmg">; cls?: string }>();
</script>

<template>
  <img v-if="b.icon" :class="cls ?? 'gi'" :src="gameArt(b.icon)" alt="" loading="lazy" />
  <span v-else :class="[cls ?? 'gi', 'gph', b.dmg]"><Ic :name="b.dmg === 'light' ? 'bolt' : b.dmg" /></span>
</template>
