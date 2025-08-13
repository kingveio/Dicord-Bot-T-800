import discord
from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="configurar")
    @commands.has_permissions(administrator=True)
    async def setup_bot(self, ctx, cargo: discord.Role, canal: discord.TextChannel):
        """Configura o sistema de notificações"""
        # Exemplo: !configurar @CargoLive #canal-notificacoes
        await self.bot.data_manager.update_guild_config(
            ctx.guild.id,
            live_role_id=cargo.id,
            notify_channel_id=canal.id
        )
        await ctx.send(
            f"⚙️ **Configurações atualizadas:**\n"
            f"- Cargo Live: {cargo.mention}\n"
            f"- Canal de Notificações: {canal.mention}"
        )

    @commands.command(name="remover_usuario")
    @commands.has_permissions(administrator=True)
    async def purge_user(self, ctx, usuario: discord.Member):
        """Remove TODOS os vínculos de um usuário"""
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id
        )
        await ctx.send(f"🧹 Todos vínculos removidos de {usuario.mention}" if success else "ℹ️ Nada para remover")

async def setup(bot):
    await bot.add_cog(Settings(bot))
