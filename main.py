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
from discord_bot import bot

os.environ.setdefault('DISABLE_VOICE', 'true')

print("╔════════════════════════════════════════════╗")
print("║         BOT DE NOTIFICAÇÕES DA TWITCH      ║")
print("╚════════════════════════════════════════════╝")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID"
]
missing = [v for v in REQUIRED_ENV if v not in os.environ]
if missing:
    logger.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

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

HTTP_SESSION = None

async def main_async():
    global HTTP_SESSION
    if HTTP_SESSION is None:
        HTTP_SESSION = aiohttp.ClientSession()
    
    bot.twitch_api = TwitchAPI(HTTP_SESSION, os.environ["TWITCH_CLIENT_ID"], os.environ["TWITCH_CLIENT_SECRET"])
    bot.drive_service = GoogleDriveService()
    
    await load_data_from_drive_if_exists(bot.drive_service)

    # Inicia o Flask em uma thread separada
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Inicia o bot do Discord
    await bot.start(os.environ["DISCORD_TOKEN"])

if __name__ == '__main__':
    # Cria o arquivo de dados inicial se não existir
    if not os.path.exists("streamers.json"):
        with open("streamers.json", 'w', encoding='utf-8') as f:
            f.write("{}")

    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.error(f"❌ Ocorreu um erro fatal: {e}")
