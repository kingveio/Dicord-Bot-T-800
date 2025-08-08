# main.py
import os
import sys
import threading
import asyncio
import logging
import aiohttp
from datetime import datetime

from flask import Flask, jsonify

from drive_service import GoogleDriveService
from twitch_api import TwitchAPI
from data_manager import load_data_from_drive_if_exists
from discord_bot import bot, twitch_api, drive_service, run_discord_bot

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Variáveis de ambiente obrigatórias
REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID"
]
missing = [v for v in REQUIRED_ENV if v not in os.environ]
if missing:
    logger.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

# Flask (health check)
app = Flask(__name__)
START_TIME = datetime.now()

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "uptime": str(datetime.now() - START_TIME),
        "bot": "running"
    }), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Inicialização principal
async def initialize_services():
    global HTTP_SESSION, twitch_api, drive_service
    # Cria sessão HTTP e serviços
    HTTP_SESSION = aiohttp.ClientSession()
    # Atribui os serviços às variáveis globais do discord_bot
    bot.twitch_api = TwitchAPI(HTTP_SESSION, os.environ["TWITCH_CLIENT_ID"], os.environ["TWITCH_CLIENT_SECRET"])
    bot.drive_service = GoogleDriveService()
    
    # Carrega dados do Drive
    await load_data_from_drive_if_exists(bot.drive_service)

async def graceful_shutdown():
    logger.info("🔻 Iniciando shutdown limpo")
    if bot.CHECK_TASK:
        bot.CHECK_TASK.cancel()
    if bot.HTTP_SESSION:
        await bot.HTTP_SESSION.close()
        logger.info("✅ Sessão HTTP fechada")
    await asyncio.sleep(0.5)

if __name__ == '__main__':
    # Inicializa serviços em um loop assíncrono
    asyncio.run(initialize_services())
    
    # Inicia o Flask em uma thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Roda o bot do Discord
    run_discord_bot(os.environ["DISCORD_TOKEN"])
