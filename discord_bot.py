import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Dict, Any
import os
import asyncio
from data_manager import get_data as dm_get_data, save_data as dm_save_data

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
        self.live_role = "AO VIVO"
        self.system_ready = False
        self.synced = False
        self.twitch_api = None
        self.youtube_api = None

    async def on_ready(self):
        """Evento quando o bot está pronto para uso."""
        if not self.synced:
            try:
                # Sincroniza os comandos a partir da variável de ambiente GUILD_ID no Render
                guild_id_str = os.environ.get("GUILD_ID")
                if guild_id_str:
                    guild_id = int(guild_id_str)
                    guild = discord.Object(id=guild_id)
                    await self.tree.sync(guild=guild)
                    self.synced = True
                    logger.info("✅ Missão: Comandos sincronizados com sucesso na guilda especificada pela variável de ambiente!")
                else:
                    await self.tree.sync()
                    self.synced = True
                    logger.warning("⚠️ Variável de ambiente GUILD_ID não encontrada. Sincronizando comandos globalmente.")

            except Exception as e:
                logger.error(f"❌ Falha ao sincronizar comandos: {e}")

        # Carrega os cogs
        try:
            await self.load_extension("cogs.twitch_monitor")
            await self.load_extension("cogs.youtube_monitor")
            await self.load_extension("cogs.admin")
            self.system_ready = True
            logger.info("✅ Módulos de monitoramento carregados. Sistema online!")
        except Exception as e:
            logger.error(f"❌ Falha ao carregar cogs: {e}")

        logger.info(f"✅ Sistema online e pronto para uso como {self.user.name} ({self.user.id}).")
    
    async def get_data(self) -> Dict[str, Any]:
        """Retorna os dados do cache de dados."""
        return await dm_get_data()

    async def save_data(self) -> None:
        """Salva os dados no arquivo e no Google Drive."""
        await dm_save_data(self.drive_service)

bot = T800Bot()

# Nota: As tarefas de monitoramento (tasks.loop) agora estão dentro dos cogs para evitar este tipo de erro.
# O cog é carregado em on_ready e o loop é iniciado dentro do próprio cog.
