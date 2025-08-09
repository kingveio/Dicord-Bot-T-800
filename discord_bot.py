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
        self.drive_service = None
        self.guild_live_roles: Dict[int, Optional[discord.Role]] = {}

bot = StreamBot()

# --------------------------------------------------------------------------
# Modals para Adicionar e Remover Streamers
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
# Comandos do Bot
# --------------------------------------------------------------------------

@bot.tree.command(name="streamers", description="Gerenciar streamers")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    """Menu principal de gerenciamento de streamers"""
    try:
        embed = discord.Embed(
            title="🎮 Gerenciamento de Streamers",
            description="Use os botões abaixo para gerenciar os streamers",
            color=0x9147FF
        )
        
        view = ui.View()
        
        # Botão para Adicionar
        add_button = ui.Button(style=discord.ButtonStyle.green, label="Adicionar Streamer", emoji="➕")
        async def add_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(AddStreamerModal())
        add_button.callback = add_callback
        view.add_item(add_button)
        
        # Botão para Remover (NOVO)
        remove_button = ui.Button(style=discord.ButtonStyle.red, label="Remover Streamer", emoji="➖")
        async def remove_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(RemoveStreamerModal())
        remove_button.callback = remove_callback
        view.add_item(remove_button)

        # Botão para Listar
        list_button = ui.Button(style=discord.ButtonStyle.blurple, label="Listar Streamers", emoji="📋")
        async def list_callback(interaction: discord.Interaction):
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
        list_button.callback = list_callback
        view.add_item(list_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Erro no comando streamers: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao abrir o menu.", ephemeral=True)


@bot.tree.command(name="status", description="Verifica o status do bot")
async def status(interaction: discord.Interaction):
    """Mostra informações do bot"""
    try:
        await interaction.response.defer(ephemeral=True)
        uptime = datetime.now() - bot.start_time
        guild_count = len(bot.guilds)
        data = await get_cached_data()
        streamer_count = sum(len(g) for g in data["streamers"].values())
        embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
        embed.add_field(name="⏱ Tempo ativo", value=str(uptime).split('.')[0], inline=False)
        embed.add_field(name="📊 Servidores", value=guild_count, inline=True)
        embed.add_field(name="🎮 Streamers", value=streamer_count, inline=True)
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Erro no comando status: {e}")
        await interaction.followup.send("❌ Erro ao verificar status.", ephemeral=True)

# --------------------------------------------------------------------------
# Sistema de Cargos e Verificação de Lives
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
    except Exception as e:
        logger.error(f"❌ Erro ao buscar lives da Twitch: {e}")
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
                    continue
                is_live = twitch_name in live_streamers
                has_role = live_role in member.roles
                if is_live and not has_role:
                    await member.add_roles(live_role)
                    logger.info(f"➕ Cargo 'Ao Vivo' dado para {twitch_name} em {guild.name}")
                elif not is_live and has_role:
                    await member.remove_roles(live_role)
                    logger.info(f"➖ Cargo 'Ao Vivo' removido de {twitch_name} em {guild.name}")
            except Exception as e:
                logger.error(f"Erro ao atualizar cargo para {twitch_name} em {guild.name}: {e}")

# --------------------------------------------------------------------------
# Eventos do Bot
# --------------------------------------------------------------------------

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

@bot.event
async def on_guild_join(guild):
    logger.info(f"➕ Entrou no servidor: {guild.name} (ID: {guild.id})")
    await get_or_create_live_role(guild)
