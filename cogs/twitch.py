# T-800: Módulo de aquisição de alvos. Twitch.
from discord.ext import commands
from data.data_manager import DataManager

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    @commands.command(name="addtwitch")
    async def add_twitch_user(self, ctx, twitch_username: str):
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        self.data_manager.add_user(guild_id, user_id, twitch_name=twitch_username)
        await ctx.send(f"Alvo '{twitch_username}' adicionado à lista de vigilância da Twitch para este servidor. Eu voltarei a verificar.")

def setup(bot):
