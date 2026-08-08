import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import keep_alive
from mcstatus import JavaServer

from cogs.bot_management import BotManagement

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("minecraft-discord-bot")


def get_env_value(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()
    return value or default


def get_env_int(key: str, default: int | None = None) -> int | None:
    value = get_env_value(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("Неверное значение для %s: %s", key, value)
        return default


DISCORD_TOKEN = get_env_value("DISCORD_TOKEN")
MC_SERVER_IP = get_env_value("MC_SERVER_IP", "127.0.0.1")
MC_SERVER_PORT = get_env_int("MC_SERVER_PORT", 25565) or 25565
MC_RCON_PORT = get_env_int("MC_RCON_PORT", 25575) or 25575
MC_RCON_PASSWORD = get_env_value("MC_RCON_PASSWORD", "")
MC_AUTH_PLAYER = get_env_value("MC_AUTH_PLAYER")
MC_CAMERA_PLAYER = get_env_value("MC_CAMERA_PLAYER")
MC_CLIENT_USERNAME = get_env_value("MC_CLIENT_USERNAME")
MC_CLIENT_PASSWORD = get_env_value("MC_CLIENT_PASSWORD")
MC_CLIENT_VERSION = get_env_value("MC_CLIENT_VERSION", "1.21.8")
MC_CLIENT_REGISTER_PASSWORD = get_env_value("MC_CLIENT_REGISTER_PASSWORD")
MC_CLIENT_LOGIN_PASSWORD = get_env_value("MC_CLIENT_LOGIN_PASSWORD")
LOG_CHANNEL_ID = get_env_int("LOG_CHANNEL_ID")
ADMIN_ROLE_ID = get_env_int("ADMIN_ROLE_ID")
GUILD_ID = get_env_int("GUILD_ID")
SYNC_GLOBALLY = get_env_value("SYNC_GLOBALLY", "false").lower() in {"1", "true", "yes", "on"}

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in environment variables.")

if not MC_SERVER_IP or MC_SERVER_IP == "your.minecraft.server.ip":
    logger.warning("MC_SERVER_IP не задан или стоит заглушка; Minecraft-команды будут недоступны до настройки.")

if not MC_RCON_PASSWORD:
    logger.warning("MC_RCON_PASSWORD не задан; команды RCON будут недоступны до настройки.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

server_down_sent = False


status_task: asyncio.Task[None] | None = None

@bot.event
async def setup_hook() -> None:
    from cogs.minecraft import Minecraft

    cog = Minecraft(
        mc_ip=MC_SERVER_IP,
        mc_port=MC_SERVER_PORT,
        rcon_port=MC_RCON_PORT,
        rcon_password=MC_RCON_PASSWORD,
        admin_role_id=ADMIN_ROLE_ID,
        log_channel_id=LOG_CHANNEL_ID,
        auth_player=MC_AUTH_PLAYER,
        camera_player=MC_CAMERA_PLAYER,
    )
    await bot.add_cog(cog)

    management_cog = BotManagement(
        bot=bot,
        bot_name="DarkAgencyBOT",
        default_status="AFK | Управление через Discord",
        admin_role_id=ADMIN_ROLE_ID,
    )
    await bot.add_cog(management_cog)

    global status_task
    status_task = asyncio.create_task(MinecraftStatusTask(bot).task_loop())


class MinecraftStatusTask:
    def __init__(self, bot_client: commands.Bot):
        self.bot = bot_client
        self.server = JavaServer(MC_SERVER_IP, MC_SERVER_PORT)
        self.server_down = False

    async def get_log_channel(self) -> discord.TextChannel | None:
        if LOG_CHANNEL_ID is None:
            return None
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
            except Exception as exc:
                logger.warning("Не удалось получить лог-канал: %s", exc)
                return None
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def update_presence(self, description: str) -> None:
        activity = discord.Game(name=description)
        try:
            await self.bot.change_presence(status=discord.Status.online, activity=activity)
            logger.info("Обновлен статус бота: %s", description)
        except Exception as exc:
            logger.warning("Не удалось обновить статус бота: %s", exc)

    async def query_server(self) -> dict:
        status = await self.server.async_status()
        return {
            "players_online": status.players.online,
            "players_max": status.players.max,
            "version": status.version.name,
            "latency": round(status.latency),
            "motd": status.description if hasattr(status, "description") else None,
        }

    async def task_loop(self) -> None:
        await self.bot.wait_until_ready()
        log_channel = await self.get_log_channel()

        while not self.bot.is_closed():
            try:
                stats = await self.query_server()
                description = f"Игроков: {stats['players_online']}/{stats['players_max']} | IP: {MC_SERVER_IP}"
                await self.update_presence(description)

                if self.server_down:
                    self.server_down = False
                    logger.info("Сервер снова доступен.")

            except Exception as exc:
                logger.warning("Ошибка запроса статуса Minecraft: %s", exc)
                if not self.server_down:
                    self.server_down = True
                    if log_channel is not None:
                        embed = discord.Embed(
                            title="Внимание: Minecraft сервер недоступен",
                            description=f"Не удалось получить статус сервера `{MC_SERVER_IP}:{MC_SERVER_PORT}`.",
                            color=discord.Color.orange(),
                        )
                        embed.add_field(name="Ошибка", value=str(exc), inline=False)
                        try:
                            await log_channel.send(embed=embed)
                        except Exception as exc_send:
                            logger.warning("Не удалось отправить уведомление о падении сервера: %s", exc_send)

            await asyncio.sleep(60)


@bot.event
async def on_ready() -> None:
    logger.info("Бот авторизован как: %s", bot.user)
    try:
        if GUILD_ID and not SYNC_GLOBALLY:
            target_guild = discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync(guild=target_guild)
            logger.info("Синхронизированы команды приложения для гильдии %s: %s", GUILD_ID, len(synced))
        else:
            synced = await bot.tree.sync()
            logger.info("Синхронизированы команды приложения глобально: %s", len(synced))
    except Exception as exc:
        logger.warning("Не удалось синхронизировать команды приложения: %s", exc)


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    logger.exception("Ошибка команды %s", interaction.command.name if interaction.command else "unknown")
    embed = discord.Embed(title="Ошибка команды", description=str(error), color=discord.Color.red())

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as send_exc:
        logger.warning("Не удалось отправить сообщение об ошибке команды: %s", send_exc)


async def main() -> None:
    keep_alive.start()
    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        if status_task is not None:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass

        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Завершение работы бота.")
