# T-800: Módulo de calibração. Definindo parâmetros de missão por servidor.
import discord
from discord.ext import commands
from data.data_manager import DataManager

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    @commands.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def set_live_role(self, ctx, role: discord.Role):
        # Apenas o líder pode definir a diretiva.
        guild_id = ctx.guild.id
        self.data_manager.set_live_role_id(guild_id, role.id)
        await ctx.send(f"A diretiva de missão foi atualizada. O cargo '{role.name}' será atribuído a streamers em live.")

    @set_live_role.error
    async def set_live_role_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Comando não autorizado. Apenas o administrador pode definir a diretiva de missão.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("O T-800 não reconhece esse cargo. Por favor, mencione o cargo ou use seu ID.")

def setup(bot):
    bot.add_cog(Settings(bot))
