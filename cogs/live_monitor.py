import discord
from discord.ext import commands, tasks
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI
from data.data_manager import DataManager
import logging

logger = logging.getLogger(__name__)

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch = TwitchAPI()
        self.youtube = YouTubeAPI()
        self.data = DataManager()
        self.monitor.start()
    
    def cog_unload(self):
        self.monitor.cancel()
    
    @tasks.loop(minutes=5.0)
    async def monitor(self):
        await self.bot.wait_until_ready()
        
        for guild in self.bot.guilds:
            guild_data = self.data.get_guild(guild.id)
            if not guild_data.get("config", {}).get("live_role_id"):
                continue
                
            for user_id, user_data in guild_data.get("users", {}).items():
                member = guild.get_member(int(user_id))
                if not member:
                    continue
                
                is_live = False
                live_role = guild.get_role(guild_data["config"]["live_role_id"])
                
                # Check Twitch
                if user_data.get("twitch"):
                    is_live = await self.twitch.is_live(user_data["twitch"])
                
                # Check YouTube if not live on Twitch
                if not is_live and user_data.get("youtube"):
                    is_live = await self.youtube.is_live(user_data["youtube"])
                
                # Update role
                if live_role:
                    if is_live and live_role not in member.roles:
                        await member.add_roles(live_role)
                        logger.info(f"Added live role to {member.display_name}")
                    elif not is_live and live_role in member.roles:
                        await member.remove_roles(live_role)
                        logger.info(f"Removed live role from {member.display_name}")

async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
