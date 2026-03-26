from __future__ import annotations

import contextlib
import datetime
import operator
import re
from collections import Counter
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from config import DEFAULT_WEBHOOK
from utilities.bases.bot import Cyrene
from utilities.bases.cog import CyCog

if TYPE_CHECKING:
    from utilities.bases.bot import Cyrene
    from utilities.bases.context import CyContext


SHAMIKO_SERVER_ID = 682869291997331466
SHAMIKO_CHAT_CHANNEL_ID = 705071817081094246

FXTWITTER_MATCH = r'https?:\/\/(?:x|twitter)\.com\/(?:\w+)\/status\/(\d+)(?:\S+)?'
FXTWITTER_REPLACE = r'https://fxtwitter.com/status/\g<1>'

SKPORT_REMINDER_ROLE = 1479873899159093420
SKPORT_REMINDER_CHANNEL = 1479897237638221987


class Utility(CyCog, name='Utility'):
    """Some useful utility commands."""

    def __init__(self, bot: Cyrene) -> None:
        super().__init__(bot)

    async def cog_load(self) -> None:

        if self.bot.webhooks.get('SHAMIKO') is None:
            await self.bot.pool.execute(
                """
                    INSERT INTO Webhooks
                    VALUES ($1, $2);
                """,
                'SHAMIKO',
                DEFAULT_WEBHOOK,
            )
            await self.bot.refresh_vars()

        self.shamiko_skport_remind.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.shamiko_skport_remind.cancel()
        await super().cog_unload()

    async def _basic_cleanup_strategy(self, ctx: CyContext, search: int) -> dict[str, int]:
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me and not (msg.mentions or msg.role_mentions):
                await msg.delete()
                count += 1
        return {'Bot': count}

    async def _complex_cleanup_strategy(self, ctx: CyContext, search: int) -> None | Counter[str]:
        prefixes = tuple(self.bot.get_prefixes(ctx.guild))  # thanks startswith

        def check(m: discord.Message) -> bool:
            return m.author == ctx.me or m.content.startswith(prefixes)

        if isinstance(ctx.channel, discord.DMChannel | discord.PartialMessageable | discord.GroupChannel):
            return None

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    async def _regular_user_cleanup_strategy(self, ctx: CyContext, search: int) -> None | Counter[str]:
        prefixes = tuple(self.bot.get_prefixes(ctx.guild))

        def check(m: discord.Message) -> bool:
            return (m.author == ctx.me or m.content.startswith(prefixes)) and not (m.mentions or m.role_mentions)

        if isinstance(ctx.channel, discord.DMChannel | discord.PartialMessageable | discord.GroupChannel):
            return None

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    @commands.command()
    @commands.guild_only()
    async def cleanup(self, ctx: CyContext, search: int = 100) -> None:
        strategy = self._basic_cleanup_strategy

        if not isinstance(ctx.author, discord.Member) or not isinstance(ctx.me, discord.Member):
            raise commands.GuildNotFound(str(ctx.guild))

        is_mod = ctx.channel.permissions_for(ctx.author).manage_messages
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            strategy = self._complex_cleanup_strategy if is_mod else self._regular_user_cleanup_strategy

        search = min(max(2, search), 1000) if is_mod else min(max(2, search), 25)

        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values()) if spammers else 0
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=operator.itemgetter(1), reverse=True) if spammers else {'Unknown': 0}
            messages.extend(f'- **{author}**: {count}' for author, count in spammers)

        await ctx.send('\n'.join(messages), delete_after=10)

    @commands.Cog.listener('on_message')
    async def shamiko_fxtwitter(self, message: discord.Message) -> None:
        if not message.guild or message.guild.id != SHAMIKO_SERVER_ID:
            return

        if message.channel.id != SHAMIKO_CHAT_CHANNEL_ID:
            return

        if message.author.bot is True:
            return

        fxtwit_str = re.sub(FXTWITTER_MATCH, FXTWITTER_REPLACE, message.content)

        if fxtwit_str == message.content:
            return

        with contextlib.suppress(discord.HTTPException):
            await message.delete()

        await self.bot.webhooks['SHAMIKO'].send(
            content=(
                f'> {message.reference.resolved.author.mention} {message.reference.jump_url}\n'
                if message.reference
                and message.reference.resolved
                and isinstance(message.reference.resolved, discord.Message)
                else ''
            )
            + fxtwit_str,
            avatar_url=message.author.display_avatar.url,
            username=message.author.display_name,
        )

    @tasks.loop(time=datetime.time(hour=16, tzinfo=datetime.UTC))
    async def shamiko_skport_remind(self) -> None:
        reminder_text = f"""<@&{SKPORT_REMINDER_ROLE}> Me when you forget to do the daily skport login"""

        ch: discord.TextChannel = self.bot.get_channel(SKPORT_REMINDER_CHANNEL)  # pyright: ignore[reportAssignmentType]
        await ch.send(reminder_text, allowed_mentions=discord.AllowedMentions.all())


async def setup(bot: Cyrene) -> None:
    await bot.add_cog(Utility(bot))
