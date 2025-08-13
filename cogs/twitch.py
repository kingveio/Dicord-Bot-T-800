import discord
from discord.ext import commands

class TwitchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="adicionar_twitch")
    @commands.has_permissions(administrator=True)
    async def add_twitch(self, ctx, canal: str, usuario: discord.Member):
        """Vincula uma conta Twitch a um usuário"""
        # Exemplo: !adicionar_twitch kingveio @user
        success = await self.bot.data_manager.link_account(
            ctx.guild.id,
            usuario,
            "twitch",
            canal.lower().strip()
        )
        await ctx.send(f"✅ Twitch `{canal}` vinculado a {usuario.mention}" if success else "❌ Falha ao vincular")

    @commands.command(name="remover_twitch")
    @commands.has_permissions(administrator=True)
    async def remove_twitch(self, ctx, usuario: discord.Member):
        """Remove vínculo da Twitch"""
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id,
            "twitch"
        )
        await ctx.send(f"🗑️ Twitch desvinculado de {usuario.mention}" if success else "ℹ️ Nada para remover")

async def setup(bot):
    await bot.add_cog(TwitchCommands(bot))
