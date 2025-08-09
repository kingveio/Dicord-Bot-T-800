import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Optional
from data_manager import DATA_CACHE, save_data
import asyncio

# Configuração de intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

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
        self.drive_service = None
        self.twitch_api = None
        self.youtube_api = None

bot = T800Bot()

@bot.event
async def on_ready():
    bot.system_ready = True
    logging.info(f"T-800 ONLINE | ID: {bot.user.id}")
    
    for guild in bot.guilds:
        await ensure_live_role(guild)

    if not monitor_streams.is_running():
        monitor_streams.start()

    try:
        synced = await bot.tree.sync()
        logging.info(f"✅ {len(synced)} comandos slash sincronizados com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao sincronizar comandos: {e}")

async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    try:
        if role := discord.utils.get(guild.roles, name=bot.live_role):
            return role
        
        if not guild.me.guild_permissions.manage_roles:
            return None

        role = await guild.create_role(
            name=bot.live_role,
            color=discord.Color.red(),
            reason="Monitoramento de streams"
        )
        return role
    except Exception as e:
        logging.error(f"ERRO EM {guild.name}: {str(e)}")
        return None

@tasks.loop(minutes=5)
async def monitor_streams():
    if not bot.system_ready:
        return
    logging.info("INICIANDO VARREDURA DE ALVOS... (e salvando dados no Drive)")
    try:
        await save_data(DATA_CACHE, bot.drive_service)
    except Exception as e:
        logging.error(f"Erro ao salvar dados no monitoramento: {e}")

# ==============================
#   COMANDOS SLASH
# ==============================

@bot.tree.command(name="status", description="Relatório do sistema")
async def system_status(interaction: discord.Interaction):
    uptime = datetime.now() - bot.start_time
    await interaction.response.send_message(
        f"**STATUS DO T-800**\n"
        f"⏱ Operando por: {str(uptime).split('.')[0]}\n"
        f"🔍 Monitorando: {len(bot.guilds)} servidores\n"
        f"✅ Sistemas operacionais",
        ephemeral=True
    )

@bot.tree.command(name="add_streamer", description="Adiciona um streamer da Twitch")
@app_commands.describe(nome="Nome do streamer")
async def add_streamer(interaction: discord.Interaction, nome: str):
    DATA_CACHE["streamers"][nome.lower()] = True
    await interaction.response.send_message(f"✅ Streamer `{nome}` adicionado à lista!", ephemeral=True)

@bot.tree.command(name="remove_streamer", description="Remove um streamer da Twitch")
@app_commands.describe(nome="Nome do streamer")
async def remove_streamer(interaction: discord.Interaction, nome: str):
    if nome.lower() in DATA_CACHE["streamers"]:
        del DATA_CACHE["streamers"][nome.lower()]
        await interaction.response.send_message(f"🗑 Streamer `{nome}` removido!", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠ Streamer `{nome}` não encontrado.", ephemeral=True)

@bot.tree.command(name="listar_streamers", description="Lista todos os streamers da Twitch monitorados")
async def listar_streamers(interaction: discord.Interaction):
    if not DATA_CACHE["streamers"]:
        await interaction.response.send_message("📭 Nenhum streamer cadastrado.", ephemeral=True)
    else:
        lista = "\n".join(f"- {nome}" for nome in DATA_CACHE["streamers"].keys())
        await interaction.response.send_message(f"🎯 **Streamers monitorados:**\n{lista}", ephemeral=True)

@bot.tree.command(name="add_youtube", description="Adiciona um canal do YouTube para monitoramento")
@app_commands.describe(url="URL do canal ou handle do YouTube")
async def add_youtube(interaction: discord.Interaction, url: str):
    channel_id = await bot.youtube_api.get_channel_id(url)
    if not channel_id:
        await interaction.response.send_message("⚠ Não foi possível identificar o canal do YouTube.", ephemeral=True)
        return
    DATA_CACHE["youtube_channels"][channel_id] = url
    await interaction.response.send_message(f"✅ Canal `{url}` adicionado com ID `{channel_id}`!", ephemeral=True)

@bot.tree.command(name="remove_youtube", description="Remove um canal do YouTube da lista de monitoramento")
@app_commands.describe(url="URL ou handle do canal do YouTube")
async def remove_youtube(interaction: discord.Interaction, url: str):
    channel_id = await bot.youtube_api.get_channel_id(url)
    if not channel_id or channel_id not in DATA_CACHE["youtube_channels"]:
        await interaction.response.send_message(f"⚠ Canal `{url}` não encontrado.", ephemeral=True)
        return
    del DATA_CACHE["youtube_channels"][channel_id]
    await interaction.response.send_message(f"🗑 Canal `{url}` removido!", ephemeral=True)

@bot.tree.command(name="listar_youtube", description="Lista todos os canais do YouTube monitorados")
async def listar_youtube(interaction: discord.Interaction):
    if not DATA_CACHE["youtube_channels"]:
        await interaction.response.send_message("📭 Nenhum canal do YouTube cadastrado.", ephemeral=True)
    else:
        lista = "\n".join(f"- {link}" for link in DATA_CACHE["youtube_channels"].values())
        await interaction.response.send_message(f"🎯 **Canais do YouTube monitorados:**\n{lista}", ephemeral=True)
