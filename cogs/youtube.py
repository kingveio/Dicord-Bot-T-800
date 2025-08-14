import discord
from discord import app_commands
from discord.ext import commands
import logging
from config import Config

logger = logging.getLogger(__name__)

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
        # ✅ CORREÇÃO: Use defer para responder imediatamente e evitar timeout
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # O ID da guilda e do usuário são obtidos da interação
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild.id,
                usuario.id,
                "youtube",
                canal
            )
            
            if success:
                # ✅ Use followup.send após o defer
                await interaction.followup.send(f"✅ Canal YouTube `{canal}` vinculado a {usuario.mention}")
            else:
                await interaction.followup.send("❌ Falha ao vincular canal")
            
        except Exception as e:
            logger.error(f"Erro no comando YouTube: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação")

    @app_commands.command(name="remover_youtube", description="Remove o vínculo de um canal YouTube de um usuário")
    @app_commands.describe(
        usuario="O usuário do Discord para remover o vínculo"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_youtube(self, interaction: discord.Interaction, usuario: discord.Member):
        """Remove o vínculo do YouTube"""
        # ✅ CORREÇÃO: Use defer para responder imediatamente e evitar timeout
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            success = await self.bot.data_manager.remove_account(
                interaction.guild.id,
                usuario.id,
                "youtube"
            )
            
            if success:
                # ✅ Use followup.send após o defer
                await interaction.followup.send(f"🗑️ YouTube desvinculado de {usuario.mention}")
            else:
                await interaction.followup.send("ℹ️ Nada para remover")
        except Exception as e:
            logger.error(f"Erro ao desvincular YouTube: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação")

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
