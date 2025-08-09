import os
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Optional

import discord
from discord.ext import commands
from discord import app_commands, ui

from data_manager import get_cached_data, set_cached_data

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="Streamers da Twitch")
)

START_TIME = datetime.now()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 55))
CHECK_TASK = None

class GuildConfig:
    def __init__(self, notification_channel_id: Optional[str] = None):
        self.notification_channel_id = notification_channel_id

async def get_or_create_live_role(guild: discord.Guild) -> Optional[discord.Role]:
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

class AddStreamerDiscordModal(ui.Modal, title="Vincular Usuário Discord"):
    def __init__(self, twitch_username: str):
        super().__init__()
        self.twitch_username = twitch_username
    
    discord_id = ui.TextInput(label="ID do Discord", placeholder="Digite o ID ou @mencione um usuário", min_length=3, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            discord_input = self.discord_id.value.strip()
            discord_id = sanitize_discord_id(discord_input)

            if not discord_id:
                await interaction.response.send_message("❌ ID do Discord inválido! Deve ter entre 17 e 19 dígitos.", ephemeral=True)
                return

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message("❌ Membro não encontrado no servidor!", ephemeral=True)
                return

            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            
            if guild_id not in data["streamers"]:
                data["streamers"][guild_id] = {}
            
            if guild_id not in data["configs"]:
                data["configs"][guild_id] = {}

            if self.twitch_username in data["streamers"][guild_id]:
                await interaction.response.send_message(f"⚠️ O streamer '{self.twitch_username}' já está vinculado!", ephemeral=True)
                return

            data["streamers"][guild_id][self.twitch_username] = discord_id
            await set_cached_data(data, bot.drive_service, persist=True)

            await interaction.response.send_message(f"✅ {member.mention} vinculado ao Twitch: `{self.twitch_username}`", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao vincular ID do Discord para {self.twitch_username}: {e}")
            await interaction.response.send_message("❌ Erro interno ao processar!", ephemeral=True)

class AddStreamerTwitchModal(ui.Modal, title="Adicionar Streamer Twitch"):
    twitch_name = ui.TextInput(label="Nome do Canal na Twitch", placeholder="ex: alanzoka", min_length=3, max_length=25)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            twitch_username = self.twitch_name.value.lower().strip()
            
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message("❌ Nome inválido na Twitch! Use apenas letras, números e _.", ephemeral=True)
                return

            await interaction.response.send_modal(AddStreamerDiscordModal(twitch_username))

        except Exception as e:
            logger.error(f"Erro ao processar nome da Twitch: {e}")
            await interaction.response.send_message("❌ Erro interno ao processar!", ephemeral=True)

class ConfigModal(ui.Modal, title="Configurar Canal de Notificações"):
    channel = ui.TextInput(label="ID do Canal ou #mencione", placeholder="Ex: #notificações ou 123456789012345678")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_input = self.channel.value.strip()
            channel_id = sanitize_discord_id(channel_input)
            
            if not channel_id:
                await interaction.response.send_message("❌ ID do canal inválido!", ephemeral=True)
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message("❌ Canal não encontrado!", ephemeral=True)
                return

            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            
            if guild_id not in data["configs"]:
                data["configs"][guild_id] = {}
            
            data["configs"][guild_id]["notification_channel_id"] = channel_id
            await set_cached_data(data, bot.drive_service, persist=True)

            await interaction.response.send_message(f"✅ Canal de notificações definido para {channel.mention}!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao configurar canal: {e}")
            await interaction.response.send_message("❌ Erro interno ao processar!", ephemeral=True)

class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este painel!", ephemeral=True)
            return False
        return True

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerTwitchModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get("streamers", {}).get(str(interaction.guild.id), {})
        if not guild_streamers:
            await interaction.response.send_message("❌ Nenhum streamer vinculado neste servidor!", ephemeral=True)
            return

        options = []
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            desc = f"Vinculado a: {member.display_name if member else 'Não encontrado'}"
            options.append(discord.SelectOption(label=streamer, description=desc, value=streamer))

        select = ui.Select(placeholder="Selecione um streamer para remover...", options=options, custom_id="select_remove_streamer")

        async def callback(inner_interaction: discord.Interaction):
            try:
                selected = select.values[0]
                data_local = await get_cached_data()
                guild_id = str(inner_interaction.guild.id)
                if selected in data_local.get("streamers", {}).get(guild_id, {}):
                    del data_local["streamers"][guild_id][selected]
                    await set_cached_data(data_local, bot.drive_service, persist=True)
                    await inner_interaction.response.send_message(f"✅ Streamer '{selected}' removido!", ephemeral=True)
                else:
                    await inner_interaction.response.send_message("❌ Streamer não encontrado (provavelmente já removido).", ephemeral=True)
            except Exception as e:
                logger.error(f"Erro no callback de remoção: {e}")
                await inner_interaction.response.send_message("❌ Erro ao remover streamer.", ephemeral=True)

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get("streamers", {}).get(str(interaction.guild.id), {})
        if not guild_streamers:
            await interaction.response.send_message("📭 Nenhum streamer vinculado neste servidor!", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(name=f"🔹 {twitch_user}", value=f"Discord: {member.mention if member else '🚨 Não encontrado'}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Configurar", style=discord.ButtonStyle.gray, emoji="⚙️", custom_id="configure")
    async def configure(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ConfigModal())

@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message("**🎮 Painel de Streamers** - Escolha uma opção:", view=StreamersView(), ephemeral=True)

@bot.tree.command(name="status", description="Verifica o status do bot")
async def status_command(interaction: discord.Interaction):
    uptime = datetime.now() - START_TIME
    data = await get_cached_data()
    total_streamers = sum(len(g) for g in data.get("streamers", {}).values())
    embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
    embed.add_field(name="⏱ Uptime", value=str(uptime).split('.')[0], inline=False)
    embed.add_field(name="📊 Streamers monitorados", value=f"{total_streamers} em {len(data.get('streamers', {}))} servidores", inline=False)
    embed.add_field(name="🔄 Última verificação", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="sync", description="Sincroniza os dados com o Google Drive")
@app_commands.checks.has_permissions(administrator=True)
async def sync_command(interaction: discord.Interaction):
    try:
        data = await get_cached_data()
        await set_cached_data(data, bot.drive_service, persist=True)
        await interaction.response.send_message("✅ Dados sincronizados com o Google Drive!", ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao sincronizar: {e}")
        await interaction.response.send_message("❌ Falha ao sincronizar com o Google Drive!", ephemeral=True)

async def get_notification_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    data = await get_cached_data()
    guild_id = str(guild.id)
    
    if guild_id in data.get("configs", {}):
        channel_id = data["configs"][guild_id].get("notification_channel_id")
        if channel_id:
            return guild.get_channel(int(channel_id))
    
    return guild.system_channel or discord.utils.get(guild.text_channels, name="geral")

async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Task de checagem iniciada")
    
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            if not isinstance(data, dict) or "streamers" not in data:
                logger.error(f"❌ Dados do cache inválidos. Tipo: {type(data)}")
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            all_streamers = {s for g in data.get("streamers", {}).values() for s in g.keys()}
            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            live_streamers = await bot.twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.get("streamers", {}).items():
                try:
                    guild = bot.get_guild(int(guild_id))
                    if not guild: continue
                    
                    live_role = await get_or_create_live_role(guild)
                    if live_role is None: continue
                    
                    notification_channel = await get_notification_channel(guild)
                    
                    for twitch_user, discord_id in streamers.items():
                        try:
                            member = guild.get_member(int(discord_id))
                            if not member: continue
                            
                            is_live = twitch_user.lower() in live_streamers
                            has_role = live_role in member.roles
                            
                            if is_live and not has_role:
                                await member.add_roles(live_role)
                                if notification_channel:
                                    await notification_channel.send(
                                        f"🎥 {member.mention} está ao vivo na Twitch como `{twitch_user}`!",
                                        allowed_mentions=discord.AllowedMentions(users=True)
                                    )
                            elif not is_live and has_role:
                                await member.remove_roles(live_role)
                        except Exception as e:
                            logger.error(f"Erro ao atualizar cargo para {twitch_user} ({discord_id}): {e}")
                except ValueError as ve:
                    logger.error(f"❌ Erro ao converter guild_id '{guild_id}' para int: {ve}")
                    continue

        except Exception as e:
            logger.error(f"Erro no verificador principal: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

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
