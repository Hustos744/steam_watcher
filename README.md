# steam_watcher

Сервіс для:
- моніторингу знижок Steam,
- фільтрації небажаних ігор через curator blocklist,
- публікації в Telegram,
- генерації одного щоденного вертикального відео (без музики).

## Як працює

Кожен цикл:
1. Очищає старі записи в PostgreSQL (`RETENTION_DAYS`).
2. Оновлює blocklist із Steam Curator.
3. Збирає актуальні знижки Steam.
4. Публікує Telegram-пости.
5. Раз на день генерує один compilation-ролик зі знижками дня.

## Щоденне відео (без музики)

Генерується раз на день у `output/shorts`:

1. Інтро: дата + повідомлення, що це добірка знижок Steam.
2. Основна частина: для кожної гри з актуальною знижкою
   - на фоні трейлер,
   - зверху текст про знижку та ціну.
3. Аутро: нагадування `Like - Follow - Telegram`.

Параметри:
- `SHORTS_ENABLED`
- `SHORTS_OUTPUT_DIR`
- `SHORTS_PER_GAME_SECONDS`
- `SHORTS_INTRO_SECONDS`
- `SHORTS_OUTRO_SECONDS`
- `SHORTS_TIMEZONE`
- `SHORTS_CTA_TELEGRAM_URL`
- `SHORTS_FONT_PATH`

## Docker запуск

```bash
docker compose up --build -d
docker compose logs -f
```

## Основні змінні `.env`

### Core
- `POLL_INTERVAL_SECONDS`
- `POST_DELAY_SECONDS`
- `MIN_DISCOUNT_PERCENT`
- `MAX_POSTS_PER_RUN`
- `DRY_RUN`
- `LOG_LEVEL`

### Steam
- `STEAM_COUNTRY`
- `STEAM_LANGUAGE`

### Telegram
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_PARSE_MODE`
- `TELEGRAM_INCLUDE_TRAILER`
- `TELEGRAM_EXTRA_IMAGES_COUNT`
- `TELEGRAM_MAX_RETRIES`
- `USD_TO_UAH_RATE`

### Curator / blocklist
- `CURATOR_BLOCKLIST_URL`
- `CURATOR_BLOCKLIST_REFRESH_SECONDS`
- `CURATOR_BLOCKLIST_MAX_PAGES`
- `BLOCKLIST_APPIDS`

### PostgreSQL
- `DATABASE_URL`
- `RETENTION_DAYS`

### Daily video
- `SHORTS_ENABLED`
- `SHORTS_OUTPUT_DIR`
- `SHORTS_PER_GAME_SECONDS`
- `SHORTS_INTRO_SECONDS`
- `SHORTS_OUTRO_SECONDS`
- `SHORTS_TIMEZONE`
- `SHORTS_CTA_TELEGRAM_URL`
- `SHORTS_FONT_PATH`

## Примітки

- Для генерації відео потрібен `ffmpeg` (в Docker вже встановлений).
- Якщо для гри немає трейлера, ця гра пропускається у daily відео.
- У репозиторій не коміть секрети з `.env`.
