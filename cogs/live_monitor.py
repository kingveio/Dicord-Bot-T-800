# T-800: Módulo de vigilância. Escaneando alvos em tempo real.
import discord
from discord.ext import commands, tasks
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI
from services.discord_service import DiscordService
from data.data_manager import DataManager
from config import GUILD_ID, LIVE_ROLE_ID

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        self.data_manager = DataManager()
        self.discord_service = DiscordService(bot)
        self.monitoring_task.start()

    def cog_unload(self):
        self.monitoring_task.cancel()
        print("T-800: Vigilância cancelada.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.discord_service.setup_guild(int(GUILD_ID))
        print("T-800: Vigilância ativada.")

    @tasks.loop(minutes=5)
    async def monitoring_task(self):
        # Ciclo de vigilância. Verificando todos os alvos a cada 5 minutos.
        print("T-800: Iniciando ciclo de escaneamento de lives.")
        users_to_check = self.data_manager.get_users()

        for user_id_str, channels in users_to_check.items():
            member = self.discord_service.guild.get_member(int(user_id_str))
            if not member:
                continue

            is_live = False

            # Verificando Twitch
            if channels.get("twitch"):
                if await self.twitch_api.is_live(channels["twitch"]):
                    is_live = True
                    print(f"T-800: Twitch live detectada para {member.name}.")

            # Verificando YouTube
            if channels.get("youtube") and not is_live: # Só checa se ainda não achou uma live
                channel_id = await self.youtube_api.get_channel_id(channels["youtube"])
                if channel_id and await self.youtube_api.is_live(channel_id):
                    is_live = True
                    print(f"T-800: YouTube live detectada para {member.name}.")

            if is_live:
                await self.discord_service.give_role(member, int(LIVE_ROLE_ID))
            else:
                await self.discord_service.remove_role(member, int(LIVE_ROLE_ID))

def setup(bot):
    bot.add_cog(LiveMonitor(bot))
    print("T-800: Módulo de vigilância online.")
