import discord
from discord.ext import commands
from config import Config

class T800Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",  # Prefixo tradicional
            intents=intents,
            help_command=None  # Remove o help padrão
        )

    async def setup_hook(self):
        # Carrega as extensões
        await self.load_extension("cogs.live_monitor")
        await self.load_extension("cogs.youtube")
        await self.load_extension("cogs.twitch")
        await self.load_extension("cogs.settings")

bot = T800Bot()

if __name__ == "__main__":
    Config.validate()
    bot.run(Config.DISCORD_TOKEN)
