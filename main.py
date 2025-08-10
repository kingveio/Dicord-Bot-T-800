import discord
from discord.ext import commands
import aiohttp
import socket
import os

# Força o uso de IPv4 para evitar timeout no Render
connector = aiohttp.TCPConnector(family=socket.AF_INET)

discord_bot = commands.Bot(
    command_prefix="!",
    intents=discord.Intents.all(),
    connector=connector
)

@discord_bot.event
async def on_ready():
    print(f"✅ Bot conectado como {discord_bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Variável DISCORD_TOKEN não encontrada no Render!")

discord_bot.run(TOKEN)
