import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import asyncio
from data_manager import get_data, save_data

# ========== CONFIGURAÇÃO INICIAL ========== #
# Configuração do logger
logger = logging.getLogger("T-800")

# Configuração das Intents do Discord
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Classe principal do Bot
class T800Bot(commands.Bot):
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
        self.system_ready = False
        self.twitch_api = None
        self.youtube_api = None
        self.drive_service = None

# Inicialização do Bot
bot = T800Bot()

# ========== EVENTOS ========== #
@bot.event
async def on_ready():
    """Evento quando o bot está pronto para uso."""
    try:
        # Sincroniza os comandos a cada inicialização para garantir que estejam atualizados.
        await bot.tree.sync()
        logger.info("✅ Missão: Comandos sincronizados com sucesso!")
    except Exception as e:
        logger.error(f"❌ Falha ao sincronizar comandos: {e}")
    
    bot.system_ready = True
    check_live_status.start()
    logger.info(f"🤖 T-800 ONLINE. Missão iniciada em {bot.start_time.strftime('%d/%m/%Y às %H:%M')}")

@bot.event
async def on_disconnect():
    """Evento quando o bot é desconectado."""
    logger.info("❌ Desconectado do Discord.")
    check_live_status.stop()

# ========== TAREFAS EM LOOP ========== #
@tasks.loop(minutes=2)
async def check_live_status():
    """Verifica o status de todos os canais e streamers monitorados."""
    if not bot.system_ready:
        return

    logger.info("📡 Iniciando ciclo de monitoramento...")
    data = await get_data()
    monitored_users = data.get("monitored_users", {"twitch": {}, "youtube": {}})

    live_twitch_users = []
    if monitored_users["twitch"]:
        twitch_logins = list(monitored_users["twitch"].keys())
        twitch_status = await bot.twitch_api.check_live_status(twitch_logins)
        for user, is_live in twitch_status.items():
            if is_live:
                live_twitch_users.append(user)

    live_youtube_users = []
    if monitored_users["youtube"]:
        for channel, info in monitored_users["youtube"].items():
            is_live = await bot.youtube_api.is_channel_live(channel)
            if is_live:
                live_youtube_users.append(channel)

    for guild in bot.guilds:
        await update_live_roles(guild, live_twitch_users, live_youtube_users)

    await save_data(bot.drive_service)
    logger.info("✅ Ciclo de monitoramento concluído.")

async def update_live_roles(guild: discord.Guild, twitch_lives: List[str], youtube_lives: List[str]):
    """Adiciona ou remove o cargo 'AO VIVO' para os membros."""
    live_role_obj = discord.utils.get(guild.roles, name=bot.live_role)
    if not live_role_obj:
        try:
            live_role_obj = await guild.create_role(name=bot.live_role, reason="Cargo para streamers ao vivo")
            logger.info(f"🆕 Cargo '{bot.live_role}' criado no servidor '{guild.name}'")
        except discord.Forbidden:
            logger.error(f"❌ Não foi possível criar o cargo '{bot.live_role}' no servidor '{guild.name}'. Verifique as permissões.")
            return

    all_monitored = {}
    data = await get_data()
    all_monitored.update(data["monitored_users"]["twitch"])
    all_monitored.update(data["monitored_users"]["youtube"])

    for channel, info in all_monitored.items():
        member = guild.get_member(info.get("added_by"))
        if not member:
            continue
        
        is_live = channel in twitch_lives or channel in youtube_lives
        has_role = live_role_obj in member.roles

        if is_live and not has_role:
            try:
                await member.add_roles(live_role_obj, reason="Streamer ao vivo")
                logger.info(f"➕ Cargo '{bot.live_role}' adicionado a {member.display_name}")
            except discord.Forbidden:
                logger.error(f"❌ Não foi possível adicionar o cargo a {member.display_name}. Verifique as permissões.")
        elif not is_live and has_role:
            try:
                await member.remove_roles(live_role_obj, reason="Streamer offline")
                logger.info(f"➖ Cargo '{bot.live_role}' removido de {member.display_name}")
            except discord.Forbidden:
                logger.error(f"❌ Não foi possível remover o cargo de {member.display_name}. Verifique as permissões.")

# ========== COMANDOS ========== #
@bot.tree.command(name="status", description="Exibe o status atual do sistema.")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = await get_data()
    monitored_count = len(data.get("monitored_users", {}).get("twitch", {})) + len(data.get("monitored_users", {}).get("youtube", {}))
    status_msg = f"**Status do T-800**\n" \
                 f"Online: {(datetime.now() - bot.start_time).total_seconds():.0f}s\n" \
                 f"Monitorando alvos: {monitored_count}"
    await interaction.followup.send(status_msg)

@bot.tree.command(name="adicionar", description="Adiciona um canal para monitoramento (Twitch/YouTube).")
@app_commands.describe(url="URL do canal")
async def add_target(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)
    platform = "youtube" if "youtube.com" in url or "youtu.be" in url else "twitch"

    if platform == "youtube":
        channel_id = await bot.youtube_api.get_channel_id_from_url(url)
        if not channel_id:
            await interaction.followup.send("❌ Falha na identificação do canal do YouTube. Verifique a URL.")
            return
        
        data = await get_data()
        data["monitored_users"]["youtube"][channel_id] = {"added_by": interaction.user.id}
        await save_data(bot.drive_service)
        await interaction.followup.send(f"✅ Canal do YouTube adicionado com sucesso para monitoramento.")

    elif platform == "twitch":
        username = url.split('/')[-1]
        if not await bot.twitch_api.validate_username(username):
            await interaction.followup.send("❌ Falha na identificação do streamer da Twitch. Verifique a URL.")
            return
        
        data = await get_data()
        data["monitored_users"]["twitch"][username.lower()] = {"added_by": interaction.user.id}
        await save_data(bot.drive_service)
        await interaction.followup.send(f"✅ Streamer da Twitch adicionado com sucesso para monitoramento.")

@bot.tree.command(name="listar", description="Lista os canais e streamers monitorados.")
async def list_targets(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = await get_data()
    
    output = "🤖 **RELATÓRIO DE ALVOS**\n\n"
    
    twitch_output = []
    for streamer, info in data["monitored_users"]["twitch"].items():
        member = interaction.guild.get_member(info.get("added_by"))
        twitch_output.append(
            f"**Plataforma:** Twitch\n"
            f"**Nome do canal:** {streamer}\n"
            f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
        )

    youtube_output = []
    for channel, info in data["monitored_users"]["youtube"].items():
        member = interaction.guild.get_member(info.get("added_by"))
        youtube_output.append(
            f"**Plataforma:** YouTube\n"
            f"**ID do canal:** {channel}\n"
            f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
        )

    if twitch_output or youtube_output:
        output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
        output += "--- YouTube ---\n" + "\n".join(youtube_output)
    else:
        output += "Nenhum alvo encontrado no sistema."

    await interaction.edit_original_response(content=output)

@bot.tree.command(name="teste_live", description="Testa a verificação de live do YouTube com um ID.")
@app_commands.describe(channel_id="ID do canal do YouTube")
async def test_live(interaction: discord.Interaction, channel_id: str):
    await interaction.response.defer(ephemeral=True)
    is_live = await bot.youtube_api.is_channel_live(channel_id)
    if is_live:
        await interaction.followup.send(f"✅ O canal com ID {channel_id} está ao vivo!")
    else:
        await interaction.followup.send(f"❌ O canal com ID {channel_id} não está ao vivo.")
