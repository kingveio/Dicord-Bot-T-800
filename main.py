import os
import asyncio
import logging
from discord_bot import bot
from data_manager import load_or_create_data, DriveService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | T-800 | %(message)s"
)
logger = logging.getLogger("T-800")

async def main():
    try:
        logger.info("🔥 Iniciando sistemas T-800...")
        
        # Configura Google Drive
        bot.drive_service = DriveService()
        bot.data = await load_or_create_data(bot.drive_service)
        
        # Inicia o bot
        await bot.start(os.getenv("DISCORD_TOKEN"))
        
    except Exception as e:
        logger.critical(f"❌ Falha catastrófica: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
