import os
import logging
from datetime import datetime
from typing import List, Dict
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Bot, Context
from data_manager import get_data, save_data

# Configuração do logger para este bot
logger = logging.getLogger("T-800")

class T800Bot(commands.Bot):
    """
    O bot principal, responsável por inicializar todos os serviços e cogs.
    """
    def __init__(self, intents: discord.Intents, application_id: int):
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            application_id=application_id,
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
        self.live_users = {} # Dicionário unificado para rastrear o status de live

    async def on_ready(self):
        """Executado quando o bot está pronto e conectado ao Discord."""
        logger.info(f"✅ Bot '{self.user}' conectado ao Discord.")
        logger.info("📡 Iniciando sincronização de cogs e comandos...")

        # Lista de cogs a serem carregados
        cogs_to_load = [
            "cogs.monitoramento",
            "cogs.youtube_monitor",
            "cogs.admin"
        ]

        await self.load_cogs(cogs_to_load)

        self.manage_live_roles.start()
        self.system_ready = True
        logger.info(f"🚀 Sistema T-800 pronto para operação. Tempo de atividade: {self.uptime()}")

    async def setup_hook(self):
        """
        Sincroniza os comandos de barra com o Discord.
        """
        if not self.synced:
            try:
                await self.tree.sync()
                self.synced = True
                logger.info("✅ Comandos de barra sincronizados com sucesso.")
            except Exception as e:
                logger.error(f"❌ Falha ao sincronizar comandos de barra: {e}", exc_info=True)

    async def load_cogs(self, cogs_to_load: List[str]):
        """
        Tenta carregar a lista de cogs.
        """
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar o cog '{cog}': {e}", exc_info=True)

    @tasks.loop(minutes=1)
    async def manage_live_roles(self):
        """
        Verifica o status de live unificado e atribui/remove o cargo 'AO VIVO'.
        """
        if not self.system_ready:
            return

        logger.info("🔄 Verificando status de live para gerenciamento de cargos...")
        
        try:
            # Iterar sobre todos os membros que estão sendo monitorados
            for member_id, status in self.live_users.items():
                guild_id = status.get("guild_id")
                if not guild_id:
                    continue

                guild = self.get_guild(guild_id)
                if not guild:
                    logger.warning(f"⚠️ Servidor com ID {guild_id} não encontrado. Pulando.")
                    continue

                member = guild.get_member(int(member_id))
                if not member:
                    logger.warning(f"⚠️ Membro com ID {member_id} não encontrado no servidor '{guild.name}'.")
                    continue
                
                # Obtém o cargo "AO VIVO"
                live_role = discord.utils.get(guild.roles, name=self.live_role_name)
                if not live_role:
                    logger.warning(f"⚠️ O cargo '{self.live_role_name}' não foi encontrado no servidor '{guild.name}'.")
                    continue

                is_live_on_any_platform = status["twitch"] or status["youtube"]

                if is_live_on_any_platform and live_role not in member.roles:
                    await member.add_roles(live_role, reason="Streamer iniciou uma live.")
                    logger.info(f"✅ Cargo '{live_role.name}' adicionado a '{member.name}'.")
                elif not is_live_on_any_platform and live_role in member.roles:
                    await member.remove_roles(live_role, reason="Streamer encerrou todas as lives.")
                    logger.info(f"❌ Cargo '{live_role.name}' removido de '{member.name}'.")

        except Exception as e:
            logger.error(f"❌ Falha no gerenciamento de cargos de live: {e}", exc_info=True)

    @manage_live_roles.before_loop
    async def before_manage_live_roles(self):
        """Espera o bot estar pronto antes de iniciar o loop."""
        await self.wait_until_ready()

    def uptime(self):
        """Calcula o tempo de atividade do bot."""
        delta = datetime.now() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
