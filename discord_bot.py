import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import asyncio
from data_manager import get_data, save_data # Corrigido: Importação absoluta

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
        self.synced = False
        self.twitch_api = None
        self.youtube_api = None

# Inicialização do Bot
bot = T800Bot()

# ========== EVENTOS ========== #
@bot.event
async def on_ready():
    """Evento quando o bot está pronto para uso."""
    if not bot.synced:
        try:
            await bot.tree.sync()
            for guild in bot.guilds:
                await bot.tree.sync(guild=guild)
            bot.synced = True
            logger.info("✅ Missão: Comandos sincronizados com sucesso!")
        except Exception as e:
            logger.error(f"❌ Falha ao sincronizar comandos: {e}")
    
    logger.info("✅ Sistema online e pronto para operar.")
    bot.system_ready = True
    monitor_streams.start()

@bot.event
async def on_member_update(before, after):
    """Monitora atualizações de membros para o cargo de AO VIVO."""
    live_role = discord.utils.get(after.guild.roles, name=bot.live_role)
    if live_role and live_role in before.roles and live_role not in after.roles:
        data = await get_data()
        
        # Verifica se o membro é um streamer da Twitch
        twitch_streamer_info = next(
            (info for name, info in data["monitored_users"]["twitch"].items() if info["added_by"] == after.id),
            None
        )
        if twitch_streamer_info:
            is_live_twitch = await bot.twitch_api.check_live_channels([twitch_streamer_info])
            if is_live_twitch.get(twitch_streamer_info.get("twitch_user_id")):
                await after.add_roles(live_role, reason="Remoção manual do cargo 'AO VIVO' detectada. Revertendo.")
                logger.warning(
                    f"⚠️ Ação manual no cargo de {after.name} revertida. Status: Alerta corrigido."
                )
        
        # Verifica se o membro é um streamer do YouTube
        youtube_streamer_info = next(
            (info for name, info in data["monitored_users"]["youtube"].items() if info["added_by"] == after.id),
            None
        )
        if youtube_streamer_info:
            is_live_youtube = await bot.youtube_api.check_live_status(youtube_streamer_info.get("youtube_channel_id"))
            if is_live_youtube:
                await after.add_roles(live_role, reason="Remoção manual do cargo 'AO VIVO' detectada. Revertendo.")
                logger.warning(
                    f"⚠️ Ação manual no cargo de {after.name} revertida. Status: Alerta corrigido."
                )

# ========== COMANDOS DE ADMINISTRAÇÃO ========== #
@bot.tree.command(name="adicionar", description="Adiciona um streamer para monitoramento")
@app_commands.describe(
    plataforma="Plataforma do canal (twitch, youtube)",
    nome="Nome do canal ou URL do YouTube",
    usuario="O usuário do Discord a ser vinculado"
)
@app_commands.choices(plataforma=[
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube")
])
async def adicionar_streamer(interaction: discord.Interaction, plataforma: str, nome: str, usuario: discord.Member):
    """Adiciona um streamer à lista de monitoramento."""
    try:
        await interaction.response.defer(ephemeral=True)
        data = await get_data()
        plataforma = plataforma.lower()

        if plataforma not in ["twitch", "youtube"]:
            return await interaction.edit_original_response(content="❌ Plataforma inválida! Alerta: Falha na operação.")

        # Lógica para adicionar Twitch
        if plataforma == "twitch":
            if nome.lower() in data["monitored_users"][plataforma]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
                )
            
            data["monitored_users"][plataforma][nome.lower()] = {
                "added_by": usuario.id,
                "added_at": datetime.now().isoformat(),
                "guild_id": interaction.guild.id
            }
            await save_data(bot.drive_service)
            await interaction.edit_original_response(
                content=f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
            )

        # Lógica para adicionar YouTube
        elif plataforma == "youtube":
            channel_id = await bot.youtube_api.get_channel_id(nome)
            if not channel_id:
                return await interaction.edit_original_response(
                    content=f"❌ Canal do YouTube '{nome}' não encontrado. Verifique a URL ou o nome. Alerta: Falha na operação."
                )
            
            if channel_id in data["monitored_users"][plataforma]:
                return await interaction.edit_original_response(
                    content=f"⚠️ O canal do YouTube já é um alvo! Alerta: Falha na operação."
                )
            
            data["monitored_users"][plataforma][channel_id] = {
                "added_by": usuario.id,
                "added_at": datetime.now().isoformat(),
                "guild_id": interaction.guild.id
            }
            await save_data(bot.drive_service)
            await interaction.edit_original_response(
                content=f"✅ **Canal do YouTube** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
            )

    except Exception as e:
        await interaction.edit_original_response(
            content=f"❌ Erro ao adicionar alvo: {e}. Alerta: Falha na operação."
        )

@bot.tree.command(name="remover", description="Remove um streamer do monitoramento")
@app_commands.describe(
    plataforma="Plataforma do canal (twitch, youtube)",
    nome="Nome do canal da Twitch ou Channel ID do YouTube"
)
@app_commands.choices(plataforma=[
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube")
])
async def remover_streamer(interaction: discord.Interaction, plataforma: str, nome: str):
    """Remove um streamer da lista de monitoramento."""
    try:
        await interaction.response.defer(ephemeral=True)
        data = await get_data()
        plataforma = plataforma.lower()

        if plataforma not in ["twitch", "youtube"]:
            return await interaction.edit_original_response(content="❌ Plataforma inválida! Alerta: Falha na operação.")

        if nome.lower() not in data["monitored_users"][plataforma]:
            return await interaction.edit_original_response(
                content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
            )

        del data["monitored_users"][plataforma][nome.lower()]
        await save_data(bot.drive_service)

        await interaction.edit_original_response(
            content=f"✅ **{nome}** removido do sistema. Missão concluída."
        )
    except Exception as e:
        await interaction.edit_original_response(
            content=f"❌ Erro ao remover alvo: {e}. Alerta: Falha na operação."
        )

@bot.tree.command(name="listar", description="Mostra a lista de alvos monitorados")
async def listar_streamers(interaction: discord.Interaction):
    """Exibe a lista de usuários monitorados."""
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
            f"**Nome do canal:** {channel}\n"
            f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
        )

    if twitch_output or youtube_output:
        output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
        output += "--- YouTube ---\n" + "\n".join(youtube_output)
    else:
        output += "Nenhum alvo encontrado no sistema."

    await interaction.edit_original_response(content=output)

# ========== TAREFAS DE MONITORAMENTO ========== #
@tasks.loop(minutes=3)
async def monitor_streams():
    """Verifica periodicamente os streamers monitorados."""
    if not bot.system_ready:
        return

    logger.info("🔍 Análise de alvos iniciada...")
    try:
        data = await get_data()
        if not data:
            logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
            return

        # Monitorar Twitch
        if data["monitored_users"]["twitch"]:
            streamers = list(data["monitored_users"]["twitch"].keys())
            live_status = await bot.twitch_api.check_live_channels(streamers)

            for streamer_name, is_live in live_status.items():
                user_info = data["monitored_users"]["twitch"].get(streamer_name.lower())
                if not user_info: continue

                guild = bot.get_guild(user_info.get("guild_id"))
                member = guild.get_member(user_info.get("added_by")) if guild else None
                if not member: continue

                live_role = discord.utils.get(guild.roles, name=bot.live_role)
                if not live_role: continue

                if is_live:
                    if live_role not in member.roles:
                        await member.add_roles(live_role, reason="Streamer está ao vivo")
                        logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (Twitch). Missão concluída.")
                else:
                    if live_role in member.roles:
                        await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                        logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (Twitch). Missão concluída.")

        # Monitorar YouTube
        if data["monitored_users"]["youtube"]:
            for channel_id, user_info in data["monitored_users"]["youtube"].items():
                is_live = await bot.youtube_api.check_live_status(channel_id)
                
                guild = bot.get_guild(user_info.get("guild_id"))
                member = guild.get_member(user_info.get("added_by")) if guild else None
                if not member: continue

                live_role = discord.utils.get(guild.roles, name=bot.live_role)
                if not live_role: continue

                if is_live:
                    if live_role not in member.roles:
                        await member.add_roles(live_role, reason="Streamer está ao vivo no YouTube")
                        logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (YouTube). Missão concluída.")
                else:
                    if live_role in member.roles:
                        await member.remove_roles(live_role, reason="Streamer não está mais ao vivo no YouTube")
                        logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (YouTube). Missão concluída.")

    except Exception as e:
        logger.error(f"❌ Falha no monitoramento: {e}. Alerta: Falha na operação.")
