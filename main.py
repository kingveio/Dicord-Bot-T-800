import os
import sys
import discord
from discord.ext import commands
import logging
import aiohttp
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
from google_drive import GoogleDriveService # Importação corrigida para o mesmo diretório

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
            if cog_file.endswith('.py'):
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

async def start_server():
    bot = DiscordBot()
    # Inicializa o serviço do Google Drive e passa para o DataManager
    if os.getenv('GOOGLE_CREDENTIALS'):
        bot.google_drive_service = GoogleDriveService()
        bot.data_manager.google_drive_service = bot.google_drive_service

    # Rodar o bot
    async with bot:
        await bot.start(Config.DISCORD_TOKEN)

# Iniciar o bot
if __name__ == "__main__":
    asyncio.run(start_server())
