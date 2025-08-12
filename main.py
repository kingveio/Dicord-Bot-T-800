import os
import asyncio
import aiohttp
import logging
from typing import List, Dict
import discord
from discord.ext import commands
from discord.ext.commands import Bot, Context

from discord_bot import T800Bot # Importe a classe
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI
from google_drive_service import GoogleDriveService
from data_manager import initialize_data, get_data, save_data

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('t800_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("T-800")

# Variáveis de ambiente obrigatórias
REQUIRED_ENV = [
    "DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
    "DRIVE_SERVICE_KEY", "DRIVE_FOLDER_ID", "YOUTUBE_API_KEY" # <-- Adicionado
]

# Função para verificar variáveis de ambiente
def check_environment():
    """Verifica se todas as variáveis de ambiente necessárias estão presentes."""
    missing_vars = [var for var in REQUIRED_ENV if var not in os.environ]
    if missing_vars:
        logger.critical(f"FALHA CATASTRÓFICA: Variáveis ausentes - {missing_vars}")
        raise EnvironmentError(f"Variáveis de ambiente ausentes: {missing_vars}")

# Definição das intents para o bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = T800Bot(
    intents=intents, # Passamos as intents
    application_id=int(os.getenv("DISCORD_TOKEN")) # Passamos o ID e convertemos para int
)

async def main_async():
    """Função assíncrona principal para inicializar e executar o bot."""
    check_environment()
    try:
        # Cria uma sessão aiohttp para as requisições
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            
            # Inicializa APIs de serviço
            bot.twitch_api = TwitchAPI(
                session,
                os.environ["TWITCH_CLIENT_ID"],
                os.environ["TWITCH_CLIENT_SECRET"]
            )
            bot.youtube_api = YouTubeAPI(session, os.environ["YOUTUBE_API_KEY"]) # <-- Adicionado

            # Inicializa sistema de dados
            await initialize_data()

            # Inicia o bot
            await bot.start(os.environ["DISCORD_TOKEN"])
    except EnvironmentError as e:
        logger.error(f"ERRO: {e}")
    except Exception as e:
        logger.error(f"ERRO inesperado: {e}", exc_info=True)
    finally:
        logger.info("Sistema T-800 finalizado.")

if __name__ == "__main__":
    logger.info("Iniciando sistema T-800...")
    asyncio.run(main_async())
