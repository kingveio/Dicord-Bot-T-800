import os
import sys
import discord
from discord.ext import commands
import logging
import aiohttp
from aiohttp import web
import asyncio
from dotenv import load_dotenv

# Adiciona o diretório 'src' ao sys.path para resolver importações (mantido por segurança)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import Config
from data.data_manager import DataManager
from cogs.live_monitor import LiveMonitor
from cogs.twitch import TwitchCommands
from cogs.youtube import YouTubeCommands
from cogs.settings import Settings
from services.google_drive_service import GoogleDriveService

load_dotenv()
Config.validate()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.session = aiohttp.ClientSession()
        self.twitch_api = None
        self.youtube_api = None
        self.data_manager = DataManager()
        self.google_drive_service = None

    async def on_ready(self):
        logger.info(f"✅ Logado como {self.user} (ID: {self.user.id})")
        
        # Carregar cogs
        for cog_file in os.listdir('./cogs'):
            if cog_file.endswith('.py') and cog_file != '__init__.py':
                cog_name = cog_file[:-3]
                try:
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"✅ Cog carregado: cogs.{cog_name}")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar cogs.{cog_name}: {e}", exc_info=True)
            
        # Sincronizar comandos slash
        synced = await self.tree.sync()
        logger.info(f"✅ Comandos slash sincronizados ({len(synced)} comando(s))")

    async def setup_hook(self):
        # Passa o bot para o DataManager e inicializa
        await self.data_manager.init_services(self)

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Bot adicionado à guilda: {guild.name} (ID: {guild.id})")

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"Bot removido da guilda: {guild.name} (ID: {guild.id})")
        # Remover dados da guilda do DataManager (opcional)

    async def close(self):
        await super().close()
        await self.session.close()

# Função para criar e rodar o servidor web
async def web_server():
    async def handler(request):
        # Este handler responderá tanto a "/" quanto a "/health"
        return web.Response(text="Bot está online!")

    app = web.Application()
    # Adiciona a rota principal
    app.router.add_get("/", handler)
    # Adiciona a rota de health check para o Render
    app.router.add_get("/health", handler)
    
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Servidor web rodando na porta {port}")

async def main_loop():
    bot = DiscordBot()
    
    if os.getenv('GOOGLE_CREDENTIALS'):
        bot.google_drive_service = GoogleDriveService()
        bot.data_manager.google_drive_service = bot.google_drive_service
        
    await bot.start(Config.DISCORD_TOKEN)

# A nova função `start_server` executa o bot e o servidor web juntos
async def start_server():
    server_task = asyncio.create_task(web_server())
    bot_task = asyncio.create_task(main_loop())
    
    await asyncio.gather(server_task, bot_task)

# Iniciar o bot
if __name__ == "__main__":
    asyncio.run(start_server())
