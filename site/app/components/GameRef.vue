<script setup lang="ts">
// A piece of the game in a text: its picture and name; its card on hover or focus (Tab reaches it).
import type { Card } from "~~/mock/page";
defineProps<{ card: Card; pop?: "below" | "left" | "right" | "" }>();
</script>

<template>
  <span :class="['ref', card.kind, 'hov']" tabindex="0">
    <img v-if="card.img && card.kind !== 'term'" :src="gameArt(card.img)" alt="" />
    <span v-else-if="card.ph" :class="['gph', card.ph]"><Ic :name="card.ph === 'light' ? 'bolt' : card.ph" /></span>{{ card.name }}
    <span :class="['pop', pop ?? 'below']"><TipCard :card="card" /></span>
  </span>
</template>
