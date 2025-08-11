import discord
from discord.ext import commands
import logging

logger = logging.getLogger("T-800")

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("✅ Módulo de administração carregado.")

    @commands.command(name="carregar", help="Carrega uma extensão (cog).")
    @commands.is_owner()
    async def load_cog(self, ctx, extension: str):
        """Carrega um cog especificado pelo nome do arquivo."""
        try:
            await self.bot.load_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Cog '{extension}' carregado com sucesso.")
        except commands.ExtensionError as e:
            await ctx.send(f"❌ Erro ao carregar o cog '{extension}': {e}")
            logger.error(f"❌ Erro ao carregar o cog '{extension}': {e}")

    @commands.command(name="descarregar", help="Descarrega uma extensão (cog).")
    @commands.is_owner()
    async def unload_cog(self, ctx, extension: str):
        """Descarrega um cog especificado pelo nome do arquivo."""
        try:
            await self.bot.unload_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Cog '{extension}' descarregado com sucesso.")
        except commands.ExtensionError as e:
            await ctx.send(f"❌ Erro ao descarregar o cog '{extension}': {e}")
            logger.error(f"❌ Erro ao descarregar o cog '{extension}': {e}")

    @commands.command(name="recarregar", help="Recarrega uma extensão (cog).")
    @commands.is_owner()
    async def reload_cog(self, ctx, extension: str):
        """Recarrega um cog especificado pelo nome do arquivo."""
        try:
            await self.bot.reload_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Cog '{extension}' recarregado com sucesso.")
            await self.bot.tree.sync()
            await ctx.send("✅ Comandos de slash sincronizados.")
        except commands.ExtensionError as e:
            await ctx.send(f"❌ Erro ao recarregar o cog '{extension}': {e}")
            logger.error(f"❌ Erro ao recarregar o cog '{extension}': {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
