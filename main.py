import os
import sys
import threading
import asyncio
import logging
import aiohttp
import json
from datetime import datetime
from flask import Flask, jsonify
from drive_service import GoogleDriveService
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI
from data_manager import load_data, save_data, get_data
from discord_bot import bot

# Configuração do logger antes de qualquer uso
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
print("║    Versão 2.0 - Monitoramento Ativo        ║")
print("╚════════════════════════════════════════════╝")

configure_logging()

REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID", "DRIVE_PRIVATE_KEY_ID", "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID", "YOUTUBE_API_KEY"
]

def check_env():
    """Verifica se todas as variáveis de ambiente necessárias estão presentes."""
    for var in REQUIRED_ENV:
        if var not in os.environ:
            logger.critical(f"❌ Variável de ambiente obrigatória não encontrada: {var}")
            sys.exit(1)
    logger.info("✅ Variáveis de ambiente verificadas com sucesso.")

async def initialize_data(drive_service: Optional[GoogleDriveService]) -> None:
    """Inicializa a estrutura de dados, carregando do Drive ou criando uma nova."""
    try:
        await load_data(drive_service)
        logger.info("✅ Dados carregados ou inicializados com sucesso.")
    except Exception as e:
        logger.critical(f"❌ Falha crítica ao carregar/inicializar dados: {e}")
        sys.exit(1)

# Inicialização do servidor Flask
app = Flask(__name__)

@app.route('/ping')
def ping():
    return jsonify({"status": "online", "bot_ready": bot.system_ready})

async def main_async():
    try:
        # Verifica variáveis de ambiente
        check_env()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            # Inicializa APIs
            bot.twitch_api = TwitchAPI(
                session,
                os.environ["TWITCH_CLIENT_ID"],
                os.environ["TWITCH_CLIENT_SECRET"]
            )
            bot.youtube_api = YouTubeAPI(
                session,
                os.environ["YOUTUBE_API_KEY"]
            )
            
            # Inicializa Drive Service e dados
            bot.drive_service = GoogleDriveService()
            await initialize_data(bot.drive_service)
            
            # Inicia servidor web em um thread separado
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
