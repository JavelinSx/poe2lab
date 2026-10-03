# poe2lab — сайт

Каталог билдов PoE2: что это и зачем — [docs/SITE.md](../docs/SITE.md). Дизайн — `design/site/` (не в git).

```bash
npm install
node scripts/dev-game-art.mjs   # картинки игры для моковых страниц (public/game, не в git)
npm run db:migrate              # локальная база D1 (.wrangler/, не в git)
npm run dev                     # http://localhost:3100
curl -X POST http://localhost:3100/api/dev/seed   # моковые билды и отзывы в локальную базу
npm test                        # юнит-тесты: проверка пакета, запрос каталога
npm run smoke                   # весь API против запущенного dev-сервера (можно гонять повторно)
npm run typecheck               # типы страниц и API
```

**Тестовый сервер** — `npm run test-server` (или превью `poe2lab-site-test`), http://localhost:8788. Боевая сборка на
движке Cloudflare (`wrangler dev`, workerd) со своей базой в `.wrangler/test`, отдельной от `npm run dev`. Вход по
нику и примеры билдов включены флагом `TEST_SERVER`: в пустую базу примеры кладутся сами. Всё только на этом
компьютере. Без пересборки: `npm run test-server -- --no-build`; проверить API: `BASE=http://localhost:8788 npm run smoke`.

Вход для разработки — на странице `/login` по нику (только в `npm run dev`); Discord появится с приложением Discord
владельца.

API — серверные маршруты Nitro (`server/api/`) на Cloudflare Workers: D1 (SQLite, схема в `migrations/`) и R2
(пакеты билдов `builds/<id>/<версия>.json`). Общие для страниц и API справочники, типы ответов и проверка пакета —
`shared/`. Маршруты `/api/dev/*` есть только в `npm run dev`.

Страницы берут данные из API. `mock/` — примеры билдов для `/api/dev/seed` и пока что поиск игровых предметов в
редакторе описания (своего API у него ещё нет). Стили: `app/assets/css/ds.css` (дизайн-система приложения),
`site.css` (компоненты сайта из дизайна), `app.css` (то, что нужно живым страницам сверх макетов).
