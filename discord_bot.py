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
                name="Exterminador do Futuro 2"
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
# Modals para Gerenciamento de Streamers (Twitch)
# --------------------------------------------------------------------------

class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_username = ui.TextInput(
        label="Nome na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )
    
    discord_user = ui.TextInput(
        label="Usuário do Discord",
        placeholder="Mencione ou digite o ID",
        min_length=3,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            twitch_name = str(self.twitch_username).lower().strip()
            if not re.match(r'^[a-z0-9_]{3,25}$', twitch_name):
                return await interaction.followup.send("❌ Nome da Twitch inválido!", ephemeral=True)

            discord_id = re.sub(r'\D', '', str(self.discord_user))
            if not discord_id.isdigit() or len(discord_id) < 17:
                return await interaction.followup.send("❌ ID do Discord inválido!", ephemeral=True)

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                return await interaction.followup.send("❌ Membro não encontrado no servidor!", ephemeral=True)
            
            data = await get_cached_data()
            guild_id = str(interaction.guild.id)

            if guild_id not in data["streamers"]:
                data["streamers"][guild_id] = {}

            if twitch_name in data["streamers"][guild_id]:
                return await interaction.followup.send("⚠️ Este streamer já está registrado!", ephemeral=True)

            data["streamers"][guild_id][twitch_name] = discord_id
            await set_cached_data(data, bot.drive_service)

            await interaction.followup.send(
                f"✅ {member.mention} vinculado ao streamer Twitch: `{twitch_name}`",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação.", ephemeral=True)

class RemoveStreamerModal(ui.Modal, title="Remover Streamer"):
    twitch_username = ui.TextInput(
        label="Nome na Twitch para remover",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            twitch_name = str(self.twitch_username).lower().strip()
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
            logger.error(f"Erro ao remover streamer: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao remover o streamer.", ephemeral=True)


# --------------------------------------------------------------------------
# Modals para Gerenciamento de Canais do YouTube
# --------------------------------------------------------------------------

class AddYoutubeChannelModal(ui.Modal, title="Adicionar Canal do YouTube"):
    youtube_url = ui.TextInput(
        label="URL do Canal do YouTube",
        placeholder="ex: youtube.com/@nome_do_canal",
        min_length=15
    )
    
    notification_channel_name = ui.TextInput(
        label="Canal do Discord",
        placeholder="Mencione ou digite o ID do canal",
        min_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            youtube_url = str(self.youtube_url).strip()
            notification_channel_id = re.sub(r'\D', '', str(self.notification_channel_name))
            
            if not notification_channel_id.isdigit():
                return await interaction.followup.send("❌ ID do canal do Discord inválido!", ephemeral=True)
            
            notification_channel = interaction.guild.get_channel(int(notification_channel_id))
            if not notification_channel:
                return await interaction.followup.send("❌ Canal do Discord não encontrado!", ephemeral=True)

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
                "notification_channel_id": notification_channel_id,
                "last_video_id": None
            }

            await set_cached_data(data, bot.drive_service)
            
            await interaction.followup.send(f"✅ Canal do YouTube adicionado com sucesso para o canal {notification_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao adicionar canal do YouTube: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação.", ephemeral=True)

class RemoveYoutubeChannelModal(ui.Modal, title="Remover Canal do YouTube"):
    youtube_url = ui.TextInput(
        label="URL ou ID do Canal do YouTube para remover",
        placeholder="ex: youtube.com/@nome_do_canal",
        min_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            youtube_url = str(self.youtube_url).strip()
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
            logger.error(f"Erro ao remover canal do YouTube: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao remover o canal.", ephemeral=True)


# --------------------------------------------------------------------------
# Comandos do Bot
# --------------------------------------------------------------------------

@bot.tree.command(name="streamers", description="Gerenciar streamers da Twitch")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True) # <<< ADICIONADO AQUI
        embed = discord.Embed(
            title="🎮 Gerenciamento de Streamers da Twitch",
            description="Use os botões abaixo para gerenciar os streamers",
            color=0x9147FF
        )
        view = ui.View()
        
        add_button = ui.Button(style=discord.ButtonStyle.green, label="Adicionar Streamer", emoji="➕")
        async def add_twitch_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(AddStreamerModal())
        add_button.callback = add_twitch_callback
        view.add_item(add_button)
        
        remove_button = ui.Button(style=discord.ButtonStyle.red, label="Remover Streamer", emoji="➖")
        async def remove_twitch_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(RemoveStreamerModal())
        remove_button.callback = remove_twitch_callback
        view.add_item(remove_button)

        list_button = ui.Button(style=discord.ButtonStyle.blurple, label="Listar Streamers", emoji="📋")
        async def list_twitch_callback(interaction: discord.Interaction):
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
        list_button.callback = list_twitch_callback
        view.add_item(list_button)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True) # <<< ALTERADO PARA followup.send()
        
    except Exception as e:
        logger.error(f"Erro no comando streamers: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao abrir o menu.", ephemeral=True)


@bot.tree.command(name="youtube", description="Gerenciar canais do YouTube")
@app_commands.checks.has_permissions(administrator=True)
async def youtube_command(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True) # <<< ADICIONADO AQUI
        embed = discord.Embed(
            title="▶️ Gerenciamento de Canais do YouTube",
            description="Use os botões abaixo para gerenciar os canais de notificação",
            color=0xFF0000
        )

        view = ui.View()
        
        add_button = ui.Button(style=discord.ButtonStyle.green, label="Adicionar Canal", emoji="➕")
        async def add_yt_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(AddYoutubeChannelModal())
        add_button.callback = add_yt_callback
        view.add_item(add_button)

        remove_button = ui.Button(style=discord.ButtonStyle.red, label="Remover Canal", emoji="➖")
        async def remove_yt_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(RemoveYoutubeChannelModal())
        remove_button.callback = remove_yt_callback
        view.add_item(remove_button)

        list_button = ui.Button(style=discord.ButtonStyle.blurple, label="Listar Canais", emoji="📋")
        async def list_yt_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True) # <<< ADICIONADO AQUI
            data = await get_cached_data()
            yt_channels = data["youtube_channels"].get(str(interaction.guild.id), {})
            
            if not yt_channels:
                return await interaction.followup.send("ℹ️ Nenhum canal do YouTube registrado neste servidor.", ephemeral=True)

            embed = discord.Embed(title="📋 Canais do YouTube Registrados", color=0xFF0000)
            for youtube_id, config in yt_channels.items():
                notification_channel = interaction.guild.get_channel(int(config["notification_channel_id"]))
                embed.add_field(
                    name=f"▶️ Canal ID: `{youtube_id}`",
                    value=f"Notificações em: {notification_channel.mention if notification_channel else '❌ Canal não encontrado'}",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True) # <<< ALTERADO PARA followup.send()
        list_button.callback = list_yt_callback
        view.add_item(list_button)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True) # <<< ALTERADO PARA followup.send()
    except Exception as e:
        logger.error(f"Erro no comando youtube: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao abrir o menu.", ephemeral=True)



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
    logger.info("🔍 Verificando streamers ao vivo...")
    data = await get_cached_data()
    all_streamers_to_check = set()
    for streamers in data["streamers"].values():
        all_streamers_to_check.update(streamers.keys())
    
    if not all_streamers_to_check:
        logger.info("ℹ️ Nenhum streamer registrado para verificar.")
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
                
                logger.info(f"Status do streamer {twitch_name} em {guild.name}: Está ao vivo? {is_live}. Tem o cargo? {has_role}.")
                
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
    logger.info("🎬 Verificando novos vídeos do YouTube...")
    data = await get_cached_data()
    
    all_channels_to_check = set()
    for guild_channels in data.get("youtube_channels", {}).values():
        all_channels_to_check.update(guild_channels.keys())

    if not all_channels_to_check:
        logger.info("ℹ️ Nenhum canal do YouTube registrado para verificar.")
        return

    # Mapear guild_id e canal_id para o último vídeo verificado
    last_checked_videos = {
        (guild_id, youtube_id): config.get("last_video_id")
        for guild_id, channels_map in data.get("youtube_channels", {}).items()
        for youtube_id, config in channels_map.items()
    }
    
    for guild_id_str, channels_map in data["youtube_channels"].items():
        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            continue
        
        for youtube_id, config in channels_map.items():
            try:
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
                    
                    await set_cached_data(data, bot.drive_service, persist=True)
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
