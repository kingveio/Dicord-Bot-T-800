# cogs/twitch.py
import discord
from discord.ext import commands
from data.data_manager import DataManager

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    @discord.app_commands.command(
        name="adicionar_twitch",
        description="Vincula seu canal da Twitch para monitoramento de lives"
    )
    async def add_twitch(self, interaction: discord.Interaction, username: str):
        self.data_manager.add_user(
            interaction.guild.id,
            interaction.user.id,
            twitch_name=username.lower().strip()
        )
        await interaction.response.send_message(
            f"✅ Twitch `{username}` vinculada com sucesso!",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="remover_twitch",
        description="Remove seu canal da Twitch do monitoramento"
    )
    async def remove_twitch(self, interaction: discord.Interaction):
        success = self.data_manager.remove_user_platform(
            interaction.guild.id,
            interaction.user.id,
            platform="twitch"
        )
        response = "✅ Twitch removida!" if success else "ℹ️ Nenhum canal Twitch vinculado."
        await interaction.response.send_message(response, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
