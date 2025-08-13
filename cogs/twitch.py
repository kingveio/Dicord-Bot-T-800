import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchModal(discord.ui.Modal, title='Vincular Conta Twitch'):
    def __init__(self, member):
        super().__init__()
        self.member = member
        self.nome_twitch = discord.ui.TextInput(
            label='Nome na Twitch',
            placeholder='Digite o nome de usuário da Twitch',
            min_length=3,
            max_length=25
        )
        self.add_item(self.nome_twitch)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            success = await interaction.client.data_manager.link_account(
                interaction.guild.id,
                self.member.id,
                "twitch",
                self.nome_twitch.value.lower().strip()
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Twitch `{self.nome_twitch.value}` vinculado a {self.member.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Falha ao vincular conta Twitch",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro no TwitchModal: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Erro interno: {str(e)}",
                ephemeral=True
            )

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Vincular Twitch',
            callback=self.vincular_twitch_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def vincular_twitch_context(self, interaction: discord.Interaction, member: discord.Member):
        """Menu de contexto para vincular Twitch"""
        modal = TwitchModal(member)
        await interaction.response.send_modal(modal)
        logger.info(f"Modal aberto para {member.display_name}")

    @app_commands.command(name="vincular_twitch", description="Vincula uma conta Twitch a um usuário")
    @app_commands.describe(
        usuario="Usuário do Discord para vincular",
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

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
