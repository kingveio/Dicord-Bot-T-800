import discord
from discord.ext import commands
import logging

logger = logging.getLogger("T-800")

class T800Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="streams humanos"
            )
        )
        self.live_users = {}  # Rastreia status de lives
        self.live_role_name = "AO VIVO"
        self.data = None
        self.drive_service = None
        self.twitch_api = None
        self.youtube_api = None

    async def setup_hook(self):
        # Carrega todos os módulos
        await self.load_extension("cogs.monitor")
        await self.load_extension("cogs.twitch")
        await self.load_extension("cogs.youtube")
        await self.tree.sync()
        logger.info("✅ Sistemas prontos. 'I'm back.'")

bot = T800Bot()
