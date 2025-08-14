import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="adicionar_twitch", description="Adiciona um canal da Twitch para ser monitorado")
    @app_commands.describe(username="O nome de usuário da Twitch")
    async def vincular_twitch(self, interaction: discord.Interaction, username: str):
        """Adiciona um canal da Twitch a um usuário"""
        await interaction.response.send_message(f"Verificando o canal '{username}' na Twitch...", ephemeral=True)
        
        try:
            channel_id = await self.bot.twitch_api.get_channel_id(username)
            if not channel_id:
                return await interaction.followup.send(f"❌ Não foi possível encontrar o canal **{username}** na Twitch. Verifique o nome de usuário.")
            
            # Chama a função do DataManager para vincular o usuário e a plataforma
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild_id, interaction.user.id, "twitch", username
            )
            
            if success:
                embed = discord.Embed(
                    title="Twitch adicionado com sucesso!",
                    description=f"O canal **{username}** agora está vinculado a sua conta no servidor. Você receberá notificações quando ele entrar em live.",
                    color=discord.Color.purple()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"❌ Ocorreu um erro ao vincular seu canal.")
                
        except Exception as e:
            logger.error(f"Erro no comando twitch: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro inesperado: {e}")

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
