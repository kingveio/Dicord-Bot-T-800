import discord
from discord.ext import commands
from discord import app_commands, ui
import aiohttp
import asyncio
import json
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ========== CONFIGURAÇÃO INICIAL ==========
print("╔════════════════════════════════════════════╗")
print("║       BOT DE NOTIFICAÇÕES DA TWITCH        ║")
print("╚════════════════════════════════════════════╝")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Verifica variáveis de ambiente necessárias
REQUIRED_ENV = ["DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"]
missing = [var for var in REQUIRED_ENV if var not in os.environ]

if missing:
    logging.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

# Configurações
TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = 60  # segundos

# ========== SERVIDOR FLASK (Keep-Alive) ==========
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot Twitch Online! Mantido por Flask no Render."

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def start_keepalive():
    """Inicia o servidor Flask para manter o bot online."""
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logging.info("✅ Servidor Flask iniciado para keep-alive")

# ========== INICIALIZAÇÃO DO BOT ==========
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Exterminador do Futuro 2"
    )
)

# ========== GERENCIAMENTO DE DADOS ==========
def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump({}, f)
            return {}

        with open(DATA_FILE) as f:
            return json.load(f)
    except Exception as e:
        logging.error("Erro ao carregar dados: %s", e)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error("Erro ao salvar dados: %s", e)

# ... (o restante do código permanece exatamente igual) ...

# ========== INICIAR O BOT ==========
if __name__ == "__main__":
    start_keepalive()  # Ativa o keep-alive com Flask

    # Tenta reconectar automaticamente em caso de falha
    while True:
        try:
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"⚠️ Bot caiu: {e}. Reconectando em 60 segundos...")
            time.sleep(60)
