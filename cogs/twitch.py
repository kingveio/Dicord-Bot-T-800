import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="vincular_twitch",
        description="Vincula sua conta da Twitch ao bot"
    )
    @app_commands.describe(
        nome_usuario="Seu nome de usuário na Twitch"
    )
    async def link_twitch(
        self,
        interaction: discord.Interaction,
        nome_usuario: str
    ):
        try:
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild.id,
                interaction.user.id,
                "twitch",
                nome_usuario.lower().strip()
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Conta Twitch `{nome_usuario}` vinculada com sucesso!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Falha ao vincular conta Twitch",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao vincular Twitch: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

    @app_commands.command(
        name="desvincular_twitch",
        description="Remove o vínculo da sua conta Twitch"
    )
    async def unlink_twitch(self, interaction: discord.Interaction):
        try:
            removed = await self.bot.data_manager.remove_user_platform(
                interaction.guild.id,
                interaction.user.id,
                "twitch"
            )
            
            if removed:
                await interaction.response.send_message(
                    "✅ Conta Twitch desvinculada com sucesso!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ Você não tinha uma conta Twitch vinculada",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao desvincular Twitch: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
