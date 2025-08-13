import discord
from discord import app_commands
from discord.ext import commands
from config import Config

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

    async def setup_hook(self):
        # Carrega extensões
        await self.load_extension("cogs.live_monitor")
        await self.load_extension("cogs.youtube")
        await self.load_extension("cogs.twitch")
        await self.load_extension("cogs.settings")
        
        # Sincroniza comandos globais
        await self.tree.sync()
        print("✅ Comandos sincronizados para todos os servidores!")

bot = T800Bot()

@bot.event
async def on_guild_join(guild):
    print(f"🤖 Entrou no servidor: {guild.name} (ID: {guild.id})")

if __name__ == "__main__":
    Config.validate()
    bot.run(Config.DISCORD_TOKEN)
