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
from youtube_api import YouTubeAPI
from data_manager import load_data_from_drive_if_exists, save_data_to_drive, get_cached_data
from discord_bot import bot

os.environ.setdefault('DISABLE_VOICE', 'true')

print("╔════════════════════════════════════════════╗")
print("║  BOT DE NOTIFICAÇÕES TWITCH E YOUTUBE      ║")
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
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY", "DRIVE_CLIENT_ID",
    "YOUTUBE_API_KEY"
]

missing = [v for v in REQUIRED_ENV if v not in os.environ]
if missing:
    logger.error(f"❌ Variáveis faltando: {missing}")
    sys.exit(1)

app = Flask(__name__)
START_TIME = datetime.now()
HTTP_SESSION = None

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "uptime": str(datetime.now() - START_TIME),
        "bot": "running"
    }), 200

@app.route('/ping')
def ping():
    return jsonify({"status": "pong"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

async def auto_save_task(drive_service):
    while True:
        try:
            await asyncio.sleep(300)
            data = await get_cached_data()
            await save_data_to_drive(data, drive_service)
            logger.info("🔄 Backup automático no Drive concluído")
        except Exception as e:
            logger.error(f"Erro no backup: {str(e)}")

async def main_async():
    global HTTP_SESSION
    HTTP_SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    
    bot.twitch_api = TwitchAPI(HTTP_SESSION, os.environ["TWITCH_CLIENT_ID"], os.environ["TWITCH_CLIENT_SECRET"])
    bot.drive_service = GoogleDriveService()
    bot.youtube_api = YouTubeAPI(HTTP_SESSION, os.environ["YOUTUBE_API_KEY"])
    
    await load_data_from_drive_if_exists(bot.drive_service)

    asyncio.create_task(auto_save_task(bot.drive_service))
    threading.Thread(target=run_flask, daemon=True).start()

    await bot.start(os.environ["DISCORD_TOKEN"])

async def shutdown():
    if HTTP_SESSION:
        await HTTP_SESSION.close()

if __name__ == '__main__':
    if not os.path.exists("streamers.json"):
        with open("streamers.json", 'w') as f:
            f.write('{"streamers": {}, "configs": {}, "youtube_channels": {}}')

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("👋 Desligado via Ctrl+C")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {str(e)}")
    finally:
        asyncio.run(shutdown())
