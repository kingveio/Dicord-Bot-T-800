import discord
from discord.ext import commands, tasks
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
        # Novo dicionário para rastrear o estado de live de cada usuário em cada plataforma
        self.live_users = {}

    async def setup_hook(self):
        """Carrega os cogs e sincroniza os comandos após o bot estar pronto."""
        logger.info("⚙️ Iniciando setup_hook para carregar cogs e sincronizar comandos...")
        cogs_to_load = ["cogs.monitoramento", "cogs.youtube_monitor", "cogs.admin"]
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o cog '{cog}': {e}")
        
        if not self.synced:
            try:
                synced_commands = await self.tree.sync()
                self.synced = True
                logger.info(f"✅ Missão: {len(synced_commands)} comandos sincronizados globalmente com sucesso!")
            except Exception as e:
                logger.error(f"❌ Falha ao sincronizar comandos globalmente: {e}")

        # Inicia o loop para gerenciar os cargos de live de forma unificada
        self.manage_live_roles.start()
        logger.info("✅ Loop de gerenciamento de cargos iniciado.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Evento quando o bot está pronto para uso."""
        logger.info(f"✅ Sistema online e pronto para operar como {self.user.name} ({self.user.id}).")
        self.system_ready = True

    @tasks.loop(minutes=1)
    async def manage_live_roles(self):
        """Gerencia os cargos de live com base no estado unificado."""
        if not self.system_ready:
            return
            
        logger.info("⚙️ Gerenciamento unificado de cargos 'AO VIVO' iniciado.")
        
        for user_id, status in self.live_users.items():
            is_live = status.get("twitch", False) or status.get("youtube", False)
            
            try:
                guild_id = status.get("guild_id")
                if not guild_id:
                    continue
                
                guild = self.get_guild(guild_id)
                member = guild.get_member(user_id) if guild else None
                if not member:
                    continue

                live_role = discord.utils.get(guild.roles, name=self.live_role_name)
                if not live_role:
                    logger.warning(f"Cargo '{self.live_role_name}' não encontrado na guilda {guild.name}. O gerenciamento de cargos não pode continuar.")
                    continue

                if is_live:
                    if live_role not in member.roles:
                        await member.add_roles(live_role, reason="Usuário está ao vivo em uma plataforma monitorada.")
                        logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name}.")
                else:
                    if live_role in member.roles:
                        await member.remove_roles(live_role, reason="Usuário não está mais ao vivo em nenhuma plataforma monitorada.")
                        logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name}.")

            except Exception as e:
                logger.error(f"❌ Falha no gerenciamento de cargos para o usuário {user_id}: {e}")

    @manage_live_roles.before_loop
    async def before_manage_live_roles(self):
        await self.wait_until_ready()

    # O resto do código permanece o mesmo

bot = T800Bot()

async def get_data_from_bot():
    return await get_data()

async def save_data_from_bot():
    return await save_data(bot.drive_service)
    
bot.get_data = get_data_from_bot
bot.save_data = save_data_from_bot
