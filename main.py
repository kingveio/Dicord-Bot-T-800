import os
import sys
import threading
import asyncio
import logging
import aiohttp
from flask import Flask, jsonify
from drive_service import GoogleDriveService
from twitch_api import TwitchAPI
from data_manager import load_data_from_drive_if_exists
from discord_bot import bot

# Configuração do logger
logger = logging.getLogger("T-800")

def configure_logging():
    """Configura o sistema de logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | T-800 | %(message)s",
        handlers=[
            logging.FileHandler("t800_system.log"),
            logging.StreamHandler()
        ]
    )

# Configuração T-800
os.environ.setdefault('DISABLE_VOICE', 'true')
print("╔════════════════════════════════════════════╗")
print("║        SISTEMA T-800 INICIALIZANDO         ║")
print("║     Versão 2.2 - Estabilizando o Core      ║")
print("╚════════════════════════════════════════════╝")

configure_logging()

REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_SERVICE_KEY", "DRIVE_FOLDER_ID", "YOUTUBE_API_KEY"
]

if missing := [var for var in REQUIRED_ENV if var not in os.environ]:
    logger.critical(f"FALHA DE INICIALIZAÇÃO: Variáveis ausentes - {missing}")
    sys.exit(1)

# Inicialização do servidor web
app = Flask(__name__)

@app.route('/ping')
def ping():
    """Rota de health check para o Render."""
    logger.info("✅ Ping recebido! Servidor web está online.")
    return jsonify({"status": "online"})

async def initialize_data():
    """Função para inicializar o serviço do Google Drive e carregar os dados."""
    bot.drive_service = GoogleDriveService()
    await load_data_from_drive_if_exists(bot.drive_service)

async def main_async():
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            # Inicializa APIs
            bot.twitch_api = TwitchAPI(
                session,
                os.environ["TWITCH_CLIENT_ID"],
                os.environ["TWITCH_CLIENT_SECRET"]
            )

            # ADICIONE ESTA LINHA:
            bot.youtube_api = YouTubeAPI(session, os.environ["YOUTUBE_API_KEY"])

            # Inicializa sistema de dados
            await initialize_data()
            
            # Inicializa sistema de dados
            await initialize_data()
            
            # Inicia servidor web em uma thread separada
            threading.Thread(
                target=lambda: app.run(
                    host='0.0.0.0',
                    port=int(os.environ.get("PORT", 8080)),
                    use_reloader=False
                ),
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
        sys.exit(1)
