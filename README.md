# steam_watcher

MVP-сервіс для:
1. Відстеження знижок у Steam.
2. Автопостингу в Telegram (фото гри, стара/нова ціна, термін дії).
3. Підготовки основи під майбутню TikTok-автоматизацію.

## Як це працює

- Кожен цикл сервіс опитує `https://store.steampowered.com/api/featuredcategories`.
- Беруться `specials` з активною знижкою.
- Знижки фільтруються за `MIN_DISCOUNT_PERCENT`.
- Щоб уникати дублювань, posted deals зберігаються у SQLite (`posted_deals`).
- У Telegram відправляється `sendPhoto` з картинкою та caption.
- Якщо заданий `CURATOR_BLOCKLIST_URL`, сервіс проходить сторінки куратора, додає нові `appid` у локальну SQLite-таблицю `blocked_appids` і не публікує ці ігри.

## Швидкий старт (Docker)

1. Створіть `.env` з шаблону:

```bash
cp .env.example .env
```

2. Заповніть у `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `CURATOR_BLOCKLIST_URL` (посилання на Steam Curator, який треба блокувати)

3. Для тесту залиште `DRY_RUN=true` (пости не підуть у Telegram, але логіка відпрацює).
4. Запуск:

```bash
docker compose up --build -d
```

5. Логи:

```bash
docker compose logs -f
```

## Основні змінні `.env`

- `POLL_INTERVAL_SECONDS` - інтервал опитування Steam.
- `MIN_DISCOUNT_PERCENT` - мінімальний % знижки для публікації.
- `MAX_POSTS_PER_RUN` - обмеження кількості постів за один цикл.
- `STEAM_COUNTRY`, `STEAM_LANGUAGE` - локаль Steam API.
- `SQLITE_PATH` - шлях до sqlite у контейнері.
- `DRY_RUN` - `true/false`.
- `CURATOR_BLOCKLIST_URL` - URL сторінки Steam Curator зі списком ігор для виключення.
- `CURATOR_BLOCKLIST_REFRESH_SECONDS` - як часто оновлювати список з куратора.
- `CURATOR_BLOCKLIST_MAX_PAGES` - ліміт сторінок пагінації куратора (`0` = авто-прохід до кінця).
- `BLOCKLIST_APPIDS` - ручний список `appid` через кому (додатковий фільтр).

Рекомендація: використовуйте URL профілю куратора (наприклад `https://store.steampowered.com/curator/12345678/`), а не тільки RSS-стрічку.

## Локальний запуск без Docker

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python main.py
```

## Подальший розвиток (TikTok)

У `app/pipelines/tiktok.py` додано заглушку `TikTokPipeline`.
Наступний етап:
- збір трейлера/геймплею,
- генерація вертикального відео (9:16),
- накладення тексту зі знижкою,
- публікація через дозволений канал/API.

## Важливі нотатки

- Steam API повертає ціни в центах.
- Для деяких позицій `discount_expiration` може бути відсутнім - такі позиції пропускаються.
- Рекомендовано запускати окремого бота/канал для тестів.
