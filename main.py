import asyncio
import logging
from aiohttp import ClientSession
import discord
from discord.ext import commands
from config import Config
from utils.logging import setup_logging

# Configuração básica de logging
logger = logging.getLogger(__name__)

async def load_cogs(bot: commands.Bot) -> None:
    """Carrega todos os cogs automaticamente"""
    cogs = [
        "cogs.live_monitor",
        "cogs.settings",
        "cogs.twitch",
        "cogs.youtube"
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"✅ Cog carregado: {cog}")
        except Exception as e:
            logger.error(f"❌ Falha ao carregar cog {cog}: {e}")

async def keep_alive():
    """Mantém o bot ativo no plano gratuito do Render"""
    while True:
        try:
            async with ClientSession() as session:
                async with session.get("https://your-bot-name.onrender.com") as resp:
                    logger.info(f"♻ Keep-alive: Status {resp.status}")
        except Exception as e:
            logger.error(f"⚠️ Keep-alive falhou: {e}")
        await asyncio.sleep(300)  # Ping a cada 5 minutos

async def main():
    """Ponto de entrada principal do bot"""
    try:
        # 1. Validação das configurações
        Config.validate()
        setup_logging(Config.LOG_LEVEL)
        
        # 2. Configuração do bot
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        bot = commands.Bot(
            command_prefix="!",  # Prefixo não é usado com comandos slash
            intents=intents,
            help_command=None,   # Remove o comando de ajuda padrão
        )
        
        # 3. Eventos do bot
        @bot.event
        async def on_ready():
            logger.info(f"✅ Bot conectado como {bot.user.name} (ID: {bot.user.id})")
            logger.info(f"📊 Em {len(bot.guilds)} servidores")
            logger.info("🔗 Use este link para convidar o bot:")
            logger.info(f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot%20applications.commands&permissions=2147485696")
        
        # 4. Inicialização
        await load_cogs(bot)
        bot.loop.create_task(keep_alive())  # Só para Render Free
        
        # 5. Conexão ao Discord
        await bot.start(Config.DISCORD_TOKEN)
        
    except Exception as e:
        logger.critical(f"💥 Erro fatal: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot encerrado pelo usuário")
    except Exception as e:
        logger.critical(f"💥 Falha não tratada: {e}", exc_info=True)
