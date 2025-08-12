import os
import asyncio
import logging
from discord_bot import bot
from data_manager import load_or_create_data, DriveService

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | T-800 | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("T-800")

async def main():
    try:
        logger.info("🔥 Iniciando sistemas... 'Hasta la vista, baby.'")
        
        # Conexão com Google Drive
        bot.drive_service = DriveService()
        bot.data = await load_or_create_data(bot.drive_service)
        
        # Inicia o bot
        await bot.start(os.getenv("DISCORD_TOKEN"))
        
    except Exception as e:
        logger.critical(f"❌ FALHA: {e} 'I'll be back.'")
        raise

if __name__ == "__main__":
    asyncio.run(main())
