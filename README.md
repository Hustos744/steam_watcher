# steam_watcher

Автоматизований сервіс для моніторингу Steam-знижок, фільтрації небажаних ігор, публікації в Telegram і генерації вертикальних short-відео.

## Що вміє проєкт

- Моніторить знижки в Steam через `featuredcategories`.
- Відсіює ігри зі Steam Curator blocklist + ручного blocklist.
- Публікує пости в Telegram з медіа (обкладинка/трейлер/додаткові фото) і текстом про знижку.
- Працює на PostgreSQL (збереження posted deals + blocked appids).
- Автоматично чистить старі записи БД через `RETENTION_DAYS`.
- Генерує вертикальні шорти (TikTok / Reels / Shorts) через `ffmpeg`.
- Підтримує музичний пайплайн:
  - авто-довантаження популярних royalty-free треків;
  - ранковий Telegram music curator (3 варіанти, "ще", вибір кнопкою, ручне завантаження треку в чат).

## Архітектура

- `app/steam.py`: Steam API клієнт (deals + media).
- `app/curator_blocklist.py`: синк appid зі Steam Curator.
- `app/repository.py`: PostgreSQL репозиторій.
- `app/service.py`: основна бізнес-логіка одного циклу.
- `app/telegram_client.py`: відправка постів у Telegram.
- `app/post_design.py`: шаблон/дизайн тексту поста.
- `app/pipelines/tiktok.py`: генерація short-відео.
- `app/pipelines/music_provider.py`: провайдери музики (`jamendo`, `pixabay`).
- `app/pipelines/music_downloader.py`: авто-довантаження треків у `assets/music`.
- `app/pipelines/music_curator_bot.py`: Telegram-бот для ручного/ранкового відбору музики.
- `main.py`: точка входу, запуск циклів і фонових потоків.

## Потік роботи (1 цикл)

1. Очищення старих записів у PostgreSQL (`RETENTION_DAYS`).
2. Оновлення blocklist з куратора + merge з БД і ручним blocklist.
3. Отримання Steam deals, фільтрація.
4. Публікація в Telegram (з retry та захистом від падінь).
5. Генерація short-відео (якщо увімкнено).
6. Пауза між постами (`POST_DELAY_SECONDS`) для зменшення 429.

## Запуск через Docker

1. Створи `.env`:

```bash
cp .env.example .env
```

2. Заповни ключові змінні (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL`, тощо).

3. Запуск:

```bash
docker compose up --build -d
```

4. Логи:

```bash
docker compose logs -f
```

## Основні директорії

- `assets/music` - бібліотека музики для short-відео.
- `output/shorts` - згенеровані шорти.

## Налаштування `.env`

### Core

- `POLL_INTERVAL_SECONDS` - інтервал скану Steam.
- `POST_DELAY_SECONDS` - пауза між постами в одному скані.
- `MIN_DISCOUNT_PERCENT` - мінімальна знижка для публікації.
- `MAX_POSTS_PER_RUN` - ліміт постів за цикл.
- `DRY_RUN` - тестовий режим без реальних постів.
- `LOG_LEVEL` - рівень логування.

### Steam

- `STEAM_COUNTRY`
- `STEAM_LANGUAGE`

### Telegram posting

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
- `BLOCKLIST_APPIDS` - ручні appid через кому.

### PostgreSQL

- `DATABASE_URL` - наприклад `postgresql://steam:steam@postgres:5432/steam_watcher`
- `RETENTION_DAYS` - автоочистка старих записів.

### Shorts generation

- `SHORTS_ENABLED`
- `SHORTS_DURATION_SECONDS` (рекомендовано 15)
- `SHORTS_OUTPUT_DIR`
- `SHORTS_MUSIC_DIR`
- `SHORTS_CTA_TELEGRAM_URL`
- `SHORTS_FONT_PATH`

### Music provider / auto fetch

- `MUSIC_PROVIDER` - `jamendo` або `pixabay`.
- `JAMENDO_CLIENT_ID` - для `MUSIC_PROVIDER=jamendo`.
- `POPULAR_MUSIC_API_KEY` - для `MUSIC_PROVIDER=pixabay`.
- `MUSIC_AUTOFETCH_ENABLED`
- `POPULAR_MUSIC_TARGET_COUNT`
- `POPULAR_MUSIC_REFRESH_HOURS`

### Telegram music curator bot

- `MUSIC_CURATOR_ENABLED`
- `MUSIC_CURATOR_CHAT_ID` - ваш приватний chat id.
- `MUSIC_CURATOR_HOUR`
- `MUSIC_CURATOR_MINUTE`
- `MUSIC_CURATOR_TIMEZONE`
- `MUSIC_CURATOR_BATCH_SIZE` - скільки треків у порції (зазвичай 3).

## Як працює Music Curator (Telegram)

Якщо `MUSIC_CURATOR_ENABLED=true`, бот:

- зранку надсилає порцію популярних треків (кнопки `Use` і `More options`);
- по `More options` надсилає наступні варіанти;
- по вибору треку зберігає його в `assets/music` і ставить preferred;
- приймає твій власний трек (`audio`/`document`) і ставить його preferred.

Команди:

- `/music` - отримати добірку зараз;
- `/more` - ще варіанти.

## Shorts: що генерується

- Вертикальне відео 1080x1920.
- Тривалість `SHORTS_DURATION_SECONDS`.
- Фон: трейлер гри.
- Оверлей: назва, знижка, стара/нова ціна.
- Фінальний CTA-блок (like/follow/telegram).
- Музика: preferred трек (якщо вибрано), інакше випадковий трек із `assets/music`.

## Важливі примітки

- Telegram API може повертати `429`; у проєкті є retry + throttle, але при високому навантаженні варто підвищувати `POST_DELAY_SECONDS`.
- Для генерації шортів потрібен `ffmpeg` (в Docker-образі вже встановлено).
- Якщо немає трейлера/музики, генерація шорту для конкретної гри пропускається.
- Не коміть секрети (`.env` вже в `.gitignore`).

## Рекомендований перший запуск

1. Запустити з `DRY_RUN=true`.
2. Перевірити логи.
3. Перемкнути на `DRY_RUN=false`.
4. Увімкнути `SHORTS_ENABLED=true` після перевірки постингу.
5. Налаштувати `MUSIC_PROVIDER` + ключі, потім `MUSIC_CURATOR_ENABLED=true`.
