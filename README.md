# steam_watcher

MVP-сервіс для:
1. Відстеження знижок у Steam.
2. Автопостингу в Telegram (фото гри, стара/нова ціна, термін дії).
3. Підготовки основи під майбутню TikTok-автоматизацію.

## Як це працює

- Кожен цикл сервіс опитує `https://store.steampowered.com/api/featuredcategories`.
- Беруться `specials` з активною знижкою.
- Знижки фільтруються за `MIN_DISCOUNT_PERCENT`.
- Щоб уникати дублювань, posted deals зберігаються у PostgreSQL (`posted_deals`).
- У Telegram відправляється основний пост (трейлер або фото) з caption + кнопками, і додаткові фото альбомом.
- Якщо заданий `CURATOR_BLOCKLIST_URL`, сервіс проходить сторінки куратора, додає нові `appid` у PostgreSQL-таблицю `blocked_appids` і не публікує ці ігри.
- Автоочистка даних: записи старше `RETENTION_DAYS` видаляються автоматично на кожному циклі.

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
- `POST_DELAY_SECONDS` - пауза між постами в межах одного скану (зменшує шанс 429).
- `MIN_DISCOUNT_PERCENT` - мінімальний % знижки для публікації.
- `MAX_POSTS_PER_RUN` - обмеження кількості постів за один цикл.
- `STEAM_COUNTRY`, `STEAM_LANGUAGE` - локаль Steam API.
- `DATABASE_URL` - рядок підключення до PostgreSQL.
- `RETENTION_DAYS` - через скільки днів автоматично видаляти старі записи.
- `DRY_RUN` - `true/false`.
- `CURATOR_BLOCKLIST_URL` - URL сторінки Steam Curator зі списком ігор для виключення.
- `CURATOR_BLOCKLIST_REFRESH_SECONDS` - як часто оновлювати список з куратора.
- `CURATOR_BLOCKLIST_MAX_PAGES` - ліміт сторінок пагінації куратора (`0` = авто-прохід до кінця).
- `BLOCKLIST_APPIDS` - ручний список `appid` через кому (додатковий фільтр).
- `USD_TO_UAH_RATE` - курс для відображення ціни у гривні в Telegram-постах.
- `TELEGRAM_INCLUDE_TRAILER` - якщо `true`, пост намагається відправити трейлер (якщо є).
- `TELEGRAM_EXTRA_IMAGES_COUNT` - скільки додаткових фото відправляти після основного поста.
- `TELEGRAM_MAX_RETRIES` - кількість retry при 429/тимчасових помилках Telegram API.

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
