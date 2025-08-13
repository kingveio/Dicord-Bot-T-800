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
        self.monitor.start()

    def cog_unload(self):
        self.monitor.cancel()

    @tasks.loop(minutes=5.0)
    async def monitor(self):
        """Tarefa periódica para verificar lives"""
        try:
            await self.bot.wait_until_ready()
            
            for guild in self.bot.guilds:
                # Obtém dados da guilda (sem await)
                guild_data = self.bot.data_manager.get_guild(guild.id)
                
                # Verifica se há configuração de cargo de live
                if not guild_data["config"]["live_role_id"]:
                    continue
                    
                live_role = guild.get_role(guild_data["config"]["live_role_id"])
                if not live_role:
                    logger.warning(f"Cargo de live não encontrado na guilda {guild.id}")
                    continue

                # Verifica cada usuário cadastrado
                for user_id_str, user_data in guild_data["users"].items():
                    user_id = int(user_id_str)
                    member = guild.get_member(user_id)
                    if not member:
                        continue
                    
                    # Verificação Twitch
                    if user_data.get("twitch"):
                        await self._check_platform(
                            member=member,
                            role=live_role,
                            platform_data=user_data["twitch"],
                            platform_name="Twitch",
                            check_func=self.bot.twitch_api.is_live
                        )
                    
                    # Verificação YouTube
                    if user_data.get("youtube"):
                        await self._check_platform(
                            member=member,
                            role=live_role,
                            platform_data=user_data["youtube"],
                            platform_name="YouTube",
                            check_func=self.bot.youtube_api.is_live
                        )
                        
        except Exception as e:
            logger.error(f"Erro no monitoramento: {e}", exc_info=True)

    async def _check_platform(
        self,
        member: discord.Member,
        role: discord.Role,
        platform_data: dict,
        platform_name: str,
        check_func
    ):
        """Método genérico para verificação de plataforma"""
        try:
            is_live, title = await check_func(platform_data["username"])
            
            if is_live:
                platform_data["last_live"] = datetime.now().isoformat()
                platform_data["is_live"] = True
                
                if role not in member.roles:
                    await member.add_roles(role)
                    logger.info(f"{member.display_name} entrou em live na {platform_name}")
                    
                    # Envia notificação se configurado
                    guild_data = self.bot.data_manager.get_guild(member.guild.id)
                    if guild_data["config"]["notify_channel_id"]:
                        channel = member.guild.get_channel(guild_data["config"]["notify_channel_id"])
                        if channel:
                            await channel.send(
                                f"🎮 {member.mention} está ao vivo na {platform_name}!\n"
                                f"**{title}**"
                            )
            else:
                platform_data["is_live"] = False
                if role in member.roles:
                    await member.remove_roles(role)
                    
        except Exception as e:
            logger.error(f"Erro ao verificar {platform_name}: {e}")

async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
