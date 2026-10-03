<script setup lang="ts">
// A page that is not there, or one that broke: in the site's frame, with the next step.
import type { NuxtError } from "#app";
const props = defineProps<{ error: NuxtError }>();
const missing = computed(() => props.error.statusCode === 404);
const again = () => clearError({ redirect: useRoute().fullPath });
useHead({ title: missing.value ? "Такой страницы нет — poe2lab" : "Ошибка — poe2lab" });
</script>

<template>
  <NuxtLayout>
    <div class="wrap" style="padding: 40px 0; max-width: 620px">
      <StatePanel v-if="missing" code="404" title="Такой страницы нет" text="Возможно, ссылка с ошибкой или билд удалили.">
        <div class="row"><NuxtLink class="btn btn-primary" to="/catalog" @click="clearError()"><Ic name="grid4" />В каталог</NuxtLink>
          <NuxtLink class="btn btn-quiet" to="/" @click="clearError()">На главную</NuxtLink></div>
      </StatePanel>
      <StatePanel v-else icon="warn" tone="bad" title="Что-то сломалось" text="Мы уже получили отчёт. Обнови страницу через минуту." :hint="`код ошибки ${error.statusCode}`">
        <div class="row"><button class="btn btn-primary" type="button" @click="again"><Ic name="refresh" />Обновить</button>
          <a class="btn btn-quiet" href="https://github.com/JavelinSx/poe2lab/issues" rel="noopener"><Ic name="mail" />Сообщить</a></div>
      </StatePanel>
    </div>
  </NuxtLayout>
</template>
