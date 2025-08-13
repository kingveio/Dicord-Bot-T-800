import discord
from discord.ext import commands, tasks
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI
from data.data_manager import DataManager

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()
        self.data_manager = DataManager()
        self.monitoring_task.start()

    def cog_unload(self):
        self.monitoring_task.cancel()
        print("T-800: Vigilância cancelada.")

    @commands.Cog.listener()
    async def on_ready(self):
        print("T-800: Vigilância multi-servidor ativada.")

    @tasks.loop(minutes=5)
    async def monitoring_task(self):
        print("T-800: Iniciando ciclo de escaneamento de lives em todos os servidores.")
        
        for guild in self.bot.guilds:
            guild_data = self.data_manager.get_guild_data(guild.id)
            live_role_id = guild_data.get("live_role_id")
            users_to_check = guild_data.get("users", {})

            if not live_role_id:
                print(f"T-800: Missão pendente no servidor {guild.name}. Nenhum cargo de live definido.")
                continue

            live_role = guild.get_role(live_role_id)
            if not live_role:
                print(f"T-800: Cargo {live_role_id} não encontrado no servidor {guild.name}.")
                continue

            for user_id_str, channels in users_to_check.items():
                member = guild.get_member(int(user_id_str))
                if not member:
                    continue

                is_live = False

                if channels.get("twitch"):
                    if await self.twitch_api.is_live(channels["twitch"]):
                        is_live = True
                        print(f"T-800: Twitch live detectada para {member.name} em {guild.name}.")

                if channels.get("youtube") and not is_live:
                    channel_id = await self.youtube_api.get_channel_id(channels["youtube"])
                    if channel_id and await self.youtube_api.is_live(channel_id):
                        is_live = True
                        print(f"T-800: YouTube live detectada para {member.name} em {guild.name}.")

                if is_live:
                    if live_role not in member.roles:
                        await member.add_roles(live_role)
                        print(f"T-800: Cargo {live_role.name} atribuído a {member.name}.")
                else:
                    if live_role in member.roles:
                        await member.remove_roles(live_role)
                        print(f"T-800: Cargo {live_role.name} removido de {member.name}.")

async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
