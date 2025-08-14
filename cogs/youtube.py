import discord
from discord import app_commands
from discord.ext import commands
import logging
from config import Config

logger = logging.getLogger(__name__)

# Nota: A classe YouTubeAPI pode estar em 'services/youtube_api.py'.
# Se for o caso, você pode remover esta classe do arquivo e usar
# self.bot.youtube_api diretamente, como no __init__.
class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="adicionar_youtube", description="Vincula um canal YouTube a um usuário")
    @app_commands.describe(
        canal="O nome do canal do YouTube",
        usuario="O usuário do Discord a ser vinculado"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_youtube(self, interaction: discord.Interaction, canal: str, usuario: discord.Member):
        """Implementação do comando de vincular YouTube"""
        try:
            # O ID da guilda e do usuário são obtidos da interação
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild.id,
                usuario.id,
                "youtube",
                canal
            )
            
            await interaction.response.send_message(
                f"✅ Canal YouTube `{canal}` vinculado a {usuario.mention}" if success
                else "❌ Falha ao vincular canal",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro no comando YouTube: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

    @app_commands.command(name="remover_youtube", description="Remove o vínculo de um canal YouTube de um usuário")
    @app_commands.describe(
        usuario="O usuário do Discord para remover o vínculo"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_youtube(self, interaction: discord.Interaction, usuario: discord.Member):
        """Remove o vínculo do YouTube"""
        try:
            success = await self.bot.data_manager.remove_account(
                interaction.guild.id,
                usuario.id,
                "youtube"
            )
            
            await interaction.response.send_message(
                f"🗑️ YouTube desvinculado de {usuario.mention}" if success
                else "ℹ️ Nada para remover",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro ao desvincular YouTube: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
