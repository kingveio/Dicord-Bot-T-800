import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands, tasks
from discord import app_commands

from data_manager import get_cached_data, set_cached_data
from twitch_api import TwitchAPI
from kick_api import KickAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuração das Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = False

class StreamBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="streamers ao vivo"
            )
        )
        self.start_time = datetime.now()
        self.live_role = "AO VIVO"
        self.twitch_api: Optional[TwitchAPI] = None
        self.kick_api: Optional[KickAPI] = None
        self.drive_service = None
        self.guild_live_roles: Dict[int, Optional[discord.Role]] = {}

bot = StreamBot()

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} comandos sincronizados.")
    except Exception as e:
        logger.error(f"❌ Falha ao sincronizar comandos: {e}")
    
    bot.start_time = datetime.now()
    logger.info(f"🤖 Bot online | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")
    
    if not bot.twitch_api or not bot.kick_api or not bot.drive_service:
        logger.error("❌ APIs não inicializadas. O bot não irá funcionar corretamente.")
        return

    monitor_streams.start()
    logger.info("🔍 Monitoramento de streams iniciado...")
    
@bot.tree.command(name="status", description="Mostra o status do bot e das APIs")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    uptime = datetime.now() - bot.start_time
    data = await get_cached_data(bot.drive_service) or {}
    streamers_data = data.get("streamers", {})

    twitch_count = 0
    kick_count = 0

    if isinstance(streamers_data, dict):
        for guild_streamers in streamers_data.values():
            if isinstance(guild_streamers, dict):
                for user_config in guild_streamers.values():
                    if isinstance(user_config, dict):
                        if 'twitch_username' in user_config:
                            twitch_count += 1
                        if 'kick_username' in user_config:
                            kick_count += 1

    # Estado das APIs
    twitch_status = "✅ OK" if bot.twitch_api and bot.twitch_api.oauth_token else "❌ OFF"
    kick_status = "✅ OK" if bot.kick_api else "❌ OFF"
    drive_status = "✅ OK" if bot.drive_service and bot.drive_service.service else "❌ OFF"

    status_msg = (
        f"**📊 STATUS DO BOT**\n"
        f"⏱ **Tempo de atividade:** {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m\n"
        f"🌐 **Servidores conectados:** {len(bot.guilds)}\n"
        f"🎯 **Alvos monitorados:**\n"
        f"   - Twitch: {twitch_count}\n"
        f"   - Kick: {kick_count}\n\n"
        f"**🔌 Status das APIs:**\n"
        f"   - Twitch API: {twitch_status}\n"
        f"   - Kick API: {kick_status}\n"
        f"   - Google Drive API: {drive_status}\n"
    )

    await interaction.followup.send(content=status_msg, ephemeral=True)
   
@bot.event
async def on_disconnect():
    logger.warning("Bot desconectado do Discord.")
    
@bot.event
async def on_resumed():
    logger.info("Bot reconectado ao Discord.")

@tasks.loop(minutes=5)
async def monitor_streams():
    logger.info("🔍 Iniciando verificação de streams...")
    data = await get_cached_data(bot.drive_service)
    
    live_twitch_users = []
    live_kick_users = []
    
    # 1. Verificação da Twitch
    twitch_users_to_check = []
    for guild_id, streamers in data.get('streamers', {}).items():
        if isinstance(streamers, dict):
            for s in streamers.values():
                if isinstance(s, dict) and 'twitch_username' in s:
                    twitch_users_to_check.append(s['twitch_username'])
    
    if twitch_users_to_check:
        try:
            live_streams = await bot.twitch_api.get_live_streams(twitch_users_to_check)
            live_twitch_users = [s['user_login'].lower() for s in live_streams]
            logger.info(f"✅ Twitch: {len(live_twitch_users)} canais ao vivo encontrados.")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lives da Twitch: {e}")

    # 2. Verificação do Kick
    kick_users_to_check = []
    for guild_id, streamers in data.get('streamers', {}).items():
        if isinstance(streamers, dict):
            for s in streamers.values():
                if isinstance(s, dict) and 'kick_username' in s:
                    kick_users_to_check.append(s['kick_username'])
    
    if kick_users_to_check:
        try:
            for username in kick_users_to_check:
                stream_info = await bot.kick_api.get_stream_info(username)
                if stream_info:
                    live_kick_users.append(username)
            logger.info(f"✅ Kick: {len(live_kick_users)} canais ao vivo encontrados.")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lives do Kick: {e}")

    # 3. Atualização dos cargos
    for guild in bot.guilds:
        if guild.id in data['streamers']:
            role = bot.guild_live_roles.get(guild.id)
            if not role:
                role = discord.utils.get(guild.roles, name=bot.live_role)
                if not role:
                    logger.warning(f"Cargo '{bot.live_role}' não encontrado no servidor '{guild.name}'. Criando...")
                    try:
                        role = await guild.create_role(
                            name=bot.live_role,
                            permissions=discord.Permissions.none(),
                            colour=discord.Colour.red()
                        )
                        bot.guild_live_roles[guild.id] = role
                    except discord.Forbidden:
                        logger.error(f"❌ Sem permissão para criar o cargo no servidor '{guild.name}'.")
                        continue
                else:
                    bot.guild_live_roles[guild.id] = role
            
            for user_id, config in data['streamers'][guild.id].items():
                member = guild.get_member(int(user_id))
                if not member:
                    continue
                
                is_live = False
                if 'twitch_username' in config and config['twitch_username'].lower() in live_twitch_users:
                    is_live = True
                if 'kick_username' in config and config['kick_username'].lower() in live_kick_users:
                    is_live = True
                
                has_role = role in member.roles
                
                if is_live and not has_role:
                    await member.add_roles(role, reason="Streamer iniciou a live")
                    logger.info(f"✅ Adicionado cargo '{bot.live_role}' para {member.display_name}.")
                elif not is_live and has_role:
                    await member.remove_roles(role, reason="Streamer encerrou a live")
                    logger.info(f"✅ Removido cargo '{bot.live_role}' de {member.display_name}.")

    logger.info("✅ Verificação de streams concluída.")
