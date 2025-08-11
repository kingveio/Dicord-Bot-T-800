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
from data_manager import load_data_from_drive_if_exists, save_data, get_data
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
    "DRIVE_CLIENT_ID"
]

if missing := [var for var in REQUIRED_ENV if var not in os.environ]:
    logger.critical(f"FALHA DE INICIALIZAÇÃO: Variáveis ausentes - {missing}")
    sys.exit(1)

app = Flask(__name__)

@app.route('/ping')
def ping():
    return jsonify({'status': 'online'})

START_TIME = datetime.now()

@app.route('/status')
def system_status():
    return jsonify({
        "status": "operacional",
        "uptime": str(datetime.now() - START_TIME),
        "mission": "monitorar_streams"
    })

async def initialize_data():
    """Inicializa o sistema de dados com fallbacks robustos"""
    try:
        drive_service = GoogleDriveService()
        
        if not hasattr(drive_service, 'download_file'):
            raise AttributeError("Serviço do Google Drive incompleto")
        
        await load_data_from_drive_if_exists(drive_service)
        return drive_service
        
    except Exception as e:
        logger.error(f"Falha ao inicializar Google Drive: {e}")
        
        if os.path.exists("streamers.json"):
            try:
                with open("streamers.json", 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        await save_data()
                        logger.info("Dados carregados do arquivo local")
            except Exception as e:
                logger.error(f"Erro ao ler arquivo local: {e}")
        
        if not os.path.exists("streamers.json"):
            with open("streamers.json", 'w') as f:
                json.dump({
                    "streamers": {},
                    "monitored_users": {
                        "twitch": {}
                    }
                }, f, indent=2)
            logger.info("Novo arquivo de dados criado")
        
        return None

async def main_async():
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            # Inicializa APIs
            bot.twitch_api = TwitchAPI(
                session,
                os.environ["TWITCH_CLIENT_ID"],
                os.environ["TWITCH_CLIENT_SECRET"]
            )
            
            # Inicializa sistema de dados
            bot.drive_service = await initialize_data()
            
            # Inicia servidor web
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
