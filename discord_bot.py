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
        self.synced = False
        self.twitch_api = None
        self.youtube_api = None
        self.drive_service = None

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
@tasks.loop(minutes=5)
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
        twitch_users = data["monitored_users"]["twitch"]
        if twitch_users and bot.twitch_api:
            streamers = list(twitch_users.keys())
            live_status = await bot.twitch_api.check_live_channels(streamers)
            
            for streamer_name, is_live in live_status.items():
                user_info = twitch_users.get(streamer_name.lower())
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
        youtube_users = data["monitored_users"]["youtube"]
        if youtube_users and bot.youtube_api:
            youtube_channels = list(youtube_users.keys())
            
            for channel_name in youtube_channels:
                user_info = youtube_users.get(channel_name.lower())
                if not user_info: continue

                guild = bot.get_guild(user_info.get("guild_id"))
                member = guild.get_member(user_info.get("added_by")) if guild else None
                if not member: continue
                
                live_role = discord.utils.get(guild.roles, name=bot.live_role)
                if not live_role: continue
                
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
@app_commands.describe(
    plataforma="Plataforma (twitch/youtube)", 
    nome="Nome do streamer/canal",
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

        if nome.lower() in data["monitored_users"][plataforma]:
            return await interaction.edit_original_response(
                content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
            )

        data["monitored_users"][plataforma][nome.lower()] = {
            "added_by": usuario.id,
            "added_at": datetime.now().isoformat(),
            "guild_id": interaction.guild.id
        }
        await save_data(data)

        await interaction.edit_original_response(
            content=f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
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
        if twitch_output:
            output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
        if youtube_output:
            output += "--- YouTube ---\n" + "\n".join(youtube_output)
    else:
        output += "Nenhum alvo encontrado no sistema."

    await interaction.edit_original_response(content=output)

# ========== INICIALIZAÇÃO ========== #
@bot.event
async def setup_hook():
    """Configurações iniciais do bot."""
    data = await get_data()
    if not data:
        # Se get_data retornar dados padrão, salva para criar o arquivo no Drive
        await save_data(data)
