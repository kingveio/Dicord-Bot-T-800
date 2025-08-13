import discord
from discord.ext import commands
import logging
from discord import app_commands

logger = logging.getLogger(__name__)

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="configurar",
        description="Configura os parâmetros do bot no servidor"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        cargo="Cargo para membros em live",
        canal="Canal de notificações"
    )
    async def configure(
        self,
        interaction: discord.Interaction,
        cargo: discord.Role,
        canal: discord.TextChannel
    ):
        try:
            guild_id = interaction.guild.id
            await self.bot.data_manager.update_guild_config(
                guild_id,
                live_role_id=cargo.id,
                notify_channel_id=canal.id
            )
            
            await interaction.response.send_message(
                f"⚙️ Configurações atualizadas:\n"
                f"- Cargo de Live: {cargo.mention}\n"
                f"- Canal de Notificações: {canal.mention}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro na configuração: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao atualizar as configurações",
                ephemeral=True
            )

    @configure.error
    async def configure_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "⚠️ Você precisa ser administrador para usar este comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ocorreu um erro inesperado",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Settings(bot))
