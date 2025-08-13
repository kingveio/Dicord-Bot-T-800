import os
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
        self.app.add_routes([
            web.get('/health', self.health_check),
            web.get('/', self.health_check)  # Rota adicional para verificação manual
        ])
        self.runner = web.AppRunner(self.app)
        self.site = None
        self.port = int(os.getenv('PORT', '10000'))  # Porta automática

    async def health_check(self, request):
        return web.Response(
            text=f"Discord Bot is running (Port: {self.port})",
            content_type='text/plain'
        )

    async def start(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        logger.info(f"✅ Health check server running on port {self.port}")

    async def stop(self):
        if self.site:
            await self.site.stop()
        await self.runner.cleanup()
        logger.info("🛑 Health server stopped")

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
        """Configuração inicial assíncrona"""
        try:
            # 1. Inicia servidor de health check
            await self.health_server.start()
            await self.tree.sync()  # Sincroniza comandos slash globais
            logger.info("✅ Comandos slash sincronizados")
            # 2. Configura sessão HTTP
            self.session = ClientSession(
                timeout=ClientTimeout(total=10),
                headers={'User-Agent': 'DiscordBot/1.0'}
            )
            
            # 3. Carrega dados e extensões
            await self.data_manager.load()
            await self.load_cogs()
            
            # 4. Keep-alive apenas no Render
            if Config.is_render():
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                logger.info("🔵 Render environment detected")
            
        except Exception as e:
            logger.critical(f"🚨 Setup hook failed: {e}", exc_info=True)
            raise

    async def load_cogs(self):
        """Carrega todas as extensões do bot"""
        cogs = [
            "cogs.live_monitor",
            "cogs.settings",
            "cogs.twitch",
            "cogs.youtube"
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"🔌 Cog loaded: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load {cog}: {e}")

    async def keep_alive(self):
        """Mantém o serviço ativo no Render"""
        await self.wait_until_ready()
        service_url = f"https://{Config.RENDER_SERVICE_NAME}.onrender.com"
        
        while not self.is_closed():
            try:
                async with self.session.get(f"{service_url}/health") as resp:
                    status = "✅" if resp.status == 200 else "⚠️"
                    logger.debug(f"{status} Keep-alive ping: {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Keep-alive failed: {e}")
            await asyncio.sleep(300)  # 5 minutos

    async def close(self):
        """Limpeza ao desligar o bot"""
        logger.info("🛑 Shutting down bot...")
        
        # 1. Cancela tarefa de keep-alive
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # 2. Para o servidor de health check
        await self.health_server.stop()
        
        # 3. Fecha sessão HTTP
        if self.session and not self.session.closed:
            await self.session.close()
        
        # 4. Fecha conexão com Discord
        await super().close()
        logger.info("👋 Bot shutdown complete")

async def main():
    try:
        # Configuração inicial
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        # Inicializa e inicia o bot
        bot = Bot()
        await bot.start(Config.DISCORD_TOKEN)
        
    except Exception as e:
        logger.critical(f"💥 FATAL ERROR: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.critical(f"💥 UNHANDLED EXCEPTION: {e}", exc_info=True)
