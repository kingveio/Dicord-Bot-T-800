import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import asyncio
from data_manager import get_data, save_data
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI

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
        self.twitch_api: Optional[TwitchAPI] = None
        self.youtube_api: Optional[YouTubeAPI] = None

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
            logger.error(f"❌ Falha ao sincronizar comandos. Alerta: {e}")

    bot.system_ready = True
    logger.info(f"🤖 T-800 ONLINE | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")

    for guild in bot.guilds:
        await ensure_live_role(guild)

    if not monitor_streams.is_running():
        monitor_streams.start()

# ========== FUNÇÕES AUXILIARES ========== #
async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante que o cargo 'AO VIVO' existe no servidor."""
    try:
        if role := discord.utils.get(guild.roles, name=bot.live_role):
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
            return role
        else:
            logger.warning(f"⚠️ Sem permissão para criar cargo em {guild.name}. Alerta: Falha na operação.")
            return None
    except Exception as e:
        logger.error(f"❌ Erro em {guild.name}: {e}. Alerta: Falha na operação.")
        return None

# ========== TAREFA PERIÓDICA ========== #
@tasks.loop(minutes=1)
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
            youtube_channels = list(data["monitored_users"]["youtube"].keys())
            
            for channel_name in youtube_channels:
                user_info = data["monitored_users"]["youtube"].get(channel_name.lower())
                if not user_info: continue

                guild = bot.get_guild(user_info.get("guild_id"))
                member = guild.get_member(user_info.get("added_by")) if guild else None
                if not member: continue
                
                live_role = discord.utils.get(guild.roles, name=bot.live_role)
                if not live_role: continue
                
                # A API do YouTube espera o channel_id. Assumimos que o nome armazenado é o ID.
                is_live = await bot.youtube_api.check_live_status(channel_name)
                
                if is_live:
                    if live_role not in member.roles:
                        await member.add_roles(live_role, reason="Streamer está ao vivo no YouTube")
                        logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (YouTube). Missão concluída.")
                else:
                    if live_role in member.roles:
                        await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                        logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (YouTube). Missão concluída.")

    except Exception as e:
        logger.error(f"❌ Falha no monitoramento: {e}. Alerta: Falha na operação.")

# ========== COMANDOS DE TEXTO (PREFIXO !) ========== #
@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Sincroniza os comandos (apenas para o dono do bot)."""
    try:
        await bot.tree.sync()
        await ctx.send("✅ Comandos sincronizados globalmente! Missão concluída.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {e}. Alerta: Falha na operação.")

# ========== COMANDOS DE APLICAÇÃO (SLASH) ========== #
@bot.tree.command(name="status", description="Mostra o status do T-800")
async def status(interaction: discord.Interaction):
    """Mostra informações do sistema."""
    await interaction.response.defer(ephemeral=True)
    uptime = datetime.now() - bot.start_time
    data = await get_data()
    await interaction.edit_original_response(
        content=(
            f"**🤖 STATUS DO T-800**\n"
            f"⏱ **Tempo de atividade:** `{str(uptime).split('.')[0]}`\n"
            f"📡 **Servidores ativos:** `{len(bot.guilds)}`\n"
            f"👀 **Alvos monitorados:** `Twitch: {len(data['monitored_users']['twitch'])} | YouTube: {len(data['monitored_users']['youtube'])}`"
        )
    )

@bot.tree.command(name="adicionar", description="Adiciona um streamer para monitoramento")
@app_commands.describe(plataforma="Plataforma (twitch/youtube)", nome="Nome do streamer/canal")
@app_commands.choices(plataforma=[
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube")
])
async def adicionar_streamer(interaction: discord.Interaction, plataforma: str, nome: str):
    """Adiciona um streamer à lista de monitoramento."""
    try:
        await interaction.response.defer(ephemeral=True)
        data = await get_data()
        plataforma = plataforma.lower()
        
        if plataforma not in ["twitch", "youtube"]:
            return await interaction.edit_original_response(content="❌ Plataforma inválida! Alerta: Falha na operação.")

        if nome.lower() in data["monitored_users"][plataforma]:
            return await interaction.edit_original_response(
                content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
            )

        data["monitored_users"][plataforma][nome.lower()] = {
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat(),
            "guild_id": interaction.guild.id
        }
        await save_data(bot.drive_service)

        await interaction.edit_original_response(
            content=f"✅ **{nome}** adicionado ao sistema. Missão concluída."
        )
    except Exception as e:
        await interaction.edit_original_response(
            content=f"❌ Erro ao adicionar alvo: {e}. Alerta: Falha na operação."
        )
        
@bot.tree.command(name="listar", description="Mostra a lista de alvos monitorados")
async def listar_streamers(interaction: discord.Interaction):
    """Exibe a lista de usuários monitorados."""
    await interaction.response.defer(ephemeral=True)
    data = await get_data()
    
    embed = discord.Embed(
        title="👥 Lista de Alvos Monitorados",
        description="Dados recuperados com sucesso.",
        color=discord.Color.blue()
    )
    
    twitch_list = []
    for streamer, info in data["monitored_users"]["twitch"].items():
        member = interaction.guild.get_member(info.get("added_by"))
        twitch_list.append(
            f"**Canal:** `{streamer}`\n"
            f"**Vinculado a:** `{member.name if member else 'Desconhecido'}`\n"
        )
    
    youtube_list = []
    for channel, info in data["monitored_users"]["youtube"].items():
        member = interaction.guild.get_member(info.get("added_by"))
        youtube_list.append(
            f"**Canal:** `{channel}`\n"
            f"**Vinculado a:** `{member.name if member else 'Desconhecido'}`\n"
        )
        
    embed.add_field(
        name="Plataforma: Twitch",
        value="\n".join(twitch_list) if twitch_list else "Nenhum alvo monitorado.",
        inline=False
    )
    
    embed.add_field(
        name="Plataforma: YouTube",
        value="\n".join(youtube_list) if youtube_list else "Nenhum alvo monitorado.",
        inline=False
    )
    
    await interaction.edit_original_response(embed=embed)


# ========== INICIALIZAÇÃO ========== #
async def setup():
    """Configurações iniciais do bot."""
    try:
        data = await get_data()
        if not data:
            await save_data()
    except Exception as e:
        logger.error(f"❌ Falha ao carregar dados: {e}. Alerta: Falha na operação.")

@bot.event
async def setup_hook():
    await setup()
