from __future__ import annotations

import operator
import re
from collections import Counter
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utilities.bases.cog import CyCog
from utilities.functions import format_var_name
from utilities.types import FeatureType

if TYPE_CHECKING:
    from utilities.bases.bot import Cyrene
    from utilities.bases.context import CyContext

FIXUP_REPLACE = {
    r'https?:\/\/(?:x|twitter|cunnyx)\.com\/(?:\w+)\/status\/(\d+)': r'https://fixupx.com/status/\g<1>',
    r'https?:\/\/open\.(?:spotify)\.com\/track\/([a-zA-Z0-9]+)': r'https://fxspotify.com/track/\g<1>',
    r'https?:\/\/(?:www\.)?(?:instagram)\.com\/(?:(?!(?:p|reels?)\/)\S+\/)?(p|reels?)\/(\S+)(?:\??\S+)?': r'https://oginstagram.com/\g<1>/\g<2>',
}

FIXUP_EMOJI = '\U0001f527'


class Utility(CyCog, name='Utility'):
    """Some useful utility commands."""

    def __init__(self, bot: Cyrene) -> None:
        super().__init__(bot)

    async def cog_load(self) -> None:
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

    @commands.hybrid_command(name='optin', description='Optin for features which are disabled by default.')
    @app_commands.choices(
        feature=[app_commands.Choice(name=feature_enum.name, value=feature_enum.value) for feature_enum in FeatureType]
    )
    async def optin_command(self, ctx: CyContext, feature: int) -> discord.Message:
        if feature not in FeatureType:
            return await ctx.reply("This feature doesn't fucking exist.")

        optins = (config for config in self.bot.feature_optins if config.feature == feature)

        if (is_opted := [_ for _ in optins if _.user == ctx.author.id]) and is_opted:
            feat = is_opted[0]
            await self.bot.pool.execute(
                'DELETE FROM FeatureOptins WHERE user_id = $1 AND feature = $2',
                ctx.author.id,
                feature,
            )
            await self.bot.refresh_vars()
            return await ctx.reply(f'You have opted out from {format_var_name(feat.feature.name)}')

        await self.bot.pool.execute('INSERT INTO FeatureOptins (user_id, feature) VALUES ($1, $2)', ctx.author.id, feature)
        await self.bot.refresh_vars()
        return await ctx.reply(f'You have opted in for {format_var_name(FeatureType(feature).name)}')

    @commands.Cog.listener('on_reaction_add')
    async def fixup_content(self, reaction: discord.Reaction, user: discord.User) -> None:
        if not [_ for _ in self.bot.feature_optins if _.feature == FeatureType.FIXUP_CONTENT and _.user == user.id]:
            return

        if reaction.emoji != FIXUP_EMOJI:
            return

        message = reaction.message

        content = message.content

        fixups: list[str] = []
        for match_regex, substitution_regex in FIXUP_REPLACE.items():
            if (matches := re.finditer(match_regex, content)) and matches:
                fixups.extend(
                    re.sub(match_regex, substitution_regex, content[match.start() : match.end()]) for match in matches
                )

        if fixups:
            await message.channel.send(content='\n'.join(fixups))


async def setup(bot: Cyrene) -> None:
    await bot.add_cog(Utility(bot))
