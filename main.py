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
from data_manager import load_data_from_drive_if_exists
from discord_bot import bot

# Configuração T-800
os.environ.setdefault('DISABLE_VOICE', 'true')
print("╔════════════════════════════════════════════╗")
print("║        SISTEMA T-800 INICIALIZANDO         ║")
print("║    Versão 2.0 - Monitoramento Ativo        ║")
print("╚════════════════════════════════════════════╝")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | T-800 | %(message)s",
    handlers=[
        logging.FileHandler("t800_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("T-800")

# Verificação de requisitos
REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID", "YOUTUBE_API_KEY"
]

if missing := [var for var in REQUIRED_ENV if var not in os.environ]:
    logger.critical(f"FALHA DE INICIALIZAÇÃO: Variáveis ausentes - {missing}")
    sys.exit(1)

# Servidor de monitoramento
app = Flask(__name__)
START_TIME = datetime.now()

@app.route('/status')
def system_status():
    return jsonify({
        "status": "operacional",
        "uptime": str(datetime.now() - START_TIME),
        "mission": "monitorar_streams"
    })

async def main_async():
    try:
        # Inicializar subsistemas
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
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

            # Verificar arquivo de dados
            if not os.path.exists("streamers.json"):
                with open("streamers.json", 'w') as f:
                    f.write('{"streamers": {}, "youtube_channels": {}}')
                logger.info("Arquivo de dados local criado")

            await load_data_from_drive_if_exists(bot.drive_service)

            # Iniciar servidor
            threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))),
                daemon=True
            ).start()

            logger.info("Conectando à rede Discord...")
            await bot.start(os.environ["DISCORD_TOKEN"])

    except Exception as e:
        logger.critical(f"FALHA CATASTRÓFICA: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Missão interrompida pelo usuário")
    except Exception as e:
        logger.error(f"ERRO: {str(e)}")
