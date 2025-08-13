import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
import random

logger = logging.getLogger(__name__)

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_role = None
        self.check_live.start()

    @tasks.loop(minutes=5)
    async def check_live(self):
        try:
            await self.bot.wait_until_ready()
            
            for guild in self.bot.guilds:
                # Verifica se data_manager existe
                if not hasattr(self.bot, 'data_manager'):
                    raise AttributeError("DataManager não inicializado")
                
                guild_data = self.bot.data_manager.get_guild(guild.id)
                
                # Verifica se as configurações existem
                if not guild_data.get("live_role_id"):
                    continue
                
                self.live_role = guild.get_role(guild_data["live_role_id"])
                if not self.live_role:
                    continue
                except Exception as e:
                logger.error(f"Erro no check_live: {e}", exc_info=True)
                # Reinicia a tarefa após 5 minutos se falhar
                await asyncio.sleep(300)
                self.check_live.restart()
                # Verifica todas as plataformas
                live_status = {}
                for platform, data in user_data["platforms"].items():
                    is_live = await self._check_platform(data["channel_id"], platform)
                    live_status[platform] = is_live
                    if is_live and not data["is_live"]:
                        await self._notify_live(member, platform)
                    data["is_live"] = is_live
                
                # Atualiza cargo
                await self._update_live_role(member, live_status)

    async def _check_platform(self, channel_id, platform):
        """Verifica se um canal está live"""
        if platform == "youtube":
            return await self.bot.youtube_api.is_live(channel_id)
        elif platform == "twitch":
            return await self.bot.twitch_api.is_live(channel_id)
        return False

    async def _notify_live(self, member, platform):
        """Notifica quando um usuário entra em live"""
        quote = random.choice([
            f"Target acquired: {member.display_name} is LIVE on {platform}",
            f"Mission: Notify {member.mention}'s stream",
            "Terminate boredom: Stream online!"
        ])
        channel = self.bot.get_channel(self.bot.data_manager.get_guild(member.guild.id)["notify_channel_id"])
        await channel.send(f"🎮 {member.mention} está ao vivo!\n*{quote}*")

    async def _update_live_role(self, member, live_status):
        """Gerencia o cargo 'AO VIVO' sem flickering"""
        should_have_role = any(live_status.values())
        has_role = self.live_role in member.roles
        
        if should_have_role and not has_role:
            await member.add_roles(self.live_role)
            await self.bot.log_action(f"Cargo concedido a {member.display_name}")
        elif not should_have_role and has_role:
            await member.remove_roles(self.live_role)
            await self.bot.log_action(f"Cargo removido de {member.display_name}")

async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
