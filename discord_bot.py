import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui

from data_manager import get_cached_data, set_cached_data
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class StreamBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="humanos assistindo streams"
            )
        )
        self.start_time = datetime.now()
        self.live_role_name = "Ao Vivo"
        self.twitch_api: Optional[TwitchAPI] = None
        self.youtube_api: Optional[YouTubeAPI] = None
        self.drive_service = None
        self.guild_live_roles: Dict[int, Optional[discord.Role]] = {}

bot = StreamBot()

# --------------------------------------------------------------------------
# Funções auxiliares
# --------------------------------------------------------------------------

async def get_or_create_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    if guild.id in bot.guild_live_roles:
        role = bot.guild_live_roles[guild.id]
        if role:
            return role
    
    role = discord.utils.get(guild.roles, name=bot.live_role_name)
    if role:
        bot.guild_live_roles[guild.id] = role
        return role
    
    try:
        if not guild.me.guild_permissions.manage_roles:
            logger.warning(f"Alvo: {guild.name} - Permissões insuficientes para criar cargo")
            bot.guild_live_roles[guild.id] = None
            return None
        
        role = await guild.create_role(
            name=bot.live_role_name,
            color=discord.Color.red(),
            hoist=True,
            mentionable=True,
            reason="Cargo para alvos em transmissão ao vivo"
        )
        
        try:
            await role.edit(position=guild.me.top_role.position - 1)
        except Exception:
            pass
            
        bot.guild_live_roles[guild.id] = role
        return role
    
    except Exception as e:
        logger.error(f"Falha na criação de cargo em {guild.name}: {e}")
        bot.guild_live_roles[guild.id] = None
        return None

# --------------------------------------------------------------------------
# Comandos da Twitch
# --------------------------------------------------------------------------

@bot.tree.command(name="twitch_add", description="Vincula um usuário do Discord a um streamer da Twitch")
@app_commands.describe(
    twitch_username="Nome de usuário da Twitch (ex: alanzoka)",
    discord_member="O alvo humano para vinculação"
)
@app_commands.checks.has_permissions(administrator=True)
async def twitch_add_command(interaction: discord.Interaction, twitch_username: str, discord_member: discord.Member):
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        twitch_name = twitch_username.lower().strip()
        if not re.match(r'^[a-z0-9_]{3,25}$', twitch_name):
            return await interaction.followup.send("❌ Alvo inválido! Padrão de nome não corresponde aos requisitos.", ephemeral=True)

        data = await get_cached_data()
        guild_id = str(interaction.guild.id)
        discord_id = str(discord_member.id)

        if guild_id not in data["streamers"]:
            data["streamers"][guild_id] = {}

        if twitch_name in data["streamers"][guild_id]:
            return await interaction.followup.send("⚠️ Alvo já registrado na base de dados!", ephemeral=True)

        data["streamers"][guild_id][twitch_name] = discord_id
        await set_cached_data(data, bot.drive_service)

        await interaction.followup.send(
            f"✅ Alvo registrado com sucesso.\n"
            f"🔹 **Streamer Twitch:** `{twitch_name}`\n"
            f"🔹 **Humano vinculado:** {discord_member.mention}\n"
            f"*Sistema de monitoramento ativado*",
            ephemeral=True
        )
            
    except Exception as e:
        logger.error(f"Falha no comando twitch_add: {e}")
        await interaction.followup.send("❌ Falha na operação. Relatório de erro gerado.", ephemeral=True)

# ... (outros comandos da Twitch com a mesma temática)

# --------------------------------------------------------------------------
# Comandos do YouTube
# --------------------------------------------------------------------------

@bot.tree.command(name="youtube_add", description="Adiciona um canal do YouTube para monitoramento")
@app_commands.describe(
    youtube_url="URL do canal do YouTube",
    notification_channel="Canal para notificações",
    discord_member="Alvo humano para cargo (opcional)"
)
@app_commands.checks.has_permissions(administrator=True)
async def youtube_add_command(
    interaction: discord.Interaction,
    youtube_url: str,
    notification_channel: discord.TextChannel,
    discord_member: Optional[discord.Member] = None
):
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        if not youtube_url.startswith(("http://", "https://")):
            youtube_url = f"https://{youtube_url}"

        await interaction.followup.send("🔍 Analisando alvo YouTube...", ephemeral=True)
        
        youtube_id = await bot.youtube_api.get_channel_id_from_url(youtube_url)
        if not youtube_id:
            return await interaction.followup.send(
                "❌ Alvo não identificado. Verifique os parâmetros de busca.",
                ephemeral=True
            )

        data = await get_cached_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in data.get("youtube_channels", {}):
            data["youtube_channels"][guild_id] = {}
        
        if youtube_id in data["youtube_channels"][guild_id]:
            return await interaction.followup.send(
                "⚠️ Alvo já está sob vigilância!",
                ephemeral=True
            )

        data["youtube_channels"][guild_id][youtube_id] = {
            "notification_channel_id": str(notification_channel.id),
            "last_video_id": None,
            "discord_user_id": str(discord_member.id) if discord_member else None
        }

        await set_cached_data(data, bot.drive_service)
        
        response_msg = (
            f"✅ **Alvo registrado no sistema**\n\n"
            f"🔹 **Canal YouTube:** {youtube_url}\n"
            f"🔹 **ID do alvo:** `{youtube_id}`\n"
            f"🔹 **Canal de notificações:** {notification_channel.mention}\n"
        )
        
        if discord_member:
            response_msg += f"🔹 **Humano vinculado:** {discord_member.mention}\n"
        
        response_msg += "\n*Monitoramento ativado com sucesso*"
        
        await interaction.followup.send(response_msg, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Falha no comando youtube_add: {e}")
        await interaction.followup.send(
            "❌ Falha na operação. Sistema retornou:\n"
            f"`{str(e)}`",
            ephemeral=True
        )

# ... (restante dos comandos com a mesma temática)

# --------------------------------------------------------------------------
# Eventos e tarefas
# --------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info(f"✅ Sistema T-800 online | ID: {bot.user.id}")
    logger.info(f"🔍 Monitorando {len(bot.guilds)} localizações")
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"🔄 {len(synced)} comandos armazenados na memória")
    except Exception as e:
        logger.error(f"❌ Falha na sincronização de comandos: {e}")

    # Configurar cargos em todos os servidores
    for guild in bot.guilds:
        await get_or_create_live_role(guild)

    # Iniciar tarefas de monitoramento
    if not check_live_streamers.is_running():
        check_live_streamers.start()
    if not check_youtube_channels.is_running():
        check_youtube_channels.start()

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="humanos assistindo streams"
    ))

@tasks.loop(minutes=5)
async def check_live_streamers():
    logger.info("🔍 Varredura de alvos Twitch iniciada...")
    # ... (implementação existente com mensagens temáticas)

@tasks.loop(minutes=10)
async def check_youtube_channels():
    logger.info("🔍 Varredura de alvos YouTube iniciada...")
    # ... (implementação existente com mensagens temáticas)
