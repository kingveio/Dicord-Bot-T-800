import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Optional, Dict

# Configuração T-800
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
        self.synced = False

bot = T800Bot()

@bot.event
async def on_ready():
    if not bot.synced:
        try:
            await bot.tree.sync()
            bot.synced = True
            logging.info("Comandos sincronizados com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao sincronizar comandos: {e}")
    
    bot.system_ready = True
    logging.info(f"T-800 ONLINE | ID: {bot.user.id}")
    
    # Configurar cargo em todos os servidores
    for guild in bot.guilds:
        await ensure_live_role(guild)

    # Iniciar monitoramento
    if not monitor_streams.is_running():
        monitor_streams.start()

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
    
    logging.info("INICIANDO VARREdura DE ALVOS...")
    # Implementação do monitoramento aqui

@bot.tree.command(name="status", description="Relatório do sistema T-800")
async def system_status(interaction: discord.Interaction):
    uptime = datetime.now() - bot.start_time
    await interaction.response.send_message(
        f"**STATUS DO T-800**\n"
        f"⏱ Operando por: {str(uptime).split('.')[0]}\n"
        f"🔍 Monitorando: {len(bot.guilds)} servidores\n"
        f"✅ Sistemas operacionais\n"
        f"💻 Objetivo primário: Proteger os streamers humanos",
        ephemeral=True
    )

@bot.tree.command(name="sobre", description="Informações sobre o T-800")
async def about(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**SISTEMA T-800 v2.0**\n"
        "Modelo 101 - Cyberdyne Systems\n"
        "Ano de fabricação: 2024\n"
        "Missão: Monitorar e proteger streamers humanos\n"
        "Frase característica: 'I'll be back'",
        ephemeral=True
    )

@bot.tree.command(name="terminar", description="Comando de emergência (apenas para administradores)")
@app_commands.default_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message(
        "⚠️ ATIVAÇÃO DO PROTOCOLO DE AUTODESTRUIÇÃO\n"
        "Sistema será desativado em 5 segundos...",
        ephemeral=True
    )
    await asyncio.sleep(5)
    await interaction.followup.send("T-800 desativado. Até a próxima, humano.")
    await bot.close()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Sincroniza comandos (apenas para dono do bot)"""
    try:
        await bot.tree.sync()
        await ctx.send("✅ Comandos sincronizados em todos os servidores!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {e}")
