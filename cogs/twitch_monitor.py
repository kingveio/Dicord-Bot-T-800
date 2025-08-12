
import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime

logger = logging.getLogger("T-800")

class TwitchMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_role_name = "AO VIVO"
        self.monitor.start()
        logger.info("✅ Modo de vigilância Twitch ativado. 'Come with me if you want to live.'")

    @tasks.loop(minutes=5)
    async def monitor(self):
        if not self.bot.system_ready:
            return

        logger.info("🔍 Varredura de alvos Twitch iniciada. 'Scanning for targets...'")
        
        try:
            data = self.bot.data
            streamers = data["monitored_users"]["twitch"]
            
            if not streamers:
                logger.info("Nenhum alvo registrado. 'No targets found.'")
                return

            live_status = await self.bot.twitch_api.check_live_channels(list(streamers.keys()))
            
            for streamer, is_live in live_status.items():
                user_info = streamers.get(streamer)
                if not user_info:
                    continue

                guild = self.bot.get_guild(user_info["guild_id"])
                member = guild.get_member(user_info["added_by"]) if guild else None
                if not member:
                    continue

                live_role = discord.utils.get(guild.roles, name=self.live_role_name)
                if not live_role:
                    logger.warning(f"❌ Cargo '{self.live_role_name}' não encontrado. 'Target role missing.'")
                    continue

                if is_live and live_role not in member.roles:
                    await member.add_roles(live_role)
                    logger.info(f"✅ {member.name} está AO VIVO. 'You're terminated.'")
                elif not is_live and live_role in member.roles:
                    await member.remove_roles(live_role)
                    logger.info(f"✅ {member.name} offline. 'Mission accomplished.'")

        except Exception as e:
            logger.error(f"❌ Falha na vigilância: {e}. 'System malfunction.'")

async def setup(bot):
    await bot.add_cog(TwitchMonitor(bot))
