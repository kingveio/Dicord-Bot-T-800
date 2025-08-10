import os
import logging
from discord_bot import bot as discord_bot
from twitch_api import TwitchAPI
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

async def initialize_apis(bot):
    """Inicializa as APIs da Twitch e Google Drive."""
    try:
        # Inicialização da Twitch API
        twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
        twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if twitch_client_id and twitch_client_secret:
            bot.twitch_api = TwitchAPI(twitch_client_id, twitch_client_secret)
            await bot.twitch_api._get_oauth_token()
            if bot.twitch_api.oauth_token:
                logger.info("✅ Twitch API inicializada com sucesso.")
            else:
                logger.error("❌ Falha ao obter token da Twitch.")
        else:
            logger.error("❌ TWITCH_CLIENT_ID ou TWITCH_CLIENT_SECRET não definidos.")

        # Inicialização do Google Drive API
        bot.drive_service = GoogleDriveService()
        if bot.drive_service.service:
            logger.info("✅ Google Drive API inicializada com sucesso.")
        else:
            logger.error("❌ Falha na inicialização do Google Drive API.")
            
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar as APIs: {e}")

if __name__ == "__main__":
    discord_bot.setup_hook = lambda: initialize_apis(discord_bot)
    discord_bot.run(os.getenv("DISCORD_TOKEN"))
