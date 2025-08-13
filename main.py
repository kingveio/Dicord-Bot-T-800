import os
import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging
from data.data_manager import DataManager
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI

logger = logging.getLogger(__name__)

class T800Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # Inicializa o DataManager
        self.data_manager = DataManager()
        self.data_manager.bot = self  # Permite acesso ao bot
        
        # Inicializa APIs
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        
        # Variáveis para health check
        self.health_server = None
        self.session = None
        self.keep_alive_task = None

    async def setup_hook(self):
        """Configuração inicial assíncrona"""
        try:
            # 1. Carrega dados primeiro
            await self.data_manager.load()
            
            # 2. Configura health check
            self.session = ClientSession(
                timeout=ClientTimeout(total=10),
                headers={'User-Agent': 'DiscordBot/1.0'}
            )
            
            # 3. Carrega os cogs
            cogs = [
                "cogs.live_monitor",
                "cogs.youtube",
                "cogs.twitch",
                "cogs.settings"
            ]
            
            for cog in cogs:
                try:
                    await self.load_extension(cog)
                    logger.info(f"✅ Cog carregado: {cog}")
                except Exception as e:
                    logger.error(f"❌ Falha ao carregar {cog}: {e}")
            
            # 4. Configura keep-alive se estiver no Render
            if Config.is_render():
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                logger.info("🔵 Ambiente Render detectado")
                
        except Exception as e:
            logger.critical(f"🚨 Falha no setup: {e}", exc_info=True)
            raise

    async def keep_alive(self):
        """Mantém o bot ativo no Render"""
        await self.wait_until_ready()
        service_url = f"https://{Config.RENDER_SERVICE_NAME}.onrender.com"
        
        while not self.is_closed():
            try:
                async with self.session.get(f"{service_url}/health") as resp:
                    status = "✅" if resp.status == 200 else "⚠️"
                    logger.debug(f"{status} Keep-alive ping: {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Keep-alive falhou: {e}")
            await asyncio.sleep(300)  # 5 minutos

    async def close(self):
        """Limpeza ao desligar o bot"""
        logger.info("🛑 Desligando bot...")
        
        # 1. Cancela tarefa de keep-alive
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # 2. Fecha sessão HTTP
        if self.session and not self.session.closed:
            await self.session.close()
        
        # 3. Fecha conexão com Discord
        await super().close()
        logger.info("👋 Bot desligado com sucesso")

async def main():
    try:
        # Valida as configurações primeiro
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        logger.info("✅ Todas as configurações validadas com sucesso")
        
        # Inicializa e inicia o bot
        bot = T800Bot()
        await bot.start(Config.DISCORD_TOKEN)
        
    except ValueError as e:
        logger.critical(f"❌ Erro de configuração: {e}")
        raise
    except Exception as e:
        logger.critical(f"💥 ERRO FATAL: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrompido pelo usuário")
    except Exception as e:
        logger.critical(f"💥 ERRO NÃO TRATADO: {e}", exc_info=True)
