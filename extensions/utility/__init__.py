from __future__ import annotations

import contextlib
import operator
import re
from collections import Counter
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utilities.bases.bot import Cyrene
from utilities.bases.cog import CyCog
from utilities.types import FeatureType

if TYPE_CHECKING:
    from utilities.bases.bot import Cyrene
    from utilities.bases.context import CyContext

FXTWITTER_MATCH = r'https?:\/\/(?:x|twitter|cunnyx)\.com\/(?:\w+)\/status\/(\d+)(?:\S+)?'
FXTWITTER_REPLACE = r'https://fxtwitter.com/status/\g<1>'


class Utility(CyCog, name='Utility'):
    """Some useful utility commands."""

    def __init__(self, bot: Cyrene) -> None:
        self.fxtwitter_optin: list[int] = []
        super().__init__(bot)

    async def cog_load(self) -> None:
        data = await self.bot.pool.fetch(
            """
            SELECT
                    user_id
            FROM
                    FeatureOptIns
            WHERE
                    feature = $1;
            """,
            FeatureType.FXTWITTER,
        )
        self.fxtwitter_optin = [_[0] for _ in data]
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

    @commands.Cog.listener('on_message')
    async def fxtwitter(self, message: discord.Message) -> None:
        if message.author.id not in self.fxtwitter_optin:
            return

        fxtwit_str = re.sub(FXTWITTER_MATCH, FXTWITTER_REPLACE, message.content)

        if fxtwit_str == message.content:
            return

        with contextlib.suppress(discord.HTTPException):
            await message.delete()

        await message.reply(content=fxtwit_str)


async def setup(bot: Cyrene) -> None:
    await bot.add_cog(Utility(bot))
