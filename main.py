import os
import logging
from discord_bot import bot as discord_bot
from twitch_api import TwitchAPI
from youtube_api import YouTubeAPI
from drive_service import GoogleDriveService

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def initialize_apis(bot):
    """Inicializa as APIs da Twitch, YouTube e Google Drive."""
    try:
        # Inicialização da Twitch API
        twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
        twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if twitch_client_id and twitch_client_secret:
            bot.twitch_api = TwitchAPI(twitch_client_id, twitch_client_secret)
            logger.info("✅ Twitch API inicializada com sucesso.")
        else:
            logger.error("❌ TWITCH_CLIENT_ID ou TWITCH_CLIENT_SECRET não definidos.")

        # Inicialização da YouTube API
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if youtube_api_key:
            bot.youtube_api = YouTubeAPI(youtube_api_key)
            logger.info("✅ YouTube API inicializada com sucesso.")
        else:
            logger.error("❌ YOUTUBE_API_KEY não definida.")
            
        # Inicialização do Google Drive API
        bot.drive_service = GoogleDriveService()
        if bot.drive_service.service:
            logger.info("✅ Google Drive API inicializada com sucesso.")
        else:
            logger.error("❌ Falha na inicialização do Google Drive API.")
            
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar as APIs: {e}")

if __name__ == "__main__":
    initialize_apis(discord_bot)
    discord_bot.run(os.getenv("DISCORD_TOKEN"))
