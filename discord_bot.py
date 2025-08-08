# discord_bot.py
import os
import asyncio
import logging
import re
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands, ui

from data_manager import get_cached_data, set_cached_data
from twitch_api import TwitchAPI

logger = logging.getLogger(__name__)

# Configurações do bot, intents, etc.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="Streamers da Twitch")
)

# Variáveis que serão inicializadas por main.py
twitch_api = None
drive_service = None
START_TIME = datetime.now()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 55))
CHECK_TASK = None

# Funções utilitárias
async def get_or_create_live_role(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name="Ao Vivo")
    if role: return role
    try:
        role = await guild.create_role(
            name="Ao Vivo",
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True
        )
        return role
    except Exception as e:
        logger.error(f"Erro ao criar cargo 'Ao Vivo' no guild {guild.id}: {e}")
        return None

def sanitize_discord_id(input_str: str) -> str:
    digits = re.sub(r'\D', '', input_str)
    if not digits.isdigit() or not (17 <= len(digits) <= 19): return ""
    return digits

# UI e Comandos
class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    # ... (código do modal) ...
    async def on_submit(self, interaction: discord.Interaction):
        # ... (código do modal com alteração para usar set_cached_data com drive_service) ...
        data = await get_cached_data()
        guild_id = str(interaction.guild.id)
        if guild_id not in data: data[guild_id] = {}
        data[guild_id][twitch_username] = discord_id
        await set_cached_data(data, drive_service, persist=True)
        # ...

class StreamersView(ui.View):
    # ... (código da view) ...
   @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        # ... (código do callback com alteração para usar set_cached_data) ...
        async def callback(inner_interaction: discord.Interaction):
            selected = select.values[0]
            data_local = await get_cached_data()
            guild_id = str(inner_interaction.guild.id)
            if selected in data_local.get(guild_id, {}):
                del data_local[guild_id][selected]
                await set_cached_data(data_local, drive_service, persist=True)
                # ...
        # ...

@bot.tree.command(...)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message("...", view=StreamersView(), ephemeral=True)

@bot.tree.command(...)
async def status_command(interaction: discord.Interaction):
    # ... (código do status) ...
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Task de verificação
async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Task de checagem iniciada")
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            all_streamers = {s for g in data.values() for s in g.keys()}
            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            live_streamers = await twitch_api.check_live_streams(all_streamers)
            # ... (código de atualização de cargos) ...
        except Exception as e:
            logger.error(f"Erro no verificador principal: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# Eventos
@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        logger.info("✅ Comandos sincronizados")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {e}")
    
    global CHECK_TASK
    if CHECK_TASK is None or CHECK_TASK.done():
        CHECK_TASK = bot.loop.create_task(check_streams_task())

@bot.event
async def on_disconnect():
    logger.info("🔻 Iniciando shutdown limpo")
    if CHECK_TASK:
        CHECK_TASK.cancel()
    # A sessão HTTP será fechada no main.py

def run_discord_bot(token: str):
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Erro ao rodar bot: {e}")
