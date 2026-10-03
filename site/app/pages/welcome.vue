<script setup lang="ts">
// The first visit after signing in: the nick (taken from Discord, changeable), as others will see it. Whether it is
// free is asked while it is typed (/api/nick); "Готово" saves it (PATCH /api/me).
import { nickOk } from "~~/shared/catalog";

definePageMeta({ middleware: "signed-in" });
const me = useMe();
const route = useRoute();
const toast = useToast();
const nick = ref(me.value?.nick ?? "");
const valid = computed(() => nickOk(nick.value));
const free = ref<boolean | null>(true);
let timer: ReturnType<typeof setTimeout> | undefined;
watch(nick, (n) => {
  clearTimeout(timer);
  free.value = null;
  if (!nickOk(n)) return;
  timer = setTimeout(async () => {
    try { const r = await $fetch<{ free: boolean }>("/api/nick", { query: { n } }); if (n === nick.value) free.value = r.free; } catch { free.value = true; }
  }, 250);
});
const busy = ref(false);
async function done() {
  if (!valid.value || free.value === false || !me.value) return;
  busy.value = true;
  try {
    if (nick.value !== me.value.nick) await $fetch("/api/me", { method: "PATCH", body: { nick: nick.value } });
    await loadMe();
    const n = String(route.query.next || "/me");
    await navigateTo(n.startsWith("/") && !n.startsWith("//") ? n : "/me");
  } catch (e) { toast(apiError(e), { bad: true }); } finally { busy.value = false; }
}
useHead({ title: "Как тебя называть — poe2lab" });
</script>

<template>
  <div class="center">
    <div class="card ornate auth">
      <Ava :nick="nick || '?'" :hue="me?.hue ?? 200" :src="me?.avatar ?? undefined" size="xl" style="margin: 4px auto 0" />
      <h1>Как тебя называть?</h1>
      <p>Ник виден на твоих билдах и отзывах. Поменять можно потом в настройках.</p>
      <div class="field" style="text-align: left; margin-top: 20px">
        <label for="nick">Ник</label>
        <div class="inwrap"><input id="nick" v-model.trim="nick" class="input" maxlength="24" style="height: 42px; font-size: 15px" @keydown.enter="done" />
          <span v-if="!valid" class="count-in" style="color: var(--bad)">не подходит</span>
          <span v-else-if="free === false" class="count-in" style="color: var(--bad)">занят</span>
          <span v-else-if="free === null" class="count-in faint">проверяю…</span>
          <span v-else class="count-in" style="color: var(--good); display: inline-flex; gap: 4px; align-items: center"><Ic name="check" cls="ic-s" />свободен</span></div>
        <p class="hint">Взяли из Discord. 3–24 знака: буквы, цифры, _ и -.</p>
      </div>
      <div class="field" style="text-align: left; margin-top: 14px">
        <label>Так увидят другие</label>
        <div class="aplate"><Ava :nick="nick || '?'" :hue="me?.hue ?? 200" :src="me?.avatar ?? undefined" size="l" /><div class="aplate-t"><b>{{ nick || "—" }}</b><span>0 билдов · на сайте с сегодня</span></div></div>
      </div>
      <div class="prov" style="margin-top: 18px"><button class="btn btn-primary btn-lg" type="button" style="justify-content: center" :disabled="!valid || free !== true || busy" @click="done">Готово</button></div>
      <div class="privacy"><Ic name="lock" /><span>Сохранили только ник и аватар из Discord. Почту не брали.</span></div>
    </div>
  </div>
</template>
