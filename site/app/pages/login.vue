<script setup lang="ts">
// Signing in: Discord (GitHub and Google later). The real button goes to /auth/discord; until the API, a mock
// account and the first visit's page.
const me = useMe();
const router = useRouter();
function discord() {
  me.value = { nick: "frostmonk", hue: 200, unread: 0, role: "user" };
  router.push("/welcome");
}
useHead({ title: "Вход — poe2lab" });
</script>

<template>
  <div class="center">
    <div class="card ornate auth">
      <NuxtLink class="logo" to="/" style="justify-content: center">poe2<span>lab</span></NuxtLink>
      <h1>Вход на сайт</h1>
      <p>Чтобы публиковать билды, писать отзывы и подписываться на авторов. Смотреть билды можно и без входа.</p>
      <div class="prov">
        <button class="btn btn-discord" type="button" @click="discord"><Ic name="chat" />Войти через Discord</button>
        <button class="btn" type="button" disabled><Ic name="link" />Войти через GitHub<small>скоро</small></button>
        <button class="btn" type="button" disabled><Ic name="person" />Войти через Google<small>скоро</small></button>
      </div>
      <div class="privacy"><Ic name="lock" /><span><b>Почту не берём.</b> Из Discord — только ник и аватар. Паролей сайт не видит и не хранит.</span></div>
      <p class="hint" style="margin-top: 14px">Входя, ты соглашаешься с <a href="#rules">правилами сайта</a>.</p>
    </div>
  </div>
</template>
