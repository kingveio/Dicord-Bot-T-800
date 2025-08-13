import asyncio
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
import logging

logger = logging.getLogger(__name__)

async def load_cogs(bot: commands.Bot):
    cogs = [
        "cogs.live_monitor",
        "cogs.settings",
        "cogs.twitch",
        "cogs.youtube"
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")

async def main():
    Config.validate()
    setup_logging(Config.LOG_LEVEL)
    
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    
    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        help_command=None
    )
    
    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    
    await load_cogs(bot)
    await bot.start(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
