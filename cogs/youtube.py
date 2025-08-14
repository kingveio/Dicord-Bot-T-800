import discord
from discord import app_commands # <<< Adicione esta linha
from discord.ext import commands
import logging
from config import Config

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self):
        if not Config.YOUTUBE_API_KEY:
            raise ValueError("YouTube API Key não configurada")
        
        self.api_key = Config.YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"
        logger.info("✅ YouTube API configurada")

class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.youtube_api = YouTubeAPI()

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
            logger.error(f"Erro ao vincular YouTube: {e}", exc_info=True)

    @commands.command(name="remover_youtube")
    @commands.has_permissions(administrator=True)
    async def remove_youtube(self, ctx, usuario: discord.Member):
        """Remove vínculo do YouTube"""
        try:
            success = await self.bot.data_manager.remove_account(
                ctx.guild.id,
                usuario.id,
                "youtube"
            )
            await ctx.send(f"🗑️ YouTube desvinculado de {usuario.mention}" if success else "ℹ️ Nada para remover")
        except Exception as e:
            await ctx.send(f"💣 Erro: {e}")
            logger.error(f"Erro ao desvincular YouTube: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
