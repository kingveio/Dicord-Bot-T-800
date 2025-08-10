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

# Configuração das Intents, com a função de voz desabilitada
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = False  # **CORREÇÃO:** Desabilita a voz para remover o aviso PyNaCl

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
        self.youtube_api: Optional[YouTubeAPI] = None
        self.drive_service = None
        self.guild_live_roles: Dict[int, Optional[discord.Role]] = {}

bot = StreamBot()

# ========== EVENTOS ========== #
@bot.event
async def on_ready():
    """Evento quando o bot está pronto para uso."""
    logger.info(f"🤖 T-800 ONLINE | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} comandos sincronizados.")
    except Exception as e:
        logger.error(f"❌ Falha ao sincronizar comandos: {e}")
    
    for guild in bot.guilds:
        await ensure_live_role(guild)

    if not monitor_streams.is_running():
        monitor_streams.start()

# ========== FUNÇÕES AUXILIARES ========== #
async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante que o cargo 'AO VIVO' existe no servidor."""
    if guild.id in bot.guild_live_roles:
        role = bot.guild_live_roles[guild.id]
        if role:
            return role
    try:
        if role := discord.utils.get(guild.roles, name=bot.live_role):
            bot.guild_live_roles[guild.id] = role
            return role
        if guild.me.guild_permissions.manage_roles:
            role = await guild.create_role(
                name=bot.live_role,
                color=discord.Color.red(),
                hoist=True,
                mentionable=True,
                reason="Monitoramento de streams T-800"
            )
            logger.info(f"✅ Cargo '{bot.live_role}' criado em {guild.name}. Objetivo concluído.")
            bot.guild_live_roles[guild.id] = role
            return role
        else:
            logger.warning(f"⚠️ Sem permissão para criar cargo em {guild.name}. Alerta: Falha na operação.")
            bot.guild_live_roles[guild.id] = None
            return None
    except Exception as e:
        logger.error(f"❌ Erro em {guild.name}: {e}. Alerta: Falha na operação.")
        bot.guild_live_roles[guild.id] = None
        return None

# ========== TAREFA PERIÓDICA ========== #
@tasks.loop(minutes=5)
async def monitor_streams():
    """Verifica periodicamente os streamers monitorados."""
    logger.info("🔍 Análise de alvos iniciada...")
    try:
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        data = await get_cached_data(bot.drive_service)
        if not data:
            logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
            return

        # Monitorar Twitch
        if bot.twitch_api:
            all_streamers_to_check = set()
            for streamers in data.get("streamers", {}).values():
                all_streamers_to_check.update(streamers.keys())
            
            if all_streamers_to_check:
                live_streamers_data = await bot.twitch_api.get_live_streams(list(all_streamers_to_check))
                live_streamers = {stream["user_login"].lower() for stream in live_streamers_data}
                
                for guild_id_str, streamers_map in data["streamers"].items():
                    guild = bot.get_guild(int(guild_id_str))
                    if not guild: continue
                    live_role = await ensure_live_role(guild)
                    if not live_role: continue

                    for twitch_name, discord_id in streamers_map.items():
                        member = guild.get_member(int(discord_id))
                        if not member: continue
                        
                        is_live = twitch_name in live_streamers
                        has_role = live_role in member.roles
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role, reason="Streamer está ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (Twitch). Missão concluída.")
                        elif not is_live and has_role:
                            await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (Twitch). Missão concluída.")

        # Monitorar YouTube
        if bot.youtube_api:
            for guild_id_str, channels_map in data.get("youtube_channels", {}).items():
                guild = bot.get_guild(int(guild_id_str))
                if not guild: continue
                live_role = await ensure_live_role(guild)
                if not live_role: continue

                for youtube_id, config in channels_map.items():
                    discord_id = config.get("discord_user_id")
                    if not discord_id: continue

                    member = guild.get_member(int(discord_id))
                    if not member: continue
                    
                    is_live = await bot.youtube_api.is_channel_live(youtube_id)
                    has_role = live_role in member.roles
                    
                    if is_live and not has_role:
                        await member.add_roles(live_role, reason="Streamer está ao vivo no YouTube")
                        logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (YouTube). Missão concluída.")
                    elif not is_live and has_role:
                        await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                        logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (YouTube). Missão concluída.")

    except Exception as e:
        logger.error(f"❌ Falha no monitoramento: {e}. Alerta: Falha na operação.")


# ========== COMANDOS DE APLICAÇÃO (SLASH) ========== #

@bot.tree.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento")
@app_commands.describe(
    nome_twitch="Nome de usuário da Twitch (ex: alanzoka)",
    usuario_discord="O usuário do Discord a ser vinculado"
)
@app_commands.checks.has_permissions(administrator=True)
async def adicionar_twitch(
    interaction: discord.Interaction,
    nome_twitch: str,
    usuario_discord: discord.Member
):
    await interaction.response.defer(ephemeral=True)
    try:
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        data = await get_cached_data(bot.drive_service)
        guild_id = str(interaction.guild.id)
        
        if guild_id not in data.get("streamers", {}):
            data["streamers"][guild_id] = {}

        if nome_twitch.lower() in data["streamers"][guild_id]:
            return await interaction.followup.send(f"⚠️ {nome_twitch} já é um alvo na Twitch! Alerta: Falha na operação.", ephemeral=True)

        data["streamers"][guild_id][nome_twitch.lower()] = str(usuario_discord.id)
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        await set_cached_data(data, bot.drive_service)

        await interaction.followup.send(
            f"✅ **{nome_twitch}** adicionado ao sistema e vinculado a {usuario_discord.mention}. Missão concluída.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar alvo Twitch: {e}. Alerta: Falha na operação.")
        await interaction.followup.send("❌ Erro ao adicionar alvo Twitch. Alerta: Falha na operação.", ephemeral=True)


@bot.tree.command(name="adicionar_youtube", description="Adiciona um canal do YouTube para monitoramento")
@app_commands.describe(
    url_canal="URL do canal do YouTube",
    usuario_discord="O usuário do Discord a ser vinculado (opcional)"
)
@app_commands.checks.has_permissions(administrator=True)
async def adicionar_youtube(
    interaction: discord.Interaction,
    url_canal: str,
    usuario_discord: Optional[discord.Member] = None
):
    await interaction.response.defer(ephemeral=True)
    try:
        youtube_id = await bot.youtube_api.get_channel_id_from_url(url_canal)
        if not youtube_id:
            return await interaction.followup.send("❌ Não foi possível encontrar o ID do canal do YouTube. Verifique a URL.", ephemeral=True)

        # **CORREÇÃO:** Adiciona o drive_service como argumento
        data = await get_cached_data(bot.drive_service)
        guild_id = str(interaction.guild.id)
        
        if guild_id not in data.get("youtube_channels", {}):
            data["youtube_channels"][guild_id] = {}
        
        if youtube_id in data["youtube_channels"][guild_id]:
            return await interaction.followup.send("⚠️ Este canal do YouTube já é um alvo! Alerta: Falha na operação.", ephemeral=True)

        data["youtube_channels"][guild_id][youtube_id] = {
            "discord_user_id": str(usuario_discord.id) if usuario_discord else None
        }
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        await set_cached_data(data, bot.drive_service)
        
        await interaction.followup.send(
            f"✅ Canal do YouTube com ID `{youtube_id}` adicionado ao sistema. Missão concluída.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar alvo YouTube: {e}. Alerta: Falha na operação.")
        await interaction.followup.send("❌ Erro ao adicionar alvo YouTube. Alerta: Falha na operação.", ephemeral=True)


@bot.tree.command(name="remover_twitch", description="Remove um streamer da Twitch do monitoramento")
@app_commands.describe(nome_twitch="Nome do streamer da Twitch")
@app_commands.checks.has_permissions(administrator=True)
async def remover_twitch(interaction: discord.Interaction, nome_twitch: str):
    await interaction.response.defer(ephemeral=True)
    try:
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        data = await get_cached_data(bot.drive_service)
        guild_id = str(interaction.guild.id)

        if guild_id not in data.get("streamers", {}) or nome_twitch.lower() not in data["streamers"][guild_id]:
            return await interaction.followup.send(
                f"⚠️ O streamer `{nome_twitch}` não está na lista de alvos! Alerta: Falha na operação.",
                ephemeral=True
            )

        discord_id = data["streamers"][guild_id].pop(nome_twitch.lower())
        # **CORREÇÃO:** Adiciona o drive_service como argumento
        await set_cached_data(data, bot.drive_service)

        member = interaction.guild.get_member(int(discord_id))
        if member:
            live_role = await ensure_live_role(interaction.guild)
            if live_role and live_role in member.roles:
                await member.remove_roles(live_role)
        
        await interaction.followup.send(
            f"✅ Streamer `{nome_twitch}` removido do sistema. Missão concluída.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"❌ Erro ao remover alvo Twitch: {e}. Alerta: Falha na operação.")
        await interaction.followup.send("❌ Erro ao remover alvo Twitch. Alerta: Falha na operação.", ephemeral=True)


@bot.tree.command(name="remover_youtube", description="Remove um canal do YouTube do monitoramento")
@app_commands.describe(url_canal="URL ou ID do Canal do YouTube")
@app_commands.checks.has_permissions(administrator=True)
async def remover_youtube(interaction: discord.Interaction, url_canal: str):
    await interaction.response.defer(ephemeral=True)
    try:
        youtube_id = await bot.youtube_api.get_channel_id_from_url(url_canal)
        if not youtube_id:
            youtube_id = url_canal # Tenta o próprio input como ID se a conversão falhar

        # **CORREÇÃO:** Adiciona o drive_service como argumento
        data = await get_cached_data(bot.drive_service)
        guild_id = str(interaction.guild.id)
        
        if youtube_id in data.get("youtube_channels", {}).get(guild_id, {}):
            del data["youtube_channels"][guild_id][youtube_id]
            # **CORREÇÃO:** Adiciona o drive_service como argumento
            await set_cached_data(data, bot.drive_service)
            await interaction.followup.send(
                f"✅ Canal do YouTube removido do sistema. Missão concluída.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ O canal `{url_canal}` não está na lista de alvos! Alerta: Falha na operação.",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"❌ Erro ao remover alvo YouTube: {e}. Alerta: Falha na operação.")
        await interaction.followup.send("❌ Erro ao remover alvo YouTube. Alerta: Falha na operação.", ephemeral=True)


@bot.tree.command(name="listar_alvos", description="Mostra a lista de alvos monitorados")
async def listar_alvos(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    # **CORREÇÃO:** Adiciona o drive_service como argumento
    data = await get_cached_data(bot.drive_service)
    
    output = "🤖 **RELATÓRIO DE ALVOS**\n\n"
    guild_id = str(interaction.guild.id)
    
    twitch_output = []
    for streamer, discord_id in data.get("streamers", {}).get(guild_id, {}).items():
        member = interaction.guild.get_member(int(discord_id))
        twitch_output.append(
            f"**Plataforma:** Twitch\n"
            f"**Nome do canal:** {streamer}\n"
            f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
        )

    youtube_output = []
    for channel_id, config in data.get("youtube_channels", {}).get(guild_id, {}).items():
        member = interaction.guild.get_member(int(config.get("discord_user_id"))) if config.get("discord_user_id") else None
        youtube_output.append(
            f"**Plataforma:** YouTube\n"
            f"**ID do canal:** {channel_id}\n"
            f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
        )

    if twitch_output or youtube_output:
        if twitch_output:
            output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
        if youtube_output:
            output += "--- YouTube ---\n" + "\n".join(youtube_output)
    else:
        output += "Nenhum alvo encontrado no sistema."

    await interaction.followup.send(content=output, ephemeral=True)


@bot.tree.command(name="status", description="Mostra o status do T-800")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uptime = datetime.now() - bot.start_time
    # **CORREÇÃO:** Adiciona o drive_service como argumento
    data = await get_cached_data(bot.drive_service)
    
    twitch_count = sum(len(g) for g in data.get("streamers", {}).values())
    youtube_count = sum(len(g) for g in data.get("youtube_channels", {}).values())
    
    await interaction.followup.send(
        content=(
            f"**🤖 STATUS DO T-800**\n"
            f"⏱ **Tempo de atividade:** `{str(uptime).split('.')[0]}`\n"
            f"📡 **Servidores ativos:** `{len(bot.guilds)}`\n"
            f"👀 **Alvos monitorados:** `Twitch: {twitch_count} | YouTube: {youtube_count}`"
        ),
        ephemeral=True
    )
