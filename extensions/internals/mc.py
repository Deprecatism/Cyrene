from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from discord.ext import commands

from utilities.bases.cog import CyCog

if TYPE_CHECKING:
    import discord

    from utilities.bases.bot import Cyrene

LOG_PATH = '/app/mc_logs/latest.log'
MESSAGE_REGEX = r'.+\[Server thread\/INFO\] .+: <(?P<username>.+)> (?P<message>.+)'
ACHIEVEMENT_REGEX = r'.+\[Server thread\/INFO\] .+: (?P<username>.+) has (.+) \[(?P<advancement>.+)\]'
CHANNEL_ID = 1464932751978270721


class Minecraft(CyCog):
    def __init__(self, bot: Cyrene) -> None:
        super().__init__(bot)

        self.task = self.bot.loop.create_task(self.minecraft_chat_recieve())

    def cog_unload(self) -> None:
        self.task.cancel()

    async def minecraft_chat_recieve(self) -> None:
        proc_coroutine = asyncio.create_subprocess_shell(
            f'tail --lines 0 -F {LOG_PATH}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        process = await self.bot.loop.create_task(proc_coroutine)

        if process.stdout is None:
            self.restart_task()
            return

        async for output in process.stdout:
            await self.mc_message_handler(output.decode())

    async def mc_message_handler(self, msg: str) -> None:
        message_match = re.findall(MESSAGE_REGEX, msg)

        if message_match:
            data = message_match[0]
            self.bot.dispatch('message_dispatch', f'**{data[0]}**: {data[1]}')

            return

        advancement_match = re.findall(ACHIEVEMENT_REGEX, msg)

        if advancement_match:
            data = advancement_match[0]
            self.bot.dispatch('message_dispatch', f'**{data[0]}** has {data[1]} [**{data[2]}**]')

            return

    @commands.Cog.listener('on_message_dispatch')
    async def send_to_channel(self, msg: str) -> None:
        channel: discord.TextChannel = self.bot.get_channel(CHANNEL_ID)  # pyright: ignore[reportAssignmentType]
        await channel.send(msg)

    def restart_task(self) -> None:
        self.task.cancel()
        self.task = self.bot.loop.create_task(self.minecraft_chat_recieve())
