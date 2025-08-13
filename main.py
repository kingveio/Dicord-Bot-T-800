import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout, ClientError
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
from data.data_manager import DataManager
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI

logger = logging.getLogger(__name__)

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
        self.keep_alive_task = None
        self.session = None

    async def setup_hook(self):
        """Configuração assíncrona durante a inicialização"""
        try:
            self.session = ClientSession(timeout=ClientTimeout(total=10))
            await self.data_manager.load()
            await self.load_cogs()
            
            if Config.is_render():
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
        except Exception as e:
            logger.critical(f"Erro no setup_hook: {e}", exc_info=True)
            raise

    async def load_cogs(self):
        """Carrega todos os cogs automaticamente"""
        cogs = [
            "cogs.live_monitor",
            "cogs.settings",
            "cogs.twitch",
            "cogs.youtube"
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog carregado: {cog}")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar cog {cog}: {e}")

    async def keep_alive(self):
        """Mantém o bot ativo no Render"""
        await self.wait_until_ready()
        health_check_url = f"https://{Config.RENDER_SERVICE_NAME}.onrender.com" if hasattr(Config, 'RENDER_SERVICE_NAME') else "https://your-service-name.onrender.com"
        
        while not self.is_closed():
            try:
                async with self.session.get(health_check_url) as resp:
                    if resp.status != 200:
                        logger.warning(f"Keep-alive status: {resp.status}")
            except ClientError as e:
                logger.error(f"⚠️ Keep-alive falhou: {e}")
            await asyncio.sleep(300)

    async def close(self):
        """Limpeza quando o bot está desligando"""
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        if self.session and not self.session.closed:
            await self.session.close()
        
        await super().close()

async def main():
    try:
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        bot = Bot()
        await bot.start(Config.DISCORD_TOKEN)
        
    except Exception as e:
        logger.critical(f"💥 Erro fatal: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot encerrado pelo usuário")
    except Exception as e:
        logger.critical(f"💥 Falha não tratada: {e}", exc_info=True)
