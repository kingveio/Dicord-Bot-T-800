import os
import logging
from flask import Flask, jsonify
from threading import Thread
import asyncio
from discord_bot import bot as discord_bot
from data_manager import load_data_from_drive_if_exists
from drive_service import GoogleDriveService
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI
import aiohttp

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("T-800")

# Inicializa o servidor web Flask
app = Flask(__name__)

# Configuração do bot
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DRIVE_SERVICE_KEY = os.environ.get("DRIVE_SERVICE_KEY")
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not DISCORD_TOKEN:
    logger.critical("❌ Variável de ambiente DISCORD_TOKEN não encontrada. O bot não pode ser iniciado.")
    exit()

# Rota para o ping do Render
@app.route('/ping')
def ping():
    logger.info("✅ Ping recebido! Servidor está online.")
    return jsonify({"status": "online"}), 200

def run_flask_server():
    """Inicia o servidor Flask em uma thread separada."""
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

async def main():
    """Função principal para inicializar o bot e as APIs."""
    logger.info("🤖 Iniciando sistema T-800...")

    # Inicializa o Google Drive Service se a chave estiver disponível
    if DRIVE_SERVICE_KEY:
        try:
            drive_service = GoogleDriveService(DRIVE_SERVICE_KEY)
            discord_bot.drive_service = drive_service
            logger.info("✅ Google Drive Service inicializado.")
        except Exception as e:
            logger.error(f"❌ Falha ao inicializar o Google Drive Service: {e}")
            discord_bot.drive_service = None
    else:
        logger.warning("⚠️ Variável de ambiente DRIVE_SERVICE_KEY não encontrada. O bot não salvará dados no Google Drive.")
        discord_bot.drive_service = None

    # Carrega os dados existentes do Drive ou localmente
    await load_data_from_drive_if_exists(discord_bot.drive_service)

    # Inicia as APIs
    async with aiohttp.ClientSession() as session:
        discord_bot.twitch_api = TwitchAPI(session, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
        discord_bot.youtube_api = YouTubeAPI(session, YOUTUBE_API_KEY)

        # Inicia o bot
        await discord_bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    # Roda o servidor Flask em uma thread separada
    server_thread = Thread(target=run_flask_server)
    server_thread.start()

    # Roda o bot em loop de eventos assíncrono
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"❌ Falha crítica na execução principal: {e}")
