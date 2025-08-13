import asyncio
import logging
from aiohttp import ClientSession
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
from data.data_manager import DataManager
from services.discord_service import DiscordService
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI

logger = logging.getLogger(__name__)

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",  # Prefixo não usado com comandos slash
            intents=intents,
            help_command=None
        )
        
        # Inicializa todos os serviços
        self.data_manager = DataManager()
        self.discord_service = DiscordService(self)
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        self.keep_alive_task = None

    async def setup_hook(self):
        """Configuração assíncrona durante a inicialização"""
        try:
            # 1. Carrega os dados primeiro
            await self.data_manager.load()
            
            # 2. Carrega todos os cogs
            await self.load_cogs()
            
            # 3. Inicia a tarefa keep-alive
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
        """Mantém o bot ativo no Render (plano gratuito)"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                async with ClientSession() as session:
                    async with session.get("https://your-bot-name.onrender.com") as resp:
                        if resp.status != 200:
                            logger.warning(f"Keep-alive status: {resp.status}")
            except Exception as e:
                logger.error(f"⚠️ Keep-alive falhou: {e}")
            await asyncio.sleep(300)  # Ping a cada 5 minutos

    async def close(self):
        """Limpeza quando o bot está desligando"""
        # Cancela a tarefa keep-alive
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        await super().close()

async def main():
    try:
        # Configuração inicial
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        # Inicializa o bot
        bot = Bot()
        
        # Inicia o bot
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
