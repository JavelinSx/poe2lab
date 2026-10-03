<script setup lang="ts">
// "◎ Монах · Заклинатель": the class's sign, its name, the ascendancy.
import { className, type ClassKey } from "~~/shared/catalog";
defineProps<{ cls: ClassKey; asc: string }>();
</script>

<template>
  <span class="clsline">
    <span :class="['cls', `k-${cls}`]"><Ic :name="`c-${cls}`" /></span><b>{{ className(cls) }}</b><span class="sep">·</span>{{ asc }}
  </span>
</template>
