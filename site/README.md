# poe2lab — сайт

Каталог билдов PoE2: что это и зачем — [docs/SITE.md](../docs/SITE.md). Дизайн — `design/site/` (не в git).

```bash
npm install
node scripts/dev-game-art.mjs   # картинки игры для моковых страниц (public/game, не в git)
npm run dev                     # http://localhost:3100
```

Пока API нет, страницы берут данные из `mock/`. Стили: `app/assets/css/ds.css` (дизайн-система приложения),
`site.css` (компоненты сайта из дизайна), `app.css` (то, что нужно живым страницам сверх макетов).
