<script setup lang="ts">
// The first visit after signing in: the nick (taken from Discord, changeable), as others will see it.
const me = useMe();
const nick = ref(me.value?.nick ?? "");
const valid = computed(() => /^[A-Za-zА-Яа-яЁё0-9_-]{3,24}$/.test(nick.value));
const taken = computed(() => ["MapMama", "Inverno", "admin"].map((x) => x.toLowerCase()).includes(nick.value.toLowerCase()));
const router = useRouter();
function done() {
  if (!valid.value || taken.value || !me.value) return;
  me.value = { ...me.value, nick: nick.value };
  router.push("/me");
}
useHead({ title: "Как тебя называть — poe2lab" });
</script>

<template>
  <div class="center">
    <div class="card ornate auth">
      <Ava :nick="nick || '?'" :hue="me?.hue ?? 200" size="xl" style="margin: 4px auto 0" />
      <h1>Как тебя называть?</h1>
      <p>Ник виден на твоих билдах и отзывах. Поменять можно потом в настройках.</p>
      <div class="field" style="text-align: left; margin-top: 20px">
        <label for="nick">Ник</label>
        <div class="inwrap"><input id="nick" v-model.trim="nick" class="input" maxlength="24" style="height: 42px; font-size: 15px" @keydown.enter="done" />
          <span v-if="!valid" class="count-in" style="color: var(--bad)">не подходит</span>
          <span v-else-if="taken" class="count-in" style="color: var(--bad)">занят</span>
          <span v-else class="count-in" style="color: var(--good); display: inline-flex; gap: 4px; align-items: center"><Ic name="check" cls="ic-s" />свободен</span></div>
        <p class="hint">Взяли из Discord. 3–24 знака: буквы, цифры, _ и -.</p>
      </div>
      <div class="field" style="text-align: left; margin-top: 14px">
        <label>Так увидят другие</label>
        <div class="aplate"><Ava :nick="nick || '?'" :hue="me?.hue ?? 200" size="l" /><div class="aplate-t"><b>{{ nick || "—" }}</b><span>0 билдов · на сайте с сегодня</span></div></div>
      </div>
      <div class="prov" style="margin-top: 18px"><button class="btn btn-primary btn-lg" type="button" style="justify-content: center" :disabled="!valid || taken" @click="done">Готово</button></div>
      <div class="privacy"><Ic name="lock" /><span>Сохранили только ник и аватар из Discord. Почту не брали.</span></div>
    </div>
  </div>
</template>
