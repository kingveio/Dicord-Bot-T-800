import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="adicionar_youtube")
    @commands.has_permissions(administrator=True)
    async def add_youtube(self, ctx, canal: str, usuario: discord.Member):
        """Vincula um canal YouTube a um usuário"""
        try:
            # Exemplo: !adicionar_youtube kingveio @user
            success = await self.bot.data_manager.link_account(
                ctx.guild.id,
                usuario,
                "youtube",
                canal
            )
            
            if success:
                await ctx.send(f"✅ Canal YouTube `{canal}` vinculado a {usuario.mention}")
            else:
                await ctx.send("❌ Falha ao vincular canal")
        except Exception as e:
            await ctx.send(f"💣 Erro: {e}")
            logger.error(f"Erro ao vincular YouTube: {e}")

    @commands.command(name="remover_youtube")
    @commands.has_permissions(administrator=True)
    async def remove_youtube(self, ctx, usuario: discord.Member):
        """Remove vínculo do YouTube"""
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id,
            "youtube"
        )
        await ctx.send(f"🗑️ YouTube desvinculado de {usuario.mention}" if success else "ℹ️ Nada para remover")

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
