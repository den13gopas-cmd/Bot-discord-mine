# Discord Bot for Minecraft Server

Простой проект Discord-бота на Python с интеграцией Minecraft-сервера через RCON и проверкой статуса сервера.

## Требования

- Python 3.11+
- Discord приложение с ботом и токеном
- Доступ к Minecraft серверу с включенным RCON
- Replit или другой хостинг, поддерживающий Flask и постоянную работу

## Установка

1. Скопируйте `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
2. Заполните значения в `.env`.
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите Discord-бота:
   ```bash
   python main.py
   ```
5. Запустите Minecraft-бота отдельно:
   ```bash
   npm run minecraft
   ```

## Команды Discord

- `/status` — показывает текущий статус сервера.
- `/cmd <команда>` — выполняет произвольную консольную команду через RCON (только админы).
- `/reg <пароль> <подтверждение>` — регистрирует Minecraft-аккаунт от имени `MC_AUTH_PLAYER`.
- `/log <пароль>` — авторизует Minecraft-аккаунт от имени `MC_AUTH_PLAYER`.
- `/kick <игрок> [причина]` — кикает игрока.
- `/ban <игрок> [причина]` — банит игрока.
- `/whitelist <add/remove> <игрок>` — управляет белым списком.

## Функции

- Flask-сервер на `/` для работы 24/7.
- Фоновая задача, опрашивающая Minecraft-сервер каждые 60 секунд.
- Автообновление статуса бота с информацией об игроках.
- Отправка уведомления в лог-канал при недоступности сервера.

## Переменные окружения

- `DISCORD_TOKEN`
- `MC_SERVER_IP`
- `MC_SERVER_PORT`
- `MC_RCON_PORT`
- `MC_RCON_PASSWORD`
- `MC_AUTH_PLAYER` — ник Minecraft-игрока, от имени которого будут выполняться команды `/reg` и `/log`
- `MC_CAMERA_PLAYER` — ник Minecraft-игрока, чья камера будет поворачиваться каждые 10 секунд
- `MC_CLIENT_USERNAME` — ник/логин Minecraft-клиента Mineflayer
- `MC_CLIENT_PASSWORD` — пароль Microsoft-аккаунта, если нужен авторизованный вход
- `MC_CLIENT_VERSION` — версия клиента, по умолчанию `1.21.8`
- `MC_CLIENT_REGISTER_PASSWORD` — пароль для регистрации в игре
- `MC_CLIENT_LOGIN_PASSWORD` — пароль для логина в игре
- `LOG_CHANNEL_ID`
- `ADMIN_ROLE_ID`
- `GUILD_ID` — ID Discord-сервера, на котором будут создаваться slash-команды
- `SYNC_GLOBALLY` — `true/false`, если нужно синхронизировать команды глобально
- `PORT` — порт веб-сервера (по умолчанию 8080)
