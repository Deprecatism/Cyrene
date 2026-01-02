from __future__ import annotations

import contextlib
import operator
import re
from collections import Counter
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from config import DEFAULT_WEBHOOK
from utilities.bases.bot import Cyrene
from utilities.bases.cog import CyCog

if TYPE_CHECKING:
    from utilities.bases.bot import Cyrene
    from utilities.bases.context import CyContext


SHAMIKO_SERVER_ID = 682869291997331466
SHAMIKO_CHAT_CHANNEL_ID = 705071817081094246
X_COM_REGEX = '.+//x.com/.+'
X_COM_SUB = '//fxtwitter.com/'


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
        await super().cog_load()

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

    @commands.Cog.listener('message')
    async def shamiko_fxtwitter(self, message: discord.Message):
        if not message.guild or message.guild.id != SHAMIKO_SERVER_ID:
            return

        if message.channel.id != SHAMIKO_CHAT_CHANNEL_ID:
            return

        if message.author.bot is True:
            return

        is_x_com_message = re.match(X_COM_REGEX, message.content)

        if not is_x_com_message:
            return

        new_content = re.sub(X_COM_REGEX, X_COM_SUB, message.content)

        with contextlib.suppress(discord.HTTPException):
            await message.delete()

        await self.bot.webhooks['SHAMIKO'].send(
            content=new_content,
            avatar_url=message.author.display_avatar.url,
            username=message.author.display_name,
        )


async def setup(bot: Cyrene) -> None:
    await bot.add_cog(Utility(bot))
