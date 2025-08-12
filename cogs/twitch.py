# T-800: Módulo de aquisição de alvos. Twitch.
from discord.ext import commands
from data.data_manager import DataManager

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    @commands.command(name="addtwitch")
    async def add_twitch_user(self, ctx, twitch_username: str):
        # Adicionando um novo alvo da Twitch à memória.
        user_id = ctx.author.id
        self.data_manager.add_user(user_id, twitch_name=twitch_username)
        await ctx.send(f"Alvo '{twitch_username}' adicionado à lista de vigilância da Twitch. Eu voltarei a verificar.")

def setup(bot):
    bot.add_cog(TwitchCommands(bot))
