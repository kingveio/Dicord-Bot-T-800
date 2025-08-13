import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="vincular_youtube",
        description="Vincula seu canal do YouTube ao bot"
    )
    @app_commands.describe(
        identificador="Nome do canal ou ID"
    )
    async def link_youtube(
        self,
        interaction: discord.Interaction,
        identificador: str
    ):
        try:
            # Verifica se é um nome de usuário ou ID
            if identificador.startswith("UC"):
                channel_id = identificador
            else:
                channel_id = await self.bot.youtube_api.get_channel_id(identificador)
                if not channel_id:
                    await interaction.response.send_message(
                        "❌ Canal não encontrado. Verifique o nome ou use o ID do canal",
                        ephemeral=True
                    )
                    return

            success = await self.bot.data_manager.link_user_platform(
                interaction.guild.id,
                interaction.user.id,
                "youtube",
                channel_id
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Canal YouTube vinculado com sucesso! (ID: `{channel_id}`)",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Falha ao vincular canal YouTube",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao vincular YouTube: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

    @app_commands.command(
        name="desvincular_youtube",
        description="Remove o vínculo do seu canal YouTube"
    )
    async def unlink_youtube(self, interaction: discord.Interaction):
        try:
            removed = await self.bot.data_manager.remove_user_platform(
                interaction.guild.id,
                interaction.user.id,
                "youtube"
            )
            
            if removed:
                await interaction.response.send_message(
                    "✅ Canal YouTube desvinculado com sucesso!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ Você não tinha um canal YouTube vinculado",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao desvincular YouTube: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
