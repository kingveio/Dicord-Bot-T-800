import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import asyncio
from data_manager import get_data, save_data, update_monitored_users

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
                name="humanos streamando"
            )
        )
        self.start_time = datetime.now()
        self.live_role = "AO VIVO"
        self.system_ready = False
        self.synced = False

# Inicialização do Bot
bot = T800Bot()

# ========== EVENTOS ========== #
@bot.event
async def on_ready():
    """Evento quando o bot está pronto para uso."""
    if not bot.synced:
        try:
            # Sincroniza comandos globais e por servidor
            await bot.tree.sync()
            for guild in bot.guilds:
                await bot.tree.sync(guild=guild)
            bot.synced = True
            logger.info("✅ Comandos sincronizados com sucesso!")
        except Exception as e:
            logger.error(f"❌ Falha ao sincronizar comandos: {e}")

    bot.system_ready = True
    logger.info(f"🤖 T-800 ONLINE | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")

    # Configura o cargo "AO VIVO" em todos os servidores
    for guild in bot.guilds:
        await ensure_live_role(guild)

    # Inicia o monitoramento de streams
    if not monitor_streams.is_running():
        monitor_streams.start()

# ========== FUNÇÕES AUXILIARES ========== #
async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante que o cargo 'AO VIVO' existe no servidor."""
    try:
        # Verifica se o cargo já existe
        if role := discord.utils.get(guild.roles, name=bot.live_role):
            return role

        # Se não existir e o bot tiver permissão, cria o cargo
        if guild.me.guild_permissions.manage_roles:
            role = await guild.create_role(
                name=bot.live_role,
                color=discord.Color.red(),
                hoist=True,
                mentionable=True,
                reason="Monitoramento de streams T-800"
            )
            logger.info(f"✅ Cargo '{bot.live_role}' criado em {guild.name}")
            return role
        else:
            logger.warning(f"⚠️ Sem permissão para criar cargo em {guild.name}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro em {guild.name}: {e}")
        return None

# ========== TAREFA PERIÓDICA ========== #
@tasks.loop(minutes=5)
async def monitor_streams():
    """Verifica periodicamente os streamers monitorados."""
    if not bot.system_ready:
        return

    logger.info("🔍 Iniciando varredura de streams...")
    try:
        data = await get_data()
        if not data:
            logger.error("⚠️ Dados não carregados corretamente!")
            return

        # Monitorar Twitch
        if data["monitored_users"]["twitch"]:
            streamers = list(data["monitored_users"]["twitch"].keys())
            live_status = await bot.twitch_api.check_live_channels(streamers)
            
            for streamer, is_live in live_status.items():
                if is_live:
                    logger.info(f"🎥 {streamer} está AO VIVO!")
                    # Lógica de notificação aqui

        # Monitorar YouTube (similar)
        # ...

    except Exception as e:
        logger.error(f"❌ Falha no monitoramento: {e}")

# ========== COMANDOS DE TEXTO (PREFIXO !) ========== #
@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Sincroniza os comandos (apenas para o dono do bot)."""
    try:
        await bot.tree.sync()
        await ctx.send("✅ Comandos sincronizados globalmente!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {e}")

# ========== COMANDOS DE APLICAÇÃO (SLASH) ========== #
@bot.tree.command(name="status", description="Mostra o status do T-800")
async def status(interaction: discord.Interaction):
    """Mostra informações do sistema."""
    uptime = datetime.now() - bot.start_time
    await interaction.response.send_message(
        f"**🤖 STATUS DO T-800**\n"
        f"⏱ **Uptime:** `{str(uptime).split('.')[0]}`\n"
        f"📡 **Servidores:** `{len(bot.guilds)}`\n"
        f"👀 **Monitorando:** `Twitch: {len((await get_data())['monitored_users']['twitch'])} | YouTube: {len((await get_data())['monitored_users']['youtube'])}`",
        ephemeral=True
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
        data = await get_data()
        plataforma = plataforma.lower()
        
        if plataforma not in ["twitch", "youtube"]:
            return await interaction.response.send_message("❌ Plataforma inválida!", ephemeral=True)

        # Verifica se já está sendo monitorado
        if nome.lower() in data["monitored_users"][plataforma]:
            return await interaction.response.send_message(
                f"⚠️ {nome} já está sendo monitorado!",
                ephemeral=True
            )

        # Adiciona ao sistema
        data["monitored_users"][plataforma][nome.lower()] = {
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat(),
            "guild_id": interaction.guild.id
        }
        await update_monitored_users(plataforma, data["monitored_users"][plataforma])

        await interaction.response.send_message(
            f"✅ **{nome}** adicionado ao monitoramento na {plataforma.capitalize()}!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Erro ao adicionar streamer: {e}",
            ephemeral=True
        )

# (Adicione outros comandos como listar, remover, etc.)

# ========== INICIALIZAÇÃO ========== #
async def setup():
    """Configurações iniciais do bot."""
    # Carrega dados persistentes
    try:
        data = await get_data()
        if not data:
            await save_data()
    except Exception as e:
        logger.error(f"❌ Falha ao carregar dados: {e}")

# Executa o setup quando o bot é iniciado
@bot.event
async def setup_hook():
    await setup()
