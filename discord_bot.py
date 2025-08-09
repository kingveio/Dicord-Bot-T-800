import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Optional

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
        self.streamers = {}  # Exemplo de lista interna de streamers

bot = T800Bot()

@bot.event
async def on_ready():
    bot.system_ready = True
    logging.info(f"T-800 ONLINE | ID: {bot.user.id}")
    
    # Configurar cargo "AO VIVO" em todos os servidores
    for guild in bot.guilds:
        await ensure_live_role(guild)

    # Iniciar monitoramento
    if not monitor_streams.is_running():
        monitor_streams.start()

    # Sincronizar comandos com o Discord
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
    logging.info("INICIANDO VARREDURA DE ALVOS...")
    # Implementar verificação de lives aqui futuramente

# ==============================
#   COMANDOS SLASH DO T-800
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

@bot.tree.command(name="ping", description="Mostra a latência do bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latência: {latency}ms", ephemeral=True)

@bot.tree.command(name="add_streamer", description="Adiciona um streamer para monitoramento")
@app_commands.describe(nome="Nome do streamer")
async def add_streamer(interaction: discord.Interaction, nome: str):
    bot.streamers[nome.lower()] = True
    await interaction.response.send_message(f"✅ Streamer `{nome}` adicionado à lista!", ephemeral=True)

@bot.tree.command(name="remove_streamer", description="Remove um streamer da lista de monitoramento")
@app_commands.describe(nome="Nome do streamer")
async def remove_streamer(interaction: discord.Interaction, nome: str):
    if nome.lower() in bot.streamers:
        del bot.streamers[nome.lower()]
        await interaction.response.send_message(f"🗑 Streamer `{nome}` removido!", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠ Streamer `{nome}` não encontrado.", ephemeral=True)

@bot.tree.command(name="listar_streamers", description="Lista todos os streamers monitorados")
async def listar_streamers(interaction: discord.Interaction):
    if not bot.streamers:
        await interaction.response.send_message("📭 Nenhum streamer cadastrado.", ephemeral=True)
    else:
        lista = "\n".join(f"- {nome}" for nome in bot.streamers.keys())
        await interaction.response.send_message(f"🎯 **Streamers monitorados:**\n{lista}", ephemeral=True)

# ==============================
#   COMANDOS DE TEXTO (!)
# ==============================

@bot.command(name="status_texto")
async def status_texto(ctx):
    uptime = datetime.now() - bot.start_time
    await ctx.send(
        f"**STATUS DO T-800**\n"
        f"⏱ Operando por: {str(uptime).split('.')[0]}\n"
        f"🔍 Monitorando: {len(bot.guilds)} servidores\n"
        f"✅ Sistemas operacionais"
    )
