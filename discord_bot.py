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
                name="lives"
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
# Comandos da Twitch
# --------------------------------------------------------------------------

@bot.tree.command(name="twitch_add", description="Vincula um usuário do Discord a um streamer da Twitch")
@app_commands.describe(
    twitch_username="Nome de usuário da Twitch (ex: alanzoka)",
    discord_member="O membro do Discord para vincular"
)
@app_commands.checks.has_permissions(administrator=True)
async def twitch_add_command(
    interaction: discord.Interaction,
    twitch_username: str,
    discord_member: discord.Member
):
    await interaction.response.defer(ephemeral=True)
    try:
        twitch_name = twitch_username.lower().strip()
        if not re.match(r'^[a-z0-9_]{3,25}$', twitch_name):
            return await interaction.followup.send("❌ Nome da Twitch inválido!", ephemeral=True)

        data = await get_cached_data()
        guild_id = str(interaction.guild.id)
        discord_id = str(discord_member.id)

        if guild_id not in data["streamers"]:
            data["streamers"][guild_id] = {}

        if twitch_name in data["streamers"][guild_id]:
            return await interaction.followup.send("⚠️ Este streamer já está registrado!", ephemeral=True)

        data["streamers"][guild_id][twitch_name] = discord_id
        await set_cached_data(data, bot.drive_service)

        await interaction.followup.send(
            f"✅ {discord_member.mention} vinculado ao streamer Twitch: `{twitch_name}`",
            ephemeral=True
        )
            
    except Exception as e:
        logger.error(f"Erro no comando twitch_add: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação.", ephemeral=True)


@bot.tree.command(name="twitch_remove", description="Remove um streamer da Twitch")
@app_commands.describe(
    twitch_username="Nome de usuário da Twitch para remover (ex: alanzoka)"
)
@app_commands.checks.has_permissions(administrator=True)
async def twitch_remove_command(
    interaction: discord.Interaction,
    twitch_username: str
):
    await interaction.response.defer(ephemeral=True)
    try:
        twitch_name = twitch_username.lower().strip()
        data = await get_cached_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in data["streamers"] or twitch_name not in data["streamers"][guild_id]:
            return await interaction.followup.send(
                f"⚠️ O streamer `{twitch_name}` não está registrado.",
                ephemeral=True
            )

        discord_id = data["streamers"][guild_id].pop(twitch_name)
        await set_cached_data(data, bot.drive_service)

        member = interaction.guild.get_member(int(discord_id))
        if member:
            live_role = await get_or_create_live_role(interaction.guild)
            if live_role and live_role in member.roles:
                await member.remove_roles(live_role)
            
        await interaction.followup.send(
            f"✅ O streamer `{twitch_name}` foi removido com sucesso.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Erro no comando twitch_remove: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao remover o streamer.", ephemeral=True)


@bot.tree.command(name="twitch_list", description="Lista streamers registrados")
@app_commands.checks.has_permissions(administrator=True)
async def twitch_list_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild.id)
    data = await get_cached_data()
    streamers_list = data["streamers"].get(guild_id, {})
    if not streamers_list:
        return await interaction.followup.send("ℹ️ Nenhum streamer registrado neste servidor.", ephemeral=True)
    
    embed = discord.Embed(title="📋 Streamers Registrados", color=0x9147FF)
    for twitch_name, discord_id in streamers_list.items():
        member = interaction.guild.get_member(int(discord_id))
        embed.add_field(
            name=f"🔹 {twitch_name}",
            value=f"Discord: {member.mention if member else '❌ Usuário não encontrado'}",
            inline=False
        )
    await interaction.followup.send(embed=embed, ephemeral=True)

# --------------------------------------------------------------------------
# Comandos do YouTube
# --------------------------------------------------------------------------

@bot.tree.command(name="youtube_add", description="Adiciona um canal do YouTube para notificar novos vídeos e lives")
@app_commands.describe(
    youtube_url="URL do canal do YouTube (ex: https://www.youtube.com/@nome_do_canal)",
    notification_channel="O canal do Discord para enviar as notificações",
    discord_member="O membro do Discord para dar o cargo 'Ao Vivo' (opcional)"
)
@app_commands.checks.has_permissions(administrator=True)
async def youtube_add_command(
    interaction: discord.Interaction,
    youtube_url: str,
    notification_channel: discord.TextChannel,
    discord_member: Optional[discord.Member] = None
):
    await interaction.response.defer(ephemeral=True)
    try:
        if not youtube_url.startswith(("http://", "https://")):
            youtube_url = f"https://{youtube_url}"
        
        youtube_id = await bot.youtube_api.get_channel_id_from_url(youtube_url)
        if not youtube_id:
            return await interaction.followup.send("❌ Não foi possível encontrar o ID do canal do YouTube a partir da URL fornecida.", ephemeral=True)

        data = await get_cached_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in data.get("youtube_channels", {}):
            data["youtube_channels"][guild_id] = {}
        
        if youtube_id in data["youtube_channels"][guild_id]:
            return await interaction.followup.send("⚠️ Este canal do YouTube já está registrado!", ephemeral=True)

        data["youtube_channels"][guild_id][youtube_id] = {
            "notification_channel_id": str(notification_channel.id),
            "last_video_id": None,
            "discord_user_id": str(discord_member.id) if discord_member else None
        }

        await set_cached_data(data, bot.drive_service)
        
        await interaction.followup.send(f"✅ Canal do YouTube adicionado com sucesso para o canal {notification_channel.mention}!", ephemeral=True)
        
    except Exception as e:
        logger.error(f"Erro no comando youtube_add: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação.", ephemeral=True)


@bot.tree.command(name="youtube_remove", description="Remove um canal do YouTube")
@app_commands.describe(
    youtube_url="URL ou ID do Canal do YouTube para remover"
)
@app_commands.checks.has_permissions(administrator=True)
async def youtube_remove_command(interaction: discord.Interaction, youtube_url: str):
    await interaction.response.defer(ephemeral=True)
    try:
        youtube_id = await bot.youtube_api.get_channel_id_from_url(youtube_url)
        if not youtube_id:
            youtube_id = youtube_url # Tenta o próprio input como ID se a conversão falhar

        data = await get_cached_data()
        guild_id = str(interaction.guild.id)
        
        if youtube_id in data.get("youtube_channels", {}).get(guild_id, {}):
            del data["youtube_channels"][guild_id][youtube_id]
            await set_cached_data(data, bot.drive_service)
            await interaction.followup.send(
                f"✅ Canal do YouTube removido com sucesso.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ O canal `{youtube_url}` não está registrado neste servidor.",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Erro no comando youtube_remove: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao remover o canal.", ephemeral=True)


@bot.tree.command(name="youtube_list", description="Lista canais do YouTube registrados")
@app_commands.checks.has_permissions(administrator=True)
async def youtube_list_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = await get_cached_data()
    yt_channels = data["youtube_channels"].get(str(interaction.guild.id), {})
    
    if not yt_channels:
        return await interaction.followup.send("ℹ️ Nenhum canal do YouTube registrado neste servidor.", ephemeral=True)

    embed = discord.Embed(title="📋 Canais do YouTube Registrados", color=0xFF0000)
    for youtube_id, config in yt_channels.items():
        notification_channel = interaction.guild.get_channel(int(config["notification_channel_id"]))
        discord_member = interaction.guild.get_member(int(config.get("discord_user_id"))) if config.get("discord_user_id") else None
        
        member_info = f"Usuário vinculado: {discord_member.mention}" if discord_member else "Nenhum usuário vinculado"
        
        embed.add_field(
            name=f"▶️ Canal ID: `{youtube_id}`",
            value=f"Notificações em: {notification_channel.mention if notification_channel else '❌ Canal não encontrado'}\n"
                  f"{member_info}",
            inline=False
        )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="Verifica o status do bot")
async def status(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        uptime = datetime.now() - bot.start_time
        guild_count = len(bot.guilds)
        data = await get_cached_data()
        streamer_count = sum(len(g) for g in data["streamers"].values())
        yt_channel_count = sum(len(g) for g in data.get("youtube_channels", {}).values())

        embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
        embed.add_field(name="⏱ Tempo ativo", value=str(uptime).split('.')[0], inline=False)
        embed.add_field(name="📊 Servidores", value=guild_count, inline=True)
        embed.add_field(name="🎮 Streamers", value=streamer_count, inline=True)
        embed.add_field(name="▶️ Canais YouTube", value=yt_channel_count, inline=True)
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Erro no comando status: {e}")
        await interaction.followup.send("❌ Erro ao verificar status.", ephemeral=True)

# --------------------------------------------------------------------------
# Tarefas de Verificação (Loop)
# --------------------------------------------------------------------------

@tasks.loop(minutes=5)
async def check_live_streamers():
    logger.info("🔍 Verificando streamers da Twitch ao vivo...")
    data = await get_cached_data()
    all_streamers_to_check = set()
    for streamers in data["streamers"].values():
        all_streamers_to_check.update(streamers.keys())
    
    if not all_streamers_to_check:
        logger.info("ℹ️ Nenhum streamer da Twitch registrado para verificar.")
        return
    
    try:
        live_streamers_data = await bot.twitch_api.get_live_streams(list(all_streamers_to_check))
        live_streamers = {stream["user_login"].lower() for stream in live_streamers_data}
        logger.info(f"✅ API da Twitch retornou {len(live_streamers)} streamers ao vivo.")
    except Exception as e:
        logger.error(f"❌ Erro ao buscar lives da Twitch: {e}. A verificação será pulada.")
        return

    for guild_id_str, streamers_map in data["streamers"].items():
        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            continue
        live_role = await get_or_create_live_role(guild)
        if not live_role:
            continue
        
        for twitch_name, discord_id in streamers_map.items():
            try:
                member = guild.get_member(int(discord_id))
                if not member:
                    logger.warning(f"❌ Membro com ID {discord_id} não encontrado no servidor {guild.name}.")
                    continue
                
                is_live = twitch_name in live_streamers
                has_role = live_role in member.roles
                
                logger.info(f"Status do streamer da Twitch {twitch_name} em {guild.name}: Está ao vivo? {is_live}. Tem o cargo? {has_role}.")
                
                if is_live and not has_role:
                    await member.add_roles(live_role)
                    logger.info(f"➕ Cargo 'Ao Vivo' dado para {twitch_name} em {guild.name}")
                elif not is_live and has_role:
                    await member.remove_roles(live_role)
                    logger.info(f"➖ Cargo 'Ao Vivo' removido de {twitch_name} em {guild.name}")
                    
            except discord.Forbidden:
                logger.error(f"❌ Erro de permissão: o bot não pode gerenciar cargos para o membro {member.name} em {guild.name}. Verifique a hierarquia de cargos.")
            except Exception as e:
                logger.error(f"Erro inesperado ao atualizar cargo para {twitch_name} em {guild.name}: {e}")


@tasks.loop(minutes=10) # Frequência menor para a API do YouTube
async def check_youtube_channels():
    logger.info("🎬 Verificando novos vídeos e lives do YouTube...")
    data = await get_cached_data()
    
    if "youtube_channels" not in data or not data["youtube_channels"]:
        logger.info("ℹ️ Nenhum canal do YouTube registrado para verificar.")
        return

    for guild_id_str, channels_map in data["youtube_channels"].items():
        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            continue
        
        live_role = await get_or_create_live_role(guild)
        if not live_role:
            continue

        for youtube_id, config in channels_map.items():
            try:
                # ----------------------------------------
                # Lógica para notificação de novos vídeos
                # ----------------------------------------
                latest_video = await bot.youtube_api.get_latest_video(youtube_id)
                last_video_id = config.get("last_video_id")
                
                if latest_video and latest_video["id"] != last_video_id:
                    config["last_video_id"] = latest_video["id"]

                    notification_channel = guild.get_channel(int(config["notification_channel_id"]))
                    if notification_channel:
                        await notification_channel.send(
                            f"▶️ **NOVO VÍDEO NO YOUTUBE!**\n"
                            f"Título: **{latest_video['title']}**\n"
                            f"Assista agora: {latest_video['url']}"
                        )
                
                # ----------------------------------------
                # Lógica para cargo de "Ao Vivo"
                # ----------------------------------------
                discord_id = config.get("discord_user_id")
                if discord_id:
                    member = guild.get_member(int(discord_id))
                    if not member:
                        logger.warning(f"❌ Membro com ID {discord_id} vinculado ao canal do YouTube não encontrado.")
                        continue
                    
                    is_live = await bot.youtube_api.is_channel_live(youtube_id)
                    has_role = live_role in member.roles
                    
                    logger.info(f"Status do canal do YouTube {youtube_id} em {guild.name}: Está ao vivo? {is_live}. Tem o cargo? {has_role}.")

                    if is_live and not has_role:
                        await member.add_roles(live_role)
                        logger.info(f"➕ Cargo 'Ao Vivo' dado para o usuário do canal do YouTube {youtube_id} em {guild.name}")
                    elif not is_live and has_role:
                        await member.remove_roles(live_role)
                        logger.info(f"➖ Cargo 'Ao Vivo' removido do usuário do canal do YouTube {youtube_id} em {guild.name}")

                await set_cached_data(data, bot.drive_service)

            except Exception as e:
                logger.error(f"❌ Erro ao verificar o canal do YouTube {youtube_id}: {e}")


# --------------------------------------------------------------------------
# Funções de Setup e Eventos
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
            logger.warning(f"Sem permissões para criar cargo em {guild.name}")
            bot.guild_live_roles[guild.id] = None
            return None
        role = await guild.create_role(
            name=bot.live_role_name,
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True,
            reason="Cargo para streamers ao vivo"
        )
        try:
            await role.edit(position=guild.me.top_role.position - 1)
        except Exception as e:
            logger.debug(f"Não foi possível reposicionar o cargo em {guild.name}: {e}")
        bot.guild_live_roles[guild.id] = role
        return role
    except Exception as e:
        logger.error(f"Erro ao criar cargo em {guild.name}: {e}")
        bot.guild_live_roles[guild.id] = None
        return None

async def setup_live_roles_for_all_guilds():
    for guild in bot.guilds:
        await get_or_create_live_role(guild)

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"📊 Servidores: {len(bot.guilds)}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"🔄 {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar comandos: {e}")
    await setup_live_roles_for_all_guilds()
    if not check_live_streamers.is_running():
        check_live_streamers.start()
    if not check_youtube_channels.is_running():
        check_youtube_channels.start()

@bot.event
async def on_guild_join(guild):
    logger.info(f"➕ Entrou no servidor: {guild.name} (ID: {guild.id})")
    await get_or_create_live_role(guild)
