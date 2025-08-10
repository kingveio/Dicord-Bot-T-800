import os
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui

from data_manager import get_cached_data, set_cached_data
from twitch_api import TwitchAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuração das Intents, com a função de voz desabilitada
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
                name="análise de alvos humanos"
            )
        )
        self.start_time = datetime.now()
        self.live_role = "AO VIVO"
        self.twitch_api: Optional[TwitchAPI] = None
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
    logger.info(f"🤖 T-800 ONLINE | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")
    
    if not bot.twitch_api or not bot.drive_service:
        logger.error("❌ APIs não inicializadas. O bot não irá funcionar corretamente.")
        return

    monitor_streams.start()
    logger.info("🔍 Análise de alvos iniciada...")
    
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
    
    # 1. Verificação da Twitch
    twitch_users_to_check = []
    for guild_id, streamers in data.get('streamers', {}).items():
        twitch_users_to_check.extend([s.get('twitch_username') for s in streamers.values()])

    if twitch_users_to_check:
        try:
            live_streams = await bot.twitch_api.get_live_streams(twitch_users_to_check)
            live_twitch_users = [s['user_login'].lower() for s in live_streams]
            logger.info(f"✅ Twitch: {len(live_twitch_users)} canais ao vivo encontrados.")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lives da Twitch: {e}")

    # 2. Atualização dos cargos
    for guild in bot.guilds:
        if guild.id in data['streamers']:
            role = bot.guild_live_roles.get(guild.id)
            if not role:
                role = discord.utils.get(guild.roles, name=bot.live_role)
                if not role:
                    logger.warning(f"Cargo '{bot.live_role}' não encontrado no servidor '{guild.name}'. Criando...")
                    try:
                        role = await guild.create_role(name=bot.live_role, permissions=discord.Permissions.none(), colour=discord.Colour.red())
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
                
                is_live = config['twitch_username'].lower() in live_twitch_users
                has_role = role in member.roles
                
                if is_live and not has_role:
                    await member.add_roles(role, reason="Streamer iniciou a live")
                    logger.info(f"✅ Adicionado cargo 'AO VIVO' para {member.display_name} ({config['twitch_username']}).")
                elif not is_live and has_role:
                    await member.remove_roles(role, reason="Streamer encerrou a live")
                    logger.info(f"✅ Removido cargo 'AO VIVO' de {member.display_name} ({config['twitch_username']}).")

    logger.info("✅ Verificação de streams concluída.")
    
@bot.tree.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento.")
@app_commands.describe(nome_twitch="O nome de usuário da Twitch (ex: monark)")
async def adicionar_twitch(interaction: discord.Interaction, nome_twitch: str, usuario_discord: Optional[discord.Member]):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    
    if not bot.drive_service or not bot.twitch_api:
        await interaction.followup.send("❌ Serviço do Google Drive ou Twitch não está disponível. Tente novamente mais tarde.", ephemeral=True)
        return

    data = await get_cached_data(bot.drive_service)
    
    if interaction.guild.id not in data['streamers']:
        data['streamers'][interaction.guild.id] = {}
        
    twitch_user_id = str(usuario_discord.id) if usuario_discord else str(interaction.user.id)
    
    if twitch_user_id in data['streamers'][interaction.guild.id]:
        await interaction.followup.send(f"❌ O usuário já tem um canal da Twitch registrado: **{data['streamers'][interaction.guild.id][twitch_user_id]['twitch_username']}**.", ephemeral=True)
        return

    data['streamers'][interaction.guild.id][twitch_user_id] = {
        "twitch_username": nome_twitch.lower(),
        "discord_user_id": twitch_user_id
    }
    
    success = await set_cached_data(data, bot.drive_service)
    
    if success:
        await interaction.followup.send(f"✅ Streamer **{nome_twitch}** adicionado para monitoramento.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Erro ao salvar os dados. Tente novamente mais tarde.", ephemeral=True)

@bot.tree.command(name="remover_twitch", description="Remove um streamer da Twitch do monitoramento.")
@app_commands.describe(nome_twitch="O nome de usuário da Twitch (ex: monark)")
async def remover_twitch(interaction: discord.Interaction, nome_twitch: str):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    
    if not bot.drive_service:
        await interaction.followup.send("❌ Serviço do Google Drive não está disponível. Tente novamente mais tarde.", ephemeral=True)
        return
        
    data = await get_cached_data(bot.drive_service)
    
    if interaction.guild.id not in data['streamers']:
        await interaction.followup.send(f"❌ Nenhum streamer da Twitch registrado neste servidor.", ephemeral=True)
        return
    
    found_user_id = None
    for user_id, config in data['streamers'][interaction.guild.id].items():
        if config['twitch_username'].lower() == nome_twitch.lower():
            found_user_id = user_id
            break

    if found_user_id:
        del data['streamers'][interaction.guild.id][found_user_id]
        
        success = await set_cached_data(data, bot.drive_service)
        
        if success:
            await interaction.followup.send(f"✅ Streamer **{nome_twitch}** removido do monitoramento.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Erro ao salvar os dados. Tente novamente mais tarde.", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Streamer **{nome_twitch}** não encontrado na lista.", ephemeral=True)

@bot.tree.command(name="listar_alvos", description="Lista todos os streamers e canais monitorados.")
async def listar_alvos(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    data = await get_cached_data(bot.drive_service)
    output = "## 🎯 Alvos de Monitoramento\n\n"
    
    twitch_output = []
    
    if interaction.guild.id in data['streamers']:
        for _, config in data['streamers'][interaction.guild.id].items():
            member = interaction.guild.get_member(int(config.get("discord_user_id"))) if config.get("discord_user_id") else None
            twitch_output.append(
                f"**Plataforma:** Twitch\n"
                f"**Usuário:** {config['twitch_username']}\n"
                f"**Vinculado a:** {member.mention if member else 'Desconhecido'}\n"
            )

    if twitch_output:
        output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
    else:
        output += "Nenhum alvo encontrado no sistema."

    await interaction.followup.send(content=output, ephemeral=True)


@bot.tree.command(name="status", description="Mostra o status do T-800")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uptime = datetime.now() - bot.start_time
    data = await get_cached_data(bot.drive_service)
    
    twitch_count = sum(len(g) for g in data.get("streamers", {}).values())
    
    await interaction.followup.send(
        content=(
            f"**🤖 STATUS DO T-800**\n"
            f"⏱ **Tempo de atividade:** {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m\n"
            f"🌐 **Servidores conectados:** {len(bot.guilds)}\n"
            f"🎯 **Alvos monitorados (Twitch):** {twitch_count}\n"
        ),
        ephemeral=True
    )
