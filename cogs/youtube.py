import logging
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="vincular_youtube", description="Vincula um canal YouTube a um usuário")
    @commands.has_permissions(administrator=True)
    async def link_yt(self, ctx, canal: str, usuario: discord.Member):
        success = await self.bot.data_manager.link_account(
            ctx.guild.id,
            usuario,
            "youtube",
            canal
        )
        quote = await self.bot.log_action(f"YouTube vinculado a {usuario.display_name}")
        await ctx.send(
            f"✅ Canal **{canal}** vinculado a {usuario.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

    @commands.hybrid_command(name="remover_youtube", description="Remove vínculo do YouTube")
    @commands.has_permissions(administrator=True)
    async def unlink_yt(self, ctx, usuario: discord.Member):
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id,
            "youtube"
        )
        quote = await self.bot.log_action(f"YouTube desvinculado de {usuario.display_name}")
        await ctx.send(
            f"🗑️ YouTube desvinculado de {usuario.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
