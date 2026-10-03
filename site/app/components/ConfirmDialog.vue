<script setup lang="ts">
// A question in the page itself (never the browser's own window): Enter says yes, Esc or a click outside says no.
const props = defineProps<{ title: string; text?: string; yes: string; no?: string; icon?: string; danger?: boolean }>();
const emit = defineEmits<{ yes: []; no: [] }>();
const key = (e: KeyboardEvent) => { if (e.key === "Escape") emit("no"); else if (e.key === "Enter") emit("yes"); };
onMounted(() => document.addEventListener("keydown", key));
onBeforeUnmount(() => document.removeEventListener("keydown", key));
</script>

<template>
  <div class="backdrop" @click.self="emit('no')">
    <div class="dlg" role="dialog" :aria-label="title">
      <div class="dlg-b"><span :class="['dlg-i', danger ? '' : 'warn']"><Ic :name="icon ?? (danger ? 'warn' : 'info')" /></span>
        <div><h3>{{ title }}</h3><p v-if="text">{{ text }}</p></div></div>
      <div class="dlg-f"><button class="btn btn-quiet" type="button" @click="emit('no')">{{ no ?? "Отмена" }}</button>
        <button :class="['btn', danger ? 'btn-danger' : 'btn-primary']" type="button" @click="emit('yes')">{{ props.yes }}</button></div>
    </div>
  </div>
</template>
