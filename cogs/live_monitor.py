import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_check = {}
        self.check_interval = timedelta(minutes=5)
        
        # Inicia a tarefa somente após o bot estar pronto
        self.monitor.start()

    def cog_unload(self):
        self.monitor.cancel()

    @tasks.loop(minutes=5.0)
    async def monitor(self):
        try:
            await self.bot.wait_until_ready()
            
            for guild in self.bot.guilds:
                guild_data = await self.bot.data_manager.get_guild(guild.id)
                if not guild_data.config.live_role_id:
                    continue
                    
                live_role = guild.get_role(guild_data.config.live_role_id)
                if not live_role:
                    continue

                for user_id, user_data in guild_data.users.items():
                    member = guild.get_member(user_id)
                    if not member:
                        continue
                    
                    # Verificar Twitch
                    twitch_status = None
                    if user_data.twitch:
                        twitch_status = await self._check_twitch(user_data.twitch.username, member, live_role)
                    
                    # Verificar YouTube se não estiver live na Twitch
                    if not twitch_status and user_data.youtube:
                        await self._check_youtube(user_data.youtube.username, member, live_role)
        except Exception as e:
            logger.error(f"Erro no monitoramento: {e}")

    async def _check_twitch(self, username: str, member: discord.Member, role: discord.Role) -> bool:
        """Verifica status na Twitch e atualiza cargo"""
        is_live, title = await self.bot.twitch_api.is_live(username)
        
        if is_live and role not in member.roles:
            await member.add_roles(role)
            if self.bot.discord_service.get_guild(member.guild.id).config.notify_channel_id:
                await self.bot.discord_service.send_notification(
                    member.guild.id,
                    f"🎮 {member.mention} está ao vivo na Twitch!\n**{title}**"
                )
            return True
        
        elif not is_live and role in member.roles:
            await member.remove_roles(role)
        
        return False

    async def _check_youtube(self, username: str, member: discord.Member, role: discord.Role) -> bool:
        """Verifica status no YouTube e atualiza cargo"""
        is_live, title = await self.bot.youtube_api.is_live(username)
        
        if is_live and role not in member.roles:
            await member.add_roles(role)
            if self.bot.discord_service.get_guild(member.guild.id).config.notify_channel_id:
                await self.bot.discord_service.send_notification(
                    member.guild.id,
                    f"🎥 {member.mention} está ao vivo no YouTube!\n**{title}**"
                )
            return True
        
        elif not is_live and role in member.roles:
            await member.remove_roles(role)
        
        return False

async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
