import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Vincular Twitch',
            callback=self.vincular_twitch_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    @app_commands.command(name="vincular_twitch", description="Vincula uma conta Twitch")
    @app_commands.describe(
        usuario="Usuário do Discord",
        nome_twitch="Nome de usuário na Twitch"
    )
    async def vincular_twitch(self, interaction: discord.Interaction, usuario: discord.Member, nome_twitch: str):
        try:
            success = await self.bot.data_manager.link_account(
                interaction.guild.id,
                usuario.id,
                "twitch",
                nome_twitch.lower().strip()
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Twitch `{nome_twitch}` vinculado a {usuario.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Falha ao vincular conta Twitch",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro ao vincular Twitch: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação",
                ephemeral=True
            )

    async def vincular_twitch_context(self, interaction: discord.Interaction, member: discord.Member):
        modal = TwitchModal(member)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
