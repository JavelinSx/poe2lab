<template>
  <footer class="sf">
    <div class="wrap">
      <div class="sf-in">
        <div class="sf-b">
          <NuxtLink class="logo" to="/">poe2<span>lab</span></NuxtLink>
          <p>Билды Path of Exile 2, посчитанные движком Path of Building. Прокачка, дерево и разбор — в приложении.</p>
          <NuxtLink class="btn btn-primary" to="/#app"><Ic name="download" />Скачать poe2lab</NuxtLink>
        </div>
        <div><h4>Сайт</h4><ul>
          <li><NuxtLink to="/catalog">Каталог билдов</NuxtLink></li>
          <li><NuxtLink to="/a/MapMama">Авторы</NuxtLink></li>
          <li><NuxtLink to="/login">Войти</NuxtLink></li>
        </ul></div>
        <div><h4>Приложение</h4><ul>
          <li><a href="https://github.com/JavelinSx/poe2lab" rel="noopener"><Ic name="download" />Скачать с GitHub</a></li>
          <li><NuxtLink to="/connect"><Ic name="plug" />Подключить к сайту</NuxtLink></li>
          <li><a href="https://github.com/JavelinSx/poe2lab/commits/master" rel="noopener"><Ic name="external" />Что нового</a></li>
        </ul></div>
        <div><h4>Правила</h4><ul>
          <li><a href="#rules">Правила сайта</a></li>
          <li><a href="#privacy">Конфиденциальность</a></li>
          <li><a href="#report"><Ic name="mail" />Сообщить о проблеме</a></li>
        </ul></div>
      </div>
      <div class="sf-legal">
        <span>This product isn't affiliated with or endorsed by Grinding Gear Games in any way.</span>
        <div class="lang"><button class="is-on" type="button">RU</button><button type="button">EN</button></div>
      </div>
    </div>
  </footer>
</template>
