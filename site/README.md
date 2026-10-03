# poe2lab — сайт

Каталог билдов PoE2: что это и зачем — [docs/SITE.md](../docs/SITE.md). Дизайн — `design/site/` (не в git).

```bash
npm install
node scripts/dev-game-art.mjs   # картинки игры для моковых страниц (public/game, не в git)
npm run db:migrate              # локальная база D1 (.wrangler/, не в git)
npm run dev                     # http://localhost:3100
curl -X POST http://localhost:3100/api/dev/seed   # моковые билды и отзывы в локальную базу
npm test                        # юнит-тесты: проверка пакета, запрос каталога
npm run smoke                   # весь API против запущенного dev-сервера
```

API — серверные маршруты Nitro (`server/api/`) на Cloudflare Workers: D1 (SQLite, схема в `migrations/`) и R2
(пакеты билдов `builds/<id>/<версия>.json`). Общие для страниц и API справочники и проверка пакета — `shared/`.
Маршруты `/api/dev/*` есть только в `npm run dev`.

Пока страницы берут данные из `mock/`. Стили: `app/assets/css/ds.css` (дизайн-система приложения),
`site.css` (компоненты сайта из дизайна), `app.css` (то, что нужно живым страницам сверх макетов).
