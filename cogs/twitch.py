import discord
from discord.ext import commands
from data.data_manager import DataManager

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    @discord.app_commands.command(
        name="adicionar_twitch",
        description="Adiciona o seu canal da Twitch à lista de monitoramento de lives."
    )
    @discord.app_commands.describe(
        username="O nome de usuário do seu canal na Twitch"
    )
    async def add_twitch_user(self, interaction: discord.Interaction, username: str):
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        self.data_manager.add_user(guild_id, user_id, twitch_name=username)
        
        await interaction.response.send_message(
            f"Alvo '{username}' adicionado à lista de vigilância da Twitch para este servidor. Eu voltarei a verificar.",
            ephemeral=True
        )
    @discord.app_commands.command(
    name="remover_twitch",
    description="Remove seu canal da Twitch do monitoramento"
)
async def remover_twitch(self, interaction: discord.Interaction):
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    self.data_manager.remove_user_platform(guild_id, user_id, platform="twitch")
    await interaction.response.send_message("✅ Canal da Twitch removido com sucesso!", ephemeral=True)
    
async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
