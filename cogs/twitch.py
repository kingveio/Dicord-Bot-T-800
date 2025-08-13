import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="vincular_twitch", description="Vincula uma conta Twitch a um usuário")
    @commands.has_permissions(administrator=True)
    async def link_twitch(self, ctx, canal: str, usuario: discord.Member):
        success = await self.bot.data_manager.link_account(
            ctx.guild.id,
            usuario,
            "twitch",
            canal.lower().strip()
        )
        quote = await self.bot.log_action(f"Twitch vinculado a {usuario.display_name}")
        await ctx.send(
            f"✅ Conta **{canal}** vinculada a {usuario.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

    @commands.hybrid_command(name="remover_twitch", description="Remove vínculo da Twitch")
    @commands.has_permissions(administrator=True)
    async def unlink_twitch(self, ctx, usuario: discord.Member):
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id,
            "twitch"
        )
        quote = await self.bot.log_action(f"Twitch desvinculado de {usuario.display_name}")
        await ctx.send(
            f"🗑️ Twitch desvinculado de {usuario.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
