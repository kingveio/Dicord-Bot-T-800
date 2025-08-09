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
from data_manager import load_data_from_drive_if_exists, save_data_to_drive
from discord_bot import bot

# Configuração inicial
os.environ.setdefault('DISABLE_VOICE', 'true')

print("╔════════════════════════════════════════════╗")
print("║           SISTEMA T-800 ONLINE             ║")
print("║    Monitoramento de Streams Ativado        ║")
print("╚════════════════════════════════════════════╝")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("t800.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("T-800")

# Variáveis obrigatórias
REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID", "YOUTUBE_API_KEY"
]

# Verificação de variáveis
missing = [v for v in REQUIRED_ENV if v not in os.environ]
if missing:
    logger.error(f"❌ Componentes essenciais faltando: {missing}")
    sys.exit(1)

# Servidor Flask para monitoramento
app = Flask(__name__)
START_TIME = datetime.now()

@app.route('/')
def status():
    return jsonify({
        "status": "online",
        "mission": "Monitorar streams humanas",
        "uptime": str(datetime.now() - START_TIME)
    })

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

async def main_async():
    logger.info("Inicializando subsistemas...")
    
    # Configurar APIs
    async with aiohttp.ClientSession() as session:
        bot.twitch_api = TwitchAPI(
            session,
            os.environ["TWITCH_CLIENT_ID"],
            os.environ["TWITCH_CLIENT_SECRET"]
        )
        bot.youtube_api = YouTubeAPI(
            session,
            os.environ["YOUTUBE_API_KEY"]
        )
        bot.drive_service = GoogleDriveService()
        
        await load_data_from_drive_if_exists(bot.drive_service)
        
        # Iniciar servidor de monitoramento em thread separada
        threading.Thread(target=run_flask, daemon=True).start()
        
        logger.info("Conectando à rede Discord...")
        await bot.start(os.environ["DISCORD_TOKEN"])

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("⏹ Missão interrompida pelo usuário")
    except Exception as e:
        logger.error(f"❌ Falha catastrófica: {str(e)}")
