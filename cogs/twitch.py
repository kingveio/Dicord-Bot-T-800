import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="adicionar_twitch", description="Vincula uma conta Twitch a um usuário")
    @app_commands.describe(
        usuario="Usuário do Discord para adicionar",
        nome_twitch="Nome de usuário na Twitch"
    )
    async def vincular_twitch(self, interaction: discord.Interaction, usuario: discord.Member, nome_twitch: str):
        """Implementação do comando de vincular Twitch"""
        try:
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild.id,
                usuario.id,
                "twitch",
                nome_twitch.lower().strip()
            )
            
            await interaction.response.send_message(
                f"✅ Conta Twitch `{nome_twitch}` vinculada a {usuario.mention}" if success 
                else "❌ Falha ao vincular conta",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro no comando twitch: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
