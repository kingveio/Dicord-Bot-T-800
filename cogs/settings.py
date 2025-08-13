import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="configurar", description="Configura o bot no servidor")
    @commands.has_permissions(administrator=True)
    async def setup_bot(self, ctx, cargo: discord.Role, canal: discord.TextChannel):
        await self.bot.data_manager.update_guild_config(
            ctx.guild.id,
            live_role_id=cargo.id,
            notify_channel_id=canal.id
        )
        quote = await self.bot.log_action(f"Configuração atualizada em {ctx.guild.name}")
        await ctx.send(
            f"⚙️ **Configurações atualizadas:**\n"
            f"- Cargo Live: {cargo.mention}\n"
            f"- Canal de Notificações: {canal.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

    @commands.hybrid_command(name="remover_usuario", description="Remove TODOS os vínculos de um usuário")
    @commands.has_permissions(administrator=True)
    async def purge_user(self, ctx, usuario: discord.Member):
        success = await self.bot.data_manager.remove_account(
            ctx.guild.id,
            usuario.id
        )
        quote = await self.bot.log_action(f"Usuário {usuario.display_name} removido completamente")
        await ctx.send(
            f"🧹 **Todos vínculos removidos de** {usuario.mention}\n"
            f"*{quote}*",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Settings(bot))
