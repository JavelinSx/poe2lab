<script setup lang="ts">
// Every icon of the design (design/site/sprite.html), once per page: <Ic name="…"> refers to its symbols.
import sprite from "~/assets/sprite.svg?raw";
</script>

<template>
  <div class="sprite" aria-hidden="true" v-html="sprite" />
</template>
