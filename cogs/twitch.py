import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="adicionar_twitch", description="Adiciona um canal da Twitch para ser monitorado")
    @app_commands.describe(
        usuario="Usuário do Discord para adicionar",
        username="O nome de usuário da Twitch"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def vincular_twitch(self, interaction: discord.Interaction, usuario: discord.Member, username: str):
        """Adiciona um canal da Twitch a um usuário"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # ✅ CORREÇÃO: Usando o método '_get_user_id' que existe em TwitchAPI
            user_id = await self.bot.twitch_api._get_user_id(username)
            
            if not user_id:
                await interaction.followup.send(f"❌ Não foi possível encontrar o canal **{username}** na Twitch. Verifique o nome de usuário.")
                return
            
            success = await self.bot.data_manager.link_user_platform(
                interaction.guild_id, usuario.id, "twitch", username
            )
            
            if success:
                embed = discord.Embed(
                    title="Twitch adicionado com sucesso!",
                    description=f"O canal **{username}** agora está vinculado a conta de {usuario.mention}.",
                    color=discord.Color.purple()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"❌ Ocorreu um erro ao vincular o canal.")
            
        except Exception as e:
            logger.error(f"Erro no comando adicionar_twitch: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro inesperado: {e}")

    @app_commands.command(name="remover_twitch", description="Remove o vínculo de uma conta Twitch de um usuário")
    @app_commands.describe(
        usuario="Usuário do Discord para remover o vínculo"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remover_twitch(self, interaction: discord.Interaction, usuario: discord.Member):
        """Remove o vínculo da Twitch de um usuário"""
        # ✅ PASSO 1: Acknowledge a interação imediatamente com `defer`.
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            success = await self.bot.data_manager.remove_account(
                interaction.guild_id, usuario.id, "twitch"
            )
            
            if success:
                await interaction.followup.send(f"🗑️ Vínculo da Twitch removido de {usuario.mention} com sucesso.")
            else:
                await interaction.followup.send(f"ℹ️ {usuario.mention} não tinha um vínculo da Twitch para remover.")
        except Exception as e:
            logger.error(f"Erro ao remover vínculo da Twitch: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro inesperado: {e}")

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
