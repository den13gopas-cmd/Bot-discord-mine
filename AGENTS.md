# AGENTS.md

## О проекте

Простой Python-проект Discord-бота, который:
- запускает Flask-сервер для постоянной работы (`keep_alive.py`)
- подключается к Minecraft-серверу по RCON (`cogs/minecraft.py`)
- регистрирует slash-команды Discord через `discord.py`
- управляет ботом и статусом через `cogs/bot_management.py`

## Быстрый запуск

1. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Настроить переменные окружения в `.env` на основе `.env.example`.
3. Запустить бота:
   ```bash
   python main.py
   ```

## Основные файлы

- `main.py` — точка входа, загружает переменные окружения, настраивает бота, регистрирует коги и запускает `keep_alive`.
- `cogs/minecraft.py` — реализация команд Minecraft и RCON, опроса статуса сервера и работы со статусом.
- `cogs/bot_management.py` — команды управления ботом (`/afk`, `/setstatus`, `/setname`) и проверка прав администратора.
- `keep_alive.py` — минимальный Flask-сервер для пинга хостинга.
- `requirements.txt` — зависимости проекта.
- `README.md` — общий обзор, список команд и переменных окружения.

## Важные детали

- Проект использует `discord.py` v2+ и `discord.app_commands` для slash-команд.
- `Minecraft` cog делает RCON-запросы через `mcrcon` в отдельном потоке (`asyncio.to_thread`).
- Статусы бота обновляются из `main.py` и `cogs/bot_management.py`.
- Бот синхронизирует команды глобально, если не задан `GUILD_ID` или если `SYNC_GLOBALLY` установлен в `true`.

## Конфигурация

Переменные окружения:
- `DISCORD_TOKEN`
- `MC_SERVER_IP`
- `MC_SERVER_PORT`
- `MC_RCON_PORT`
- `MC_RCON_PASSWORD`
- `LOG_CHANNEL_ID`
- `ADMIN_ROLE_ID`
- `GUILD_ID`
- `SYNC_GLOBALLY`
- `PORT`

## Рекомендации для агента

- Не изменяй `main.py` без явной необходимости; логика и регистрация коги находятся там.
- Для новых Discord-команд добавляй их в соответствующий cog.
- При работе с Minecraft-командами соблюдай формат RCON и проверку ролей администратора.
- Если нужна документация по запуску или переменным окружения, ориентируйся на `README.md`.
