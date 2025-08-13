import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout, ClientError
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
from data.data_manager import DataManager
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self):
        self.app = web.Application()
        self.app.add_routes([web.get('/health', self.health_check)])
        self.runner = web.AppRunner(self.app)
        self.site = None

    async def health_check(self, request):
        return web.Response(text="Bot is running")

    async def start(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 10000)
        await self.site.start()
        logger.info("Health check server started on port 10000")

    async def stop(self):
        if self.site:
            await self.site.stop()
        await self.runner.cleanup()
        logger.info("Health check server stopped")

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        self.data_manager = DataManager()
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        self.health_server = HealthServer()
        self.session = None
        self.keep_alive_task = None

    async def setup_hook(self):
        """Async setup during bot initialization"""
        try:
            # Start health check server
            await self.health_server.start()
            
            # Initialize aiohttp session
            self.session = ClientSession(timeout=ClientTimeout(total=10))
            
            # Load data and cogs
            await self.data_manager.load()
            await self.load_cogs()
            
            # Start keep-alive if on Render
            if Config.is_render():
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                
        except Exception as e:
            logger.critical(f"Error in setup_hook: {e}", exc_info=True)
            raise

    async def load_cogs(self):
        """Load all cogs automatically"""
        cogs = [
            "cogs.live_monitor",
            "cogs.settings",
            "cogs.twitch",
            "cogs.youtube"
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog loaded: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load cog {cog}: {e}")

    async def keep_alive(self):
        """Keep the bot alive on Render"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                async with self.session.get(f"https://{Config.RENDER_SERVICE_NAME}.onrender.com/health") as resp:
                    if resp.status != 200:
                        logger.warning(f"Keep-alive status: {resp.status}")
            except ClientError as e:
                logger.error(f"⚠️ Keep-alive failed: {e}")
            await asyncio.sleep(300)  # Ping every 5 minutes

    async def close(self):
        """Cleanup when bot is shutting down"""
        logger.info("Shutting down bot...")
        
        # Cancel keep-alive task
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # Close health server
        await self.health_server.stop()
        
        # Close aiohttp session
        if self.session and not self.session.closed:
            await self.session.close()
        
        # Close discord connection
        await super().close()

async def main():
    try:
        # Initial setup
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        # Initialize and start bot
        bot = Bot()
        await bot.start(Config.DISCORD_TOKEN)
        
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot shutdown by user")
    except Exception as e:
        logger.critical(f"💥 Unhandled failure: {e}", exc_info=True)
