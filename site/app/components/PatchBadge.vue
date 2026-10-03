<script setup lang="ts">
// The patch a build was made for: an earlier one in yellow (its numbers may be counted otherwise now).
defineProps<{ patch: string; old?: boolean }>();
</script>

<template>
  <span v-if="old" class="patch old">{{ patch }} · устарел</span>
  <span v-else class="patch">{{ patch }}</span>
</template>
