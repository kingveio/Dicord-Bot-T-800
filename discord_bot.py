import os
import sys
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands
from discord import app_commands, ui

# Configuração inicial
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Intents necessários
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Inicialização do Bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Streamers da Twitch"
    )
)

# Variáveis globais
START_TIME = datetime.now()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))  # 5 minutos
CHECK_TASK = None

# ---------------------------------------------------------------------------- #
#                                  COMPONENTES                                 #
# ---------------------------------------------------------------------------- #

class AddStreamerDiscordModal(ui.Modal, title="Vincular Usuário Discord"):
    discord_id = ui.TextInput(label="ID do Discord", placeholder="Digite o ID ou @mencione", min_length=3, max_length=32)

    def __init__(self, twitch_username: str):
        super().__init__()
        self.twitch_username = twitch_username

    async def on_submit(self, interaction: discord.Interaction):
        try:
            discord_id = re.sub(r'\D', '', str(self.discord_id))
            if not (17 <= len(discord_id) <= 19):
                return await interaction.response.send_message("❌ ID inválido!", ephemeral=True)

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                return await interaction.response.send_message("❌ Membro não encontrado!", ephemeral=True)

            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            
            if guild_id not in data["streamers"]:
                data["streamers"][guild_id] = {}

            if self.twitch_username in data["streamers"][guild_id]:
                return await interaction.response.send_message("⚠️ Streamer já vinculado!", ephemeral=True)

            data["streamers"][guild_id][self.twitch_username] = discord_id
            await set_cached_data(data, bot.drive_service, persist=True)

            await interaction.response.send_message(
                f"✅ {member.mention} vinculado a `{self.twitch_username}`",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro no modal: {str(e)}")
            await interaction.response.send_message("❌ Erro interno!", ephemeral=True)

class AddStreamerTwitchModal(ui.Modal, title="Adicionar Streamer Twitch"):
    twitch_name = ui.TextInput(label="Nome na Twitch", placeholder="ex: alanzoka", min_length=3, max_length=25)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            username = str(self.twitch_name).lower().strip()
            if not re.match(r'^[a-z0-9_]{3,25}$', username):
                return await interaction.response.send_message("❌ Nome inválido!", ephemeral=True)
            
            await interaction.response.send_modal(AddStreamerDiscordModal(username))
        except Exception as e:
            logger.error(f"Erro no modal Twitch: {str(e)}")
            await interaction.response.send_message("❌ Erro interno!", ephemeral=True)

class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerTwitchModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_button(self, interaction: discord.Interaction, button: ui.Button):
        # Implementação existente...
        pass

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_button(self, interaction: discord.Interaction, button: ui.Button):
        # Implementação existente...
        pass

# ---------------------------------------------------------------------------- #
#                                   COMANDOS                                   #
# ---------------------------------------------------------------------------- #

@bot.tree.command(name="streamers", description="Painel de gerenciamento")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_panel(interaction: discord.Interaction):
    """Painel principal de streamers"""
    try:
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "⚠️ Preciso da permissão **Gerenciar Cargos**!",
                ephemeral=True
            )
        
        await interaction.response.send_message(
            "**🎮 Painel de Streamers** - Escolha uma opção:",
            view=StreamersView(),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Erro no /streamers: {str(e)}")
        await interaction.response.send_message("❌ Erro ao abrir painel!", ephemeral=True)

@bot.command()
@commands.is_owner()
async def debug(ctx):
    """🔧 Mostra informações técnicas do bot (Apenas dono)"""
    try:
        embed = discord.Embed(
            title="🤖 DEBUG - Status Completo",
            color=0x00FFFF,
            timestamp=datetime.now()
        )
        
        # Informações básicas
        embed.add_field(name="🕒 Uptime", value=str(datetime.now() - START_TIME).split('.')[0], inline=False)
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
        embed.add_field(name="⚙ Comandos", value=len(bot.commands), inline=True)
        
        # Informações de sistema
        embed.add_field(name="🐍 Python", value=sys.version.split()[0], inline=True)
        embed.add_field(name="📁 Diretório", value=os.getcwd(), inline=False)
        
        # Informações específicas do bot
        data = await get_cached_data()
        total_streamers = sum(len(g) for g in data.get("streamers", {}).values())
        embed.add_field(name="🎮 Streamers", value=f"{total_streamers} em {len(data.get('streamers', {}))} servidores", inline=False)
        
        embed.set_footer(text=f"Bot ID: {bot.user.id}")
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Erro no debug: {str(e)}")
        await ctx.send("❌ Falha ao gerar relatório de debug!")

# ---------------------------------------------------------------------------- #
#                                   EVENTOS                                    #
# ---------------------------------------------------------------------------- #

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"📊 Em {len(bot.guilds)} servidores")
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"🔄 {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar comandos: {str(e)}")
    
    # Inicia a tarefa de verificação
    global CHECK_TASK
    if CHECK_TASK is None or CHECK_TASK.done():
        CHECK_TASK = bot.loop.create_task(check_streams_task())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ Apenas o dono do bot pode usar este comando!")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("⚠️ Você não tem permissão para usar este comando!")
    else:
        logger.error(f"Erro no comando {ctx.command}: {str(error)}")

# ---------------------------------------------------------------------------- #
#                                   TAREFAS                                   #
# ---------------------------------------------------------------------------- #

async def check_streams_task():
    """Verifica periodicamente os streamers ao vivo"""
    await bot.wait_until_ready()
    logger.info("🔍 Iniciando verificador de lives...")
    
    while not bot.is_closed():
        try:
            # Implementação existente...
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Erro na task de lives: {str(e)}")
            await asyncio.sleep(60)  # Espera antes de tentar novamente

# ---------------------------------------------------------------------------- #
#                                INICIALIZAÇÃO                                #
# ---------------------------------------------------------------------------- #

def setup():
    """Configurações iniciais"""
    bot.add_view(StreamersView())  # Persistência da View
    logger.info("🛠️ Configuração inicial concluída")

# Executa a configuração quando o arquivo é carregado
setup()
