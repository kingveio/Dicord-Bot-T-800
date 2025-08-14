import os
import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
from data.data_manager import DataManager
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI
from services.google_drive import GoogleDriveService

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self):
        self.app = web.Application()
        self.app.add_routes([
            web.get('/health', self.health_check),
            web.get('/', self.health_check)
        ])
        self.runner = web.AppRunner(self.app)
        self.site = None
        self.port = 8080  # Porta alterada para 8080

    async def health_check(self, request):
        return web.Response(text="🤖 T-800 Online (Porta 8080)")

    async def start(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        logger.info(f"✅ Health check rodando na porta {self.port}")

    async def stop(self):
        if self.site:
            await self.site.stop()
        await self.runner.cleanup()

class T800Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # 1. Inicializa o DataManager
        self.data_manager = DataManager()
        self.data_manager.bot = self
        
        # 2. Inicializa o serviço do Google Drive e o passa para o DataManager
        self.google_drive_service = GoogleDriveService()
        self.data_manager.google_drive_service = self.google_drive_service
        
        # 3. Inicializa os demais serviços e atributos
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        self.health_server = HealthServer()
        self.session = None
        self.keep_alive_task = None

    async def setup_hook(self):
        try:
            # 1. Inicia health check na porta 8080
            await self.health_server.start()
            
            # 2. Configura HTTP client
            self.session = ClientSession(
                timeout=ClientTimeout(total=10),
                headers={'User-Agent': 'DiscordBot/1.0'}
            )
            
            # 3. Carrega dados e extensões
            await self.data_manager.load()
            cogs = ["cogs.live_monitor", "cogs.youtube", "cogs.twitch", "cogs.settings"]
            for cog in cogs:
                try:
                    await self.load_extension(cog)
                    logger.info(f"✅ Cog carregado: {cog}")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar {cog}: {e}")
            
            # 4. Sincroniza comandos slash
            await self.tree.sync()
            logger.info("✅ Comandos slash sincronizados")
            
            # 5. Keep-alive para Render
            if Config.is_render():
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                
        except Exception as e:
            logger.critical(f"🚨 Falha no setup: {e}", exc_info=True)
            raise

    async def keep_alive(self):
        """Mantém o bot ativo no Render"""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                async with self.session.get(f"http://localhost:8080/health") as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ Health check falhou: {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Keep-alive error: {e}")
            await asyncio.sleep(60)

    async def close(self):
        logger.info("🛑 Desligando bot...")
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
        if self.session:
            await self.session.close()
        await self.health_server.stop()
        await super().close()
        logger.info("👋 Bot desligado")

async def main():
    try:
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        bot = T800Bot()
        await bot.start(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"💥 ERRO: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())
