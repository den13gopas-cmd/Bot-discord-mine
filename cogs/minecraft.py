import asyncio
import logging
import os
import socket
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from mcrcon import MCRcon, MCRconException
from mcstatus import JavaServer

load_dotenv()

logger = logging.getLogger("minecraft-cog")


def get_int_env(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Minecraft(commands.Cog):
    def __init__(
        self,
        mc_ip: str,
        mc_port: int,
        rcon_port: int,
        rcon_password: str,
        admin_role_id: Optional[int],
        log_channel_id: Optional[int],
        auth_player: Optional[str],
        camera_player: Optional[str],
    ):
        self.mc_ip = mc_ip
        self.mc_port = mc_port
        self.rcon_port = rcon_port
        self.rcon_password = rcon_password
        self.admin_role_id = admin_role_id
        self.log_channel_id = log_channel_id
        self.auth_player = auth_player
        self.camera_player = camera_player
        self.server = JavaServer(self.mc_ip, self.mc_port)
        self.camera_task: asyncio.Task[None] | None = None
        self.camera_yaw = 0.0

    async def cog_load(self) -> None:
        logger.info("Cog Minecraft загружен.")
        if self.camera_player:
            self.camera_task = asyncio.create_task(self.camera_loop())

    async def cog_unload(self) -> None:
        if self.camera_task:
            self.camera_task.cancel()
            try:
                await self.camera_task
            except asyncio.CancelledError:
                pass

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        if self.admin_role_id is None:
            return True
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        return any(role.id == self.admin_role_id for role in interaction.user.roles)

    async def rcon_command(self, command: str) -> str:
        def execute() -> str:
            with MCRcon(self.mc_ip, self.rcon_password, port=self.rcon_port, timeout=10) as mcr:
                return mcr.command(command)

        try:
            result = await asyncio.to_thread(execute)
            return result or "(пустой ответ)"
        except (MCRconException, socket.timeout, ConnectionRefusedError, OSError) as exc:
            logger.error("Ошибка RCON: %s", exc)
            raise RuntimeError("Не удалось отправить RCON-команду. Проверьте доступность сервера и пароль RCON.") from exc

    async def query_status(self) -> dict:
        try:
            status = await self.server.async_status()
            return {
                "online": True,
                "players_online": status.players.online,
                "players_max": status.players.max,
                "version": status.version.name,
                "latency": round(status.latency),
            }
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            logger.warning("Ошибка при запросе статуса сервера: %s", exc)
            return {"online": False}

    async def execute_as_player(self, player: str, command: str) -> str:
        if not player:
            raise RuntimeError("MC_AUTH_PLAYER не настроен.")
        return await self.rcon_command(f"execute as {player} run {command}")

    def build_embed(self, title: str, description: str, color: discord.Color) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=f"Сервер: {self.mc_ip}:{self.mc_port}")
        return embed

    @app_commands.command(name="status", description="Показать статус Minecraft-сервера.")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        status = await self.query_status()
        if not status.get("online"):
            embed = self.build_embed(
                "Сервер недоступен",
                "Не удалось получить статус Minecraft-сервера. Попробуйте позже.",
                discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        embed = self.build_embed(
            "Статус Minecraft-сервера",
            f"**Версия:** {status['version']}\n"
            f"**Игроков:** {status['players_online']}/{status['players_max']}\n"
            f"**Пинг:** {status['latency']} ms",
            discord.Color.green(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="cmd", description="Отправить консольную команду на сервер через RCON.")
    @app_commands.describe(command="Команда Minecraft для отправки в консоль.")
    async def cmd(self, interaction: discord.Interaction, command: str) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        await interaction.response.defer(ephemeral=True)
        try:
            response = await self.rcon_command(command)
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed("RCON-команда выполнена", f"**Запрос:** `{command}`\n**Ответ:** {response}", discord.Color.blue())
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="reg", description="Регистрация аккаунта на сервере.")
    @app_commands.describe(password="Пароль", confirm_password="Подтвердите пароль")
    async def reg(
        self,
        interaction: discord.Interaction,
        password: str,
        confirm_password: str,
    ) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        if self.auth_player is None:
            raise app_commands.AppCommandError("MC_AUTH_PLAYER не настроен.")

        if password != confirm_password:
            raise app_commands.AppCommandError("Пароли не совпадают.")

        await interaction.response.defer(ephemeral=True)
        try:
            response = await self.execute_as_player(self.auth_player, f"reg {password} {confirm_password}")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка регистрации", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed(
            "Регистрация выполнена",
            f"**Игрок:** {self.auth_player}\n**Ответ сервера:** {response}",
            discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="log", description="Авторизоваться на сервере.")
    @app_commands.describe(password="Пароль")
    async def log(
        self,
        interaction: discord.Interaction,
        password: str,
    ) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        if self.auth_player is None:
            raise app_commands.AppCommandError("MC_AUTH_PLAYER не настроен.")

        await interaction.response.defer(ephemeral=True)
        try:
            response = await self.execute_as_player(self.auth_player, f"login {password}")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка авторизации", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed(
            "Авторизация выполнена",
            f"**Игрок:** {self.auth_player}\n**Ответ сервера:** {response}",
            discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="players", description="Показать список игроков онлайн.")
    async def players(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            response = await self.rcon_command("list")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed)
            return

        embed = self.build_embed("Список игроков", response, discord.Color.teal())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="plugins", description="Показать установленные плагины.")
    async def plugins(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            response = await self.rcon_command("plugins")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed)
            return

        embed = self.build_embed("Плагины сервера", response, discord.Color.purple())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="inventory", description="Показать инвентарь игрока.")
    @app_commands.describe(player="Имя игрока")
    async def inventory(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer()
        try:
            response = await self.rcon_command(f"data get entity {player} Inventory")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed)
            return

        embed = self.build_embed(f"Инвентарь {player}", response, discord.Color.gold())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="say", description="Отправить сообщение всем игрокам в игре.")
    @app_commands.describe(message="Текст сообщения")
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        await interaction.response.defer(ephemeral=True)
        try:
            response = await self.rcon_command(f"say {message}")
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed("Сообщение отправлено", response, discord.Color.blurple())
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="kick", description="Кикнуть игрока с сервера Minecraft.")
    @app_commands.describe(player="Имя игрока", reason="Причина кика")
    async def kick(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        await interaction.response.defer(ephemeral=True)
        command = f"kick {player} {reason or 'Вы были кикнуты администратором.'}"
        try:
            response = await self.rcon_command(command)
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed(
            "Игрок кикнут",
            f"**Игрок:** {player}\n**Причина:** {reason or 'Не указана'}\n**Ответ сервера:** {response}",
            discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ban", description="Забанить игрока на сервере Minecraft.")
    @app_commands.describe(player="Имя игрока", reason="Причина бана")
    async def ban(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        await interaction.response.defer(ephemeral=True)
        command = f"ban {player} {reason or 'Нарушение правил сервера.'}"
        try:
            response = await self.rcon_command(command)
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = self.build_embed(
            "Игрок забанен",
            f"**Игрок:** {player}\n**Причина:** {reason or 'Не указана'}\n**Ответ сервера:** {response}",
            discord.Color.dark_red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="whitelist", description="Добавить или удалить игрока из белого списка.")
    @app_commands.describe(action="add или remove", player="Имя игрока")
    async def whitelist(
        self,
        interaction: discord.Interaction,
        action: str,
        player: str,
    ) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        action = action.lower()
        if action not in ("add", "remove"):
            raise app_commands.AppCommandError("Действие должно быть add или remove.")

        await interaction.response.defer(ephemeral=True)
        command_text = f"whitelist {action} {player}"
        try:
            response = await self.rcon_command(command_text)
        except RuntimeError as exc:
            embed = self.build_embed("Ошибка RCON", str(exc), discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        verb = "Добавлен" if action == "add" else "Удален"
        embed = self.build_embed(
            "Белый список обновлен",
            f"**Игрок:** {player}\n**Операция:** {verb}\n**Ответ сервера:** {response}",
            discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def camera_loop(self) -> None:
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            try:
                if not self.camera_player:
                    return

                response = await self.rcon_command(
                    f"execute as {self.camera_player} run tp @s ~ ~ ~ {int(self.camera_yaw)} ~"
                )
                logger.info(
                    "Камера игрока %s повернута на %s°: %s",
                    self.camera_player,
                    int(self.camera_yaw),
                    response,
                )
                self.camera_yaw = (self.camera_yaw + 30) % 360
            except Exception as exc:
                logger.warning("Не удалось повернуть камеру игрока %s: %s", self.camera_player, exc)

            await asyncio.sleep(10)


async def setup(bot: commands.Bot) -> None:
    mc_ip = os.getenv("MC_SERVER_IP")
    mc_port = get_int_env("MC_SERVER_PORT", 25565)
    rcon_port = get_int_env("MC_RCON_PORT", 25575)
    rcon_password = os.getenv("MC_RCON_PASSWORD")
    admin_role_id = get_int_env("ADMIN_ROLE_ID")
    log_channel_id = get_int_env("LOG_CHANNEL_ID")
    auth_player = os.getenv("MC_AUTH_PLAYER")
    camera_player = os.getenv("MC_CAMERA_PLAYER")

    if not mc_ip or not rcon_password:
        logger.error("MC_SERVER_IP и MC_RCON_PASSWORD обязаны быть установлены.")
        return

    await bot.add_cog(
        Minecraft(
            mc_ip=mc_ip,
            mc_port=mc_port,
            rcon_port=rcon_port,
            rcon_password=rcon_password,
            admin_role_id=admin_role_id,
            log_channel_id=log_channel_id,
            auth_player=auth_player,
            camera_player=camera_player,
        )
    )
