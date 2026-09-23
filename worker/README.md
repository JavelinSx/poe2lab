# Сервер отзывов (Cloudflare Worker)

Форма «✉ сообщить о нестыковке» в poe2lab отправляет отзыв сюда. Worker проверяет отзыв и пересылает его на
`poe2lab@proton.me` через [Resend](https://resend.com). Ключ Resend хранится только в Cloudflare (секрет
Worker), в приложении и в репозитории его нет.

**Защита от спама**
- Адрес получателя задан в `wrangler.toml` и из запроса не берётся. Resend без своего домена вообще шлёт только
  на почту владельца аккаунта, поэтому чужому адресу ничего не уйдёт.
- В каждом отзыве должен быть настоящий PoB-код билда PoE2: worker распаковывает его и проверяет.
- Лимиты: 2 отзыва в минуту с одного IP, 6 в минуту на всех вместе, до 100 писем в сутки (бесплатный Resend).
- Размер: сообщение до 5000 символов, до 3 скринов (PNG/JPG/WebP, каждый до 3 МБ, тип проверяется по
  содержимому). Письмо уходит только простым текстом.
- CORS-заголовков нет, а без заголовка `X-Poe2lab-Feedback` запрос отклоняется. Сайты в браузере сюда
  отправить не могут.

## Установка (один раз, ~10 минут, карта не нужна)

1. **Resend.** Зарегистрируйся на https://resend.com с адресом **poe2lab@proton.me** и подтверди почту.
   Затем *API Keys → Create API Key*: права *Sending access*. Скопируй ключ `re_…`.
2. **Cloudflare.** Зарегистрируйся на https://dash.cloudflare.com/sign-up (бесплатный план).
3. В консоли в папке проекта:

   ```bash
   cd worker
   npx wrangler login
   npx wrangler deploy
   npx wrangler secret put RESEND_API_KEY
   ```

   - `login` открывает браузер: разреши доступ.
   - `deploy` при первом запуске попросит выбрать поддомен `*.workers.dev`. В конце он печатает адрес вида
     `https://poe2lab-feedback.<поддомен>.workers.dev`.
   - `secret put` просит вставить ключ Resend. Ключ вводится в консоль и никуда не записывается.
4. Пропиши адрес с `/feedback` на конце в `RELAY_URL` в [poe2lab/feedback.py](../poe2lab/feedback.py) и
   закоммить. У игроков форма заработает после обновления.

Проверка без приложения (должно вернуть `{"error":"build code missing"}`, значит worker жив и ключ на месте):

```bash
curl -s -X POST https://poe2lab-feedback.<поддомен>.workers.dev/feedback -H "Content-Type: application/json" -H "X-Poe2lab-Feedback: 1" -d "{\"message\":\"hello\"}"
```

## Разработка

- Тесты: `node --test worker/feedback.test.mjs` (их запускает и `pytest`). Resend в тестах заменён заглушкой.
- Логи работающего worker: `npx wrangler tail`.
- Сменить адрес получателя: `FEEDBACK_TO` в `wrangler.toml`, затем `npx wrangler deploy`. Без своего домена в
  Resend адрес должен совпадать с почтой аккаунта Resend.
