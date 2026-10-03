<script setup lang="ts">
// A rating as five stars, halves included.
const props = defineProps<{ r: number; cls?: string }>();
const half = computed(() => Math.round(props.r * 2) / 2);
const kind = (i: number) => (i <= half.value ? "full" : i - 0.5 === half.value ? "half" : "off");
</script>

<template>
  <span :class="['stars', cls]" :aria-label="`Оценка ${fmtRating(r)} из 5`">
    <template v-for="i in 5" :key="i">
      <Ic v-if="kind(i) === 'full'" name="star" />
      <Ic v-else-if="kind(i) === 'half'" name="star-h" />
      <Ic v-else name="star" cls="off" />
    </template>
  </span>
</template>
