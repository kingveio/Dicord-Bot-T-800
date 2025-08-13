import discord
from discord import app_commands
from discord.ext import commands

class YouTubeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="vincular_youtube",
        description="Vincula um canal YouTube a um usuário (Admin)"
    )
    @app_commands.describe(
        canal="Nome ou ID do canal YouTube",
        usuario="Usuário do Discord"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_vincular(self, interaction: discord.Interaction, canal: str, usuario: discord.Member):
        try:
            # Lógica de vinculação aqui
            await interaction.response.send_message(
                f"✅ YouTube vinculado: {canal} → {usuario.mention}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Erro: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(YouTubeCommands(bot))
