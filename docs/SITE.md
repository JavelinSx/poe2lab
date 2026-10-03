# Сайт poe2lab — план

Каталог билдов PoE2 с аккаунтами билдостроителей, оценками и отзывами. Сайт — лёгкая витрина:
- на странице билда скиллы и камни, снаряжение, DPS и защита коротко, небольшое описание автора с иконками;
- всё подробное (прокачка, дерево, разбор, крафт, советы) — в приложении, куда ведёт кнопка «Открыть в poe2lab».

**Сайт ничего не считает:** билд публикуется из приложения готовым пакетом.

Дизайн: `design/site/` (Claude Design; папка не в git).
- `src/*.dc.html` — макеты каждого экрана и их телефонные версии;
- `site.css` — компоненты поверх `ds.css` приложения;
- `sprite.html` — все иконки;
- `src/Notes.dc.html` — заметки по взаимодействию.

## Стек

- **Nuxt (Vue 3)** в папке `site/` этого репозитория. Почему не отдельный репозиторий: общая дизайн-система с
  приложением (`ds.css`) и общий формат пакета публикации.
- **Хостинг — Cloudflare**, бесплатные лимиты:
  - Workers: 100 000 запросов в день, 10 мс процессора на запрос;
  - D1: 5 ГБ, 5 млн чтений и 100 тыс. записей в день;
  - R2: 10 ГБ;
  - Turnstile — защита от ботов.
- **Сборка — SPA + API.** Страницы отдаются статикой, данные берутся из API (Nitro server routes на Workers,
  пресет `cloudflare_module`, привязки D1 и R2). Рендер Vue на сервере в 10 мс процессора бесплатного плана может не
  уложиться, а запрос к D1 и JSON укладываются.
- **Превью для Discord и Telegram.** Для ботов (Discordbot, TelegramBot…) по ссылке `/b/<id>` сервер отдаёт короткий
  HTML с OG-тегами: название, класс, DPS, оценка. Людям отдаётся обычная страница.
- **Локально:** `npm run dev` в `site/`. Пока нет API — моковые данные из `site/mock/`.

## Данные (D1)

| Таблица | Поля |
|---|---|
| `users` | id, discord_id, nick, avatar, bio, links (json), role (user/mod/owner), banned_at, created_at |
| `sessions` | id (токен в cookie, httpOnly), user_id, expires_at |
| `app_tokens` | id, user_id, token_hash, name («poe2lab на ПК»), created_at, last_used_at |
| `device_codes` | code (6 знаков), device_id, user_id (после подтверждения), expires_at (10 мин) |
| `builds` | id (короткий), author_id, app_key (ключ билда в приложении: повторная публикация обновляет тот же), title, class, ascendancy, main_skill, damage_type, weapon, tags (json), patch, description, package_key (R2), dps, life, es, rating_avg, rating_n, views, opens, status (published/hidden/removed), created_at, updated_at |
| `reviews` | id, build_id, user_id (один на пару), rating 1–5, criteria (json: урон, живучесть, бюджет, лёгкость), text, char_class, char_level, helpful_n, reply (ответ автора), reply_at, status, created_at, updated_at |
| `review_votes` | review_id, user_id |
| `favorites` | user_id, build_id |
| `follows` | user_id, author_id |
| `notifications` | id, user_id, kind (review/reply/patch), build_id, review_id, read_at, created_at |
| `reports` | id, reporter_id, target (build/review/user), target_id, reason, status, created_at |

Пакет билда целиком лежит в R2 (`builds/<id>/<version>.json`). В D1 — только то, по чему ищут и сортируют.

## Пакет публикации (из приложения)

```
{ v: 1, app: "poe2lab 0.x", patch: "0.5.5", key, title, tags,
  class, ascendancy, mainSkill, damageType, weapon,
  numbers: { dps, dpsSkill, life, es, res: {fire, cold, lightning, chaos}, defence: {kind, value}, deflect },
  description,                        // текст автора с токенами [[gem:…]] (до ~1500 знаков)
  skills: [{ actives, supports: [{name, level, quality}], role, spirit, note }],
  gear: [{ slot, name, base, rarity, level, implicits, explicits, runes, props }],
  cards: { "gem:Ice Strike": {...}, ... },   // всё для подсказок того, что упомянуто
  pob: "<код PoB>" }
```

Лимит — около 200 КБ. Сервер проверяет форму, размер, токены и длину описания.

## Вход и связь с приложением

- **Сайт:** вход через Discord (OAuth2, scope `identify`, без почты), сессия в cookie. Ник выбирается при первом
  входе.
- **Приложение — код устройства:**
  1. poe2lab просит код и показывает его.
  2. Игрок открывает `/connect`, видит тот же код, жмёт «Подтвердить».
  3. Приложение получает токен и хранит его в своих настройках (APPDATA, рядом с ключами).
- **«Открыть в poe2lab»:** ссылка `poe2lab://build/<id>`. Протокол регистрирует приложение. Если через 2 с страница
  ещё видна — окно со ссылкой на скачивание.

## API (Nitro, `site/server/api`)

- **Вход:**
  - `GET /auth/discord`, `GET /auth/discord/callback`, `POST /api/logout`, `GET /api/me`;
  - `POST /api/device/start` (приложение), `POST /api/device/confirm` (сайт), `POST /api/device/token` (приложение).
- **Билды:**
  - `GET /api/builds` — фильтры, сортировка, курсор, 24 на страницу; `GET /api/builds/:id`;
  - `POST /api/builds` — публикация из приложения по токену; повторная с тем же `key` обновляет билд;
  - `PATCH /api/builds/:id` — на сайте: название, теги, обложка, описание;
  - `POST /api/builds/:id/state` — `published` / `hidden` / `removed` (удаление насовсем);
  - `GET /api/builds/:id/pob` — код PoB по кнопке; `GET /api/me/builds` — кабинет.
- **Поиск:** `GET /api/search/suggest?q=` — теги, скиллы, билды, авторы.
- **Отзывы:**
  - `GET /api/builds/:id/reviews`, `PUT /api/builds/:id/review`;
  - `POST /api/reviews/:id/helpful`, `POST /api/reviews/:id/reply`.
- **Прочее:**
  - `POST|DELETE /api/favorites/:id` (список — `GET /api/builds?fav=1`), `POST|DELETE /api/follows/:nick`;
  - `GET /api/notifications`, `POST /api/notifications/read` — видны те виды, что включены в настройках;
  - `GET /api/home`, `GET /api/authors/:nick`, `GET /api/nick?n=` (ник свободен?);
  - `GET /api/me/settings`, `PATCH /api/me`, `DELETE /api/me/apps/:id`, `DELETE /api/me` (аккаунт насовсем);
  - `POST /api/reports`; `GET /api/mod/reports`, `POST /api/mod/action` — только модератор.

Защита:
- Turnstile на входе, отзывах и жалобах;
- лимиты частоты по пользователю и адресу;
- проверка `Origin` на изменениях;
- всё, что пишут люди, выводится только как текст.

## Страницы ↔ макеты

| Путь | Макет | Что |
|---|---|---|
| `/` | Main | поиск, классы, подборки, лучшие авторы, приложение |
| `/catalog` | Catalog (+ filters-phone) | фильтры в адресе, сетка или список, «показать ещё» |
| `/b/:id` | Build | шапка, цифры коротко, описание, скиллы, снаряжение, автор, отзывы |
| `/a/:nick` | Author | профиль, билды, отзывы на билды |
| `/me` | Cabinet | мои билды, статистика |
| `/me/b/:id` | BuildEdit | название, теги, обложка, описание с иконками (@-поиск, панель) |
| `/me/settings` | Account | уведомления, настройки |
| `/login`, `/welcome` | Login, Welcome | вход через Discord, выбор ника |
| `/connect` | Connect | подтверждение кода приложения |
| `/mod` | Moderation | жалобы |
| — | States | 404, снятый билд, ошибка, нет связи, пустые списки, диалоги |
| — (в приложении) | Publish, PublishFlow | окно «Опубликовать» в poe2lab |

## Картинки и тексты игры

- **Иконки камней, вещей и пассивок.** На сайте нужны ссылки на CDN игры; правила адресов ещё надо найти. Пока в
  разработке иконки берутся из кэша приложения в `site/public/game/` — папка не в git, в репозиторий арт GGG не
  кладём. Где картинки нет — рамка и глиф типа урона (`.gph`), как в макете.
- **Тексты для подсказок** приходят в пакете билда (`cards`): ровно то, что упомянуто в билде.

## Этапы

0. **План и вёрстка** — этот файл; `site/` на Nuxt; оболочка (шапка, подвал, нижняя панель телефона);
   страницы главная, каталог, билд, автор, кабинет, правка, вход, подключение, состояния на моковых данных; сверка
   с макетами снимками.
1. **API и база:** схема D1 (миграции), билды, поиск, фильтры; локально `wrangler` / `nitro-cloudflare-dev`.
   Готово, страницы работают от API; проверки — `npm test`, `npm run smoke`, `npm run typecheck`.
2. **Вход:** Discord OAuth, сессии, выбор ника. Нужно приложение Discord: client id и secret заводит владелец.
3. **Приложение:** пакет публикации (`poe2lab/publish.py`), код устройства, окно «Опубликовать», ссылка
   `poe2lab://`.
4. **Отзывы и оценки**, «полезно», ответы автора, избранное, подписки, уведомления. Готово (вместе с этапом 1).
5. **Модерация:** жалобы, скрытие, блокировка; правила сайта и конфиденциальность.
6. **Выкладка** на Cloudflare с аккаунта владельца, домен — только с его «да».

## Открытые вопросы

- Адреса картинок игры на CDN, правила GGG для фан-сайтов.
- Домен: покупает и привязывает владелец.
- Discord: имя приложения, адрес возврата.
