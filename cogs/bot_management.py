import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("bot-management-cog")


class BotManagement(commands.Cog):
    def __init__(self, bot: commands.Bot, bot_name: str, default_status: str, admin_role_id: Optional[int]):
        self.bot = bot
        self.bot_name = bot_name or "DarkAgencyBOT"
        self.default_status = default_status or "AFK | Управление через Discord"
        self.admin_role_id = admin_role_id
        self.afk_mode = True
        self.custom_status: Optional[str] = None
        self._initialized = False

    async def cog_load(self) -> None:
        logger.info("Cog BotManagement загружен.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        await self.set_bot_name(self.bot_name)
        await self.set_presence()

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        if self.admin_role_id is None:
            return True
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        return any(role.id == self.admin_role_id for role in interaction.user.roles)

    async def set_bot_name(self, new_name: str) -> None:
        if not new_name:
            return
        try:
            if self.bot.user is not None:
                await self.bot.user.edit(username=new_name)
                logger.info("Имя бота изменено на %s", new_name)
        except Exception as exc:
            logger.warning("Не удалось изменить имя бота: %s", exc)

    async def set_presence(self, message: Optional[str] = None) -> None:
        text = message or self.custom_status or self.default_status
        status = discord.Status.idle if self.afk_mode else discord.Status.online
        activity = discord.Game(name=text)
        try:
            await self.bot.change_presence(status=status, activity=activity)
        except Exception as exc:
            logger.warning("Не удалось обновить статус бота: %s", exc)

    @app_commands.command(name="afk", description="Включить или выключить AFK-режим бота.")
    async def afk(self, interaction: discord.Interaction) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        self.afk_mode = not self.afk_mode
        await self.set_presence()
        state = "включён" if self.afk_mode else "выключен"
        await interaction.response.send_message(f"AFK-режим {state}.", ephemeral=True)

    @app_commands.command(name="setstatus", description="Изменить статус бота.")
    @app_commands.describe(message="Текст статуса")
    async def setstatus(self, interaction: discord.Interaction, message: str) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        self.custom_status = message or None
        await self.set_presence(message)
        await interaction.response.send_message(f"Статус обновлён: {message or self.default_status}", ephemeral=True)

    @app_commands.command(name="setname", description="Изменить имя бота.")
    @app_commands.describe(name="Новое имя бота")
    async def setname(self, interaction: discord.Interaction, name: str) -> None:
        if not await self.is_admin(interaction):
            raise app_commands.CheckFailure("Только администратор может использовать эту команду.")

        self.bot_name = name or self.bot_name
        await self.set_bot_name(self.bot_name)
        await interaction.response.send_message(f"Имя бота изменено на {self.bot_name}", ephemeral=True)
