import discord
from discord.ext import commands
import logging

logger = logging.getLogger("T-800")

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("✅ Módulo de administração inicializado.")

    def cog_unload(self):
        logger.info("❌ Módulo de administração descarregado.")

    @commands.command(name="recarregar")
    # A linha abaixo foi removida para que o comando possa ser usado por qualquer administrador.
    # @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, cog_name: str):
        """Recarrega um módulo do bot."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Você não tem permissão para usar este comando. Alerta: Falha na operação.")
            return

        try:
            await self.bot.reload_extension(f"cogs.{cog_name}")
            await ctx.send(f"✅ O módulo `{cog_name}` foi recarregado. Missão concluída.")
            logger.info(f"✅ Módulo '{cog_name}' recarregado com sucesso por {ctx.author.name}.")
        except commands.ExtensionNotLoaded:
            await ctx.send(f"⚠️ O módulo `{cog_name}` não está carregado. Alerta: Falha na operação.")
            logger.warning(f"⚠️ Tentativa de recarregar módulo não carregado: '{cog_name}'.")
        except Exception as e:
            await ctx.send(f"❌ Erro ao recarregar o módulo `{cog_name}`: {e}. Alerta: Falha na operação.")
            logger.error(f"❌ Erro ao recarregar o módulo '{cog_name}': {e}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
