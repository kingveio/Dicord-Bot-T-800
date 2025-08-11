import discord
from discord.ext import commands
import logging
from datetime import datetime
from data_manager import get_data, save_data

# ========== CONFIGURAÇÃO INICIAL ========== #
logger = logging.getLogger("T-800")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class T800Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="análise de alvos humanos"
            )
        )
        self.start_time = datetime.now()
        self.live_role_name = "AO VIVO"
        self.system_ready = False
        self.synced = False
        self.twitch_api = None
        self.youtube_api = None
        self.drive_service = None

    async def setup_hook(self):
        """Carrega os cogs e sincroniza os comandos após o bot estar pronto."""
        # Carrega os cogs
        cogs_to_load = ["cogs.monitoramento", "cogs.youtube_monitor", "cogs.admin"] # <-- 'cogs.admin' adicionado
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o cog '{cog}': {e}")
        
        # Sincroniza os comandos com o Discord
        if not self.synced:
            try:
                synced_commands = await self.tree.sync()
                self.synced = True
                logger.info(f"✅ Missão: {len(synced_commands)} comandos sincronizados globalmente com sucesso!")
            except Exception as e:
                logger.error(f"❌ Falha ao sincronizar comandos globalmente: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Evento quando o bot está pronto para uso."""
        logger.info("✅ Sistema online e pronto para operar.")
        self.system_ready = True
        
bot = T800Bot()

# Adiciona os métodos de dados à classe do bot para facilitar o acesso dos cogs
async def get_data_from_bot():
    return await get_data()

async def save_data_from_bot():
    return await save_data(bot.drive_service)
    
bot.get_data = get_data_from_bot
bot.save_data = save_data_from_bot
