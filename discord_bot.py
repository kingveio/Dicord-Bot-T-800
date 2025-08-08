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
from drive_service import GoogleDriveService

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
twitch_api: TwitchAPI = None
drive_service: GoogleDriveService = None
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
    twitch_name = ui.TextInput(label="Nome na Twitch", placeholder="ex: alanzoka", min_length=3, max_length=25)
    discord_id = ui.TextInput(label="ID/Menção do Discord", placeholder="Digite o ID ou @usuário", min_length=3, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Apenas administradores podem usar este comando!", ephemeral=True)
                return

            twitch_username = self.twitch_name.value.lower().strip()
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message("❌ Nome inválido na Twitch! Use apenas letras, números e _", ephemeral=True)
                return

            if not await bot.twitch_api.validate_streamer(twitch_username):
                await interaction.response.send_message(f"❌ Streamer '{twitch_username}' não encontrado na Twitch!", ephemeral=True)
                return

            discord_input = self.discord_id.value.strip()
            discord_id = sanitize_discord_id(discord_input)
            if not discord_id:
                await interaction.response.send_message("❌ ID Discord inválido! Deve ter entre 17 e 19 dígitos.", ephemeral=True)
                return

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message("❌ Membro não encontrado no servidor!", ephemeral=True)
                return

            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            if guild_id not in data:
                data[guild_id] = {}

            if twitch_username in data[guild_id]:
                await interaction.response.send_message(f"⚠️ O streamer '{twitch_username}' já está vinculado!", ephemeral=True)
                return

            data[guild_id][twitch_username] = discord_id
            await set_cached_data(data, bot.drive_service, persist=True)

            await interaction.response.send_message(f"✅ {member.mention} vinculado ao Twitch: `{twitch_username}`", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}")
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
        await interaction.response.send_modal(AddStreamerModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get(str(interaction.guild.id), {})
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
                if selected in data_local.get(guild_id, {}):
                    del data_local[guild_id][selected]
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
        guild_streamers = data.get(str(interaction.guild.id), {})
        if not guild_streamers:
            await interaction.response.send_message("📭 Nenhum streamer vinculado neste servidor!", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(name=f"🔹 {twitch_user}", value=f"Discord: {member.mention if member else '🚨 Não encontrado'}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# Comandos do bot
@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message("**🎮 Painel de Streamers** - Escolha uma opção:", view=StreamersView(), ephemeral=True)

@bot.tree.command(name="status", description="Verifica o status do bot")
async def status_command(interaction: discord.Interaction):
    uptime = datetime.now() - START_TIME
    data = await get_cached_data()
    total_streamers = sum(len(g) for g in data.values())
    embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
    embed.add_field(name="⏱ Uptime", value=str(uptime).split('.')[0], inline=False)
    embed.add_field(name="📊 Streamers monitorados", value=f"{total_streamers} em {len(data)} servidores", inline=False)
    embed.add_field(name="🔄 Última verificação", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Task de verificação
async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Task de checagem iniciada")
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            if not isinstance(data, dict):
                logger.error(f"❌ Dados do cache não são um dicionário. Tipo: {type(data)}")
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            all_streamers = {s for g in data.values() for s in g.keys()}
            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            live_streamers = await bot.twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.items():
                guild = bot.get_guild(int(guild_id))
                if not guild: continue
                live_role = await get_or_create_live_role(guild)
                if live_role is None: continue
                
                for twitch_user, discord_id in streamers.items():
                    try:
                        member = guild.get_member(int(discord_id))
                        if not member: continue
                        is_live = twitch_user.lower() in live_streamers
                        has_role = live_role in member.roles
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            channel = guild.system_channel or discord.utils.get(guild.text_channels, name="geral")
                            if channel:
                                await channel.send(
                                    f"🎥 {member.mention} está ao vivo na Twitch como `{twitch_user}`!",
                                    allowed_mentions=discord.AllowedMentions(users=True)
                                )
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo para {twitch_user} ({discord_id}): {e}")

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

def run_discord_bot(token: str):
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Erro ao rodar bot: {e}")
