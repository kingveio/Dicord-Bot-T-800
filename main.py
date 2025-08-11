import os
import aiohttp
import asyncio
import threading
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv

from twitch_api import TwitchAPI
from drive_service import DriveService
from data_manager import initialize_data
from discord_bot import bot

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REQUIRED_ENV = [
    "DISCORD_TOKEN",
    "TWITCH_CLIENT_ID",
    "TWITCH_CLIENT_SECRET"
]

# Servidor Flask para health check
app = Flask(__name__)
@app.route("/")
def health_check():
    """Endpoint de health check."""
    return jsonify({"status": "healthy", "message": "Bot is running"})


async def main_async():
    """Função principal assíncrona que inicializa e executa o bot."""
    try:
        # Verifica variáveis de ambiente
        missing_vars = [var for var in REQUIRED_ENV if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"❌ Variáveis de ambiente faltando: {', '.join(missing_vars)}")

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


def main():
    """Função de entrada do programa."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Programa encerrado pelo usuário.")


if __name__ == "__main__":
    main()
