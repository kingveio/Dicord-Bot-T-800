import os
import sys
import asyncio
import logging
from discord_bot import bot
from data_manager import load_or_create_data, DriveService

logger = logging.getLogger("T-800")

async def main():
    try:
        logger.info("⏳ Inicializando sistemas primários... 'I'll be back.'")
        
        # Conexão com Google Drive
        bot.drive_service = DriveService()
        bot.data = await load_or_create_data(bot.drive_service)
        
        logger.info("✅ Dados carregados. 'My CPU is a neural net processor.'")
        
        # Inicia o bot
        await bot.start(os.getenv("DISCORD_TOKEN"))
        
    except Exception as e:
        logger.critical(f"❌ FALHA CATASTRÓFICA: {e} 'I need your clothes, your boots and your motorcycle.'")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | T-800 | %(message)s")
    asyncio.run(main())
