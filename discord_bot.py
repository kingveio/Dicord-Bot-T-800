import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Dict, Any, List
import os
import asyncio
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
        self.live_role = "AO VIVO"
        self.system_ready = False
        self.synced = False
        self.twitch_api = None # Mantemos a referência aqui, mas a inicialização será no main.py
        self.youtube_api = None
    
    async def on_ready(self):
        """Evento quando o bot está pronto para uso."""
        if not self.synced:
            try:
                await self.tree.sync()
                for guild in self.guilds:
                    await self.tree.sync(guild=guild)
                self.synced = True
                logger.info("✅ Missão: Comandos sincronizados com sucesso!")
            except Exception as e:
                logger.error(f"❌ Falha ao sincronizar comandos: {e}")

        # Carrega os cogs
        try:
            await self.load_extension("cogs.twitch_monitor")
            await self.load_extension("cogs.youtube_monitor")
            self.system_ready = True
            logger.info("✅ Módulos de monitoramento carregados. Sistema online!")
        except Exception as e:
            logger.error(f"❌ Falha ao carregar cogs: {e}")

        logger.info(f"✅ Sistema online e pronto para uso como {self.user.name} ({self.user.id}).")
        
        # Inicia a tarefa de monitoramento de status
        self.monitor_twitch_and_youtube.start()

    @tasks.loop(minutes=5)
    async def monitor_twitch_and_youtube(self):
        """Esta tarefa será usada apenas para monitorar e não para lógica de API"""
        if not self.system_ready:
            return

        # Chamadas para os métodos de monitoramento dos cogs
        await self.get_cog('TwitchMonitor').monitor_twitch_streams()
        await self.get_cog('YouTubeMonitor').monitor_youtube_streams()

bot = T800Bot()
