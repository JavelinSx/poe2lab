<script setup lang="ts">
// An icon of the sprite (SiteSprite): one colour, it takes the text's.
defineProps<{ name: string; cls?: string }>();
</script>

<template>
  <svg :class="['ic', cls]" aria-hidden="true"><use :href="`#i-${name}`" /></svg>
</template>
