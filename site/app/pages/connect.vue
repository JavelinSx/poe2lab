<script setup lang="ts">
// Connecting the app: poe2lab shows a code and asks to publish for this account; here the player checks the code is
// the same and allows (or declines). The code lives 10 minutes (docs/SITE.md: the device code). Without a code in the
// address, the player types it.
const route = useRoute();
const router = useRouter();
const me = useMe();
const toast = useToast();
const clean = (v: unknown) => String(v || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
const code = computed(() => clean(route.query.code));
const typed = ref("");
const ask = ref<{ name: string; state: string; expiresIn: number } | null>(null);
const failed = ref("");
const state = ref<"ask" | "done" | "declined">("ask");
const busy = ref(false);

async function load() {
  ask.value = null; failed.value = "";
  if (code.value.length !== 6 || !me.value) return;
  try { ask.value = await $fetch(`/api/device/${code.value}`); } catch (e) { failed.value = apiError(e); }
}
watch([code, me], load, { immediate: true });
const enter = () => router.replace({ query: { code: clean(typed.value) } });
async function answer(allow: boolean) {
  busy.value = true;
  try {
    await $fetch("/api/device/confirm", { method: "POST", body: { code: code.value, allow } });
    state.value = allow ? "done" : "declined";
  } catch (e) { toast(apiError(e), { bad: true }); await load(); } finally { busy.value = false; }
}
const minutes = computed(() => Math.max(1, Math.ceil((ask.value?.expiresIn ?? 0) / 60)));
useHead({ title: "Подключить poe2lab — poe2lab" });
</script>

<template>
  <div class="center">
    <div v-if="!me" class="card ornate auth">
      <h1>Подключить poe2lab</h1><p>Сначала войди — приложение будет публиковать билды от имени твоего аккаунта.</p>
      <div class="prov"><NuxtLink class="btn btn-discord" :to="{ path: '/login', query: { next: route.fullPath } }"><Ic name="login" />Войти</NuxtLink></div>
    </div>
    <div v-else-if="code.length !== 6" class="card ornate auth">
      <span class="state-art gold" style="width: 72px; height: 72px; margin: 0 auto"><Ic name="plug" style="width: 30px; height: 30px" /></span>
      <h1>Подключить poe2lab</h1>
      <p>Открой в приложении «Опубликовать» — оно покажет код из 6 знаков. Введи его здесь.</p>
      <form class="field" style="margin-top: 18px" @submit.prevent="enter">
        <input v-model="typed" class="input" maxlength="7" placeholder="K7Q-4MX" aria-label="Код из приложения"
          style="height: 50px; font-size: 22px; text-align: center; letter-spacing: .2em; text-transform: uppercase" />
        <div class="prov" style="margin-top: 12px"><button class="btn btn-primary btn-lg" type="submit" style="justify-content: center" :disabled="clean(typed).length !== 6">Дальше</button></div>
      </form>
    </div>
    <div v-else-if="failed" class="card auth">
      <h1>Код не подошёл</h1><p>{{ failed }}</p>
      <div class="prov"><button class="btn" type="button" style="justify-content: center" @click="typed = ''; router.replace({ query: {} })">Ввести другой код</button></div>
    </div>
    <div v-else-if="!ask" class="card auth"><span class="skel" style="height: 120px" /></div>
    <div v-else-if="state === 'ask'" class="card ornate auth">
      <span class="state-art gold" style="width: 72px; height: 72px; margin: 0 auto"><Ic name="plug" style="width: 30px; height: 30px" /></span>
      <h1>Подключить poe2lab</h1>
      <p>Приложение просит публиковать билды от имени <b style="color: var(--text)">{{ me.nick }}</b>. Проверь, что код совпадает с тем, что в окне приложения.</p>
      <div class="codecells" :aria-label="`Код ${code.slice(0, 3)}-${code.slice(3)}`">
        <template v-for="(ch, i) in code" :key="i"><i v-if="i === 3" /><span>{{ ch }}</span></template></div>
      <p class="hint">Код действует ещё {{ minutes }} {{ plural(minutes, "минуту", "минуты", "минут") }}</p>
      <div class="device"><Ic name="monitor" /><span style="flex: 1"><b>{{ ask.name }}</b><span>ждёт ответа</span></span></div>
      <div class="perm">
        <div class="yes"><Ic name="check" /><span>Публиковать и обновлять твои билды: скиллы, снаряжение, цифры, описание</span></div>
        <div class="no"><Ic name="x" /><span>Не видит почту и пароль Discord, не меняет ник, не удаляет аккаунт и отзывы</span></div>
      </div>
      <div class="prov" style="margin-top: 20px">
        <button class="btn btn-primary btn-lg" type="button" style="justify-content: center" :disabled="busy" @click="answer(true)"><Ic name="check" />Разрешить</button>
        <button class="btn btn-quiet" type="button" style="justify-content: center" :disabled="busy" @click="answer(false)">Это не я — отклонить</button>
      </div>
    </div>
    <div v-else-if="state === 'done'" class="card auth" style="border-color: rgba(95, 201, 141, .35)">
      <span class="state-art" style="width: 72px; height: 72px; margin: 0 auto; color: var(--good); box-shadow: inset 0 0 0 1.5px rgba(95, 201, 141, .5), 0 0 0 6px var(--bg), 0 0 0 7px rgba(95, 201, 141, .25)"><Ic name="check" style="width: 30px; height: 30px" /></span>
      <h1>Готово</h1>
      <p>poe2lab подключён. Вернись в приложение — публикация продолжится сама.</p>
      <p class="hint" style="margin-top: 14px">Отключить можно в <NuxtLink to="/me/settings#settings">настройках</NuxtLink>.</p>
      <div class="prov"><NuxtLink class="btn" to="/me" style="justify-content: center">В кабинет</NuxtLink></div>
    </div>
    <div v-else class="card auth">
      <h1>Запрос отклонён</h1>
      <p>Приложение не получит доступ. Если это был не ты — ничего делать не нужно, код сгорит через 10 минут.</p>
      <div class="prov"><NuxtLink class="btn" to="/" style="justify-content: center">На главную</NuxtLink></div>
    </div>
  </div>
</template>
