# T-800: Módulo de calibração. Definindo parâmetros de missão por servidor.
import discord
from discord.ext import commands
from data.data_manager import DataManager

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    # Comando de barra /setar_cargo
    @discord.app_commands.command(
        name="setar_cargo",
        description="Define o cargo que será atribuído a streamers em live."
    )
    @discord.app_commands.describe(
        cargo="O cargo que será atribuído (mencione-o ou use o ID)."
    )
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_live_role(self, interaction: discord.Interaction, cargo: discord.Role):
        guild_id = interaction.guild.id
        self.data_manager.set_live_role_id(guild_id, cargo.id)
        await interaction.response.send_message(f"A diretiva de missão foi atualizada. O cargo '{cargo.name}' será atribuído a streamers em live.", ephemeral=True)

    @set_live_role.error
    async def set_live_role_error(self, interaction: discord.Interaction, error):
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("Comando não autorizado. Apenas o administrador pode definir a diretiva de missão.", ephemeral=True)
        else:
            await interaction.response.send_message("O T-800 não reconhece esse cargo. Por favor, mencione o cargo ou use seu ID.", ephemeral=True)

def setup(bot):
    bot.add_cog(Settings(bot))
