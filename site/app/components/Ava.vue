<script setup lang="ts">
// An author's avatar: the Discord picture, or the nick's letters on its colour.
defineProps<{ nick: string; hue?: number; size?: "xs" | "s" | "l" | "xl"; src?: string }>();
</script>

<template>
  <span :class="['ava', size]" :style="{ '--h': hue ?? 210 }">
    <img v-if="src" :src="src" alt="" />
    <template v-else>{{ initials(nick) }}</template>
  </span>
</template>
