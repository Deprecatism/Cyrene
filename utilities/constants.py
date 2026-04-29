from __future__ import annotations

import discord

__ALL__ = (
    'BASE_COLOUR',
    'ERROR_COLOUR',
    'BOT_THRESHOLD',
    'BLACKLIST_COLOUR',
    'BOT_FARM_COLOUR',
    'BotEmojis',
    'WebhookThreads',
)

BASE_COLOUR = discord.Colour.from_str('#FFB3DE')
ERROR_COLOUR = discord.Colour.from_str('#bb6688')

CHAR_LIMIT = 2000


class BotEmojis:
    GREY_TICK = discord.PartialEmoji(name='greyTick', id=1499153371830026330)
    GREEN_TICK = discord.PartialEmoji(name='greenTick', id=1499153286786322463)
    RED_CROSS = discord.PartialEmoji(name='redTick', id=1499153450842198096)

    PASS = discord.PartialEmoji(name='pass', id=1499154823927562390)
    SMASH = discord.PartialEmoji(name='smash', id=1499154775860838471)
