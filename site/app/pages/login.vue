<script setup lang="ts">
// Signing in: Discord (GitHub and Google later). Discord's sign-in comes with the owner's Discord application
// (docs/SITE.md, stage 2); until then, in development only, a nick signs in (/api/dev/login). After it: the welcome
// page for a new account, or back where one came from.
const route = useRoute();
const me = useMe();
const toast = useToast();
const next = computed(() => { const n = String(route.query.next || "/me"); return n.startsWith("/") && !n.startsWith("//") ? n : "/me"; });
const dev = import.meta.dev;
const nick = ref("");
const busy = ref(false);
async function devLogin() {
  busy.value = true;
  try {
    const { fresh } = await $fetch<{ fresh: boolean }>("/api/dev/login", { method: "POST", body: { nick: nick.value.trim() } });
    await loadMe();
    await navigateTo(fresh ? { path: "/welcome", query: { next: next.value } } : next.value);
  } catch (e) { toast(apiError(e), { bad: true }); } finally { busy.value = false; }
}
onMounted(() => { if (me.value) navigateTo(next.value, { replace: true }); });
useHead({ title: "Вход — poe2lab" });
</script>

<template>
  <div class="center">
    <div class="card ornate auth">
      <NuxtLink class="logo" to="/" style="justify-content: center">poe2<span>lab</span></NuxtLink>
      <h1>Вход на сайт</h1>
      <p>Чтобы публиковать билды, писать отзывы и подписываться на авторов. Смотреть билды можно и без входа.</p>
      <div class="prov">
        <button class="btn btn-discord" type="button" disabled><Ic name="chat" />Войти через Discord<small>скоро</small></button>
        <button class="btn" type="button" disabled><Ic name="link" />Войти через GitHub<small>скоро</small></button>
        <button class="btn" type="button" disabled><Ic name="person" />Войти через Google<small>скоро</small></button>
      </div>
      <form v-if="dev" class="field" style="text-align: left; margin-top: 18px" @submit.prevent="devLogin">
        <label for="dev-nick">Вход для разработки — только на этом компьютере</label>
        <div class="row" style="gap: 8px"><input id="dev-nick" v-model="nick" class="input" maxlength="24" placeholder="ник, например frostmonk" style="flex: 1" />
          <button class="btn btn-primary" type="submit" :disabled="busy || nick.trim().length < 3"><Ic name="login" />Войти</button></div>
        <p class="hint">Новый ник станет новым аккаунтом. На настоящем сайте этого входа нет.</p>
      </form>
      <div class="privacy"><Ic name="lock" /><span><b>Почту не берём.</b> Из Discord — только ник и аватар. Паролей сайт не видит и не хранит.</span></div>
      <p class="hint" style="margin-top: 14px">Входя, ты соглашаешься с <a href="#rules">правилами сайта</a>.</p>
    </div>
  </div>
</template>
