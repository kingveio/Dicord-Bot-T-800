import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone
import random
import asyncio
from typing import Optional

# Os imports abaixo precisam ser ajustados conforme sua estrutura
from data.data_manager import DataManager
from config import Config
from services.twitch_api import TwitchAPI
from services.youtube_api import YouTubeAPI

logger = logging.getLogger(__name__)

class LiveMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.live_role = None
        self.check_live.start()

    def cog_unload(self):
        self.check_live.cancel()
        
    @tasks.loop(minutes=Config.LIVE_CHECK_INTERVAL_MINUTES)
    async def check_live(self):
        """Verifica se os streamers estão online e envia notificações"""
        await self.bot.wait_until_ready()
        
        # Cria um lock para evitar que o DataManager seja acessado de forma concorrente
        async with self.bot.data_manager._lock:
            for guild in self.bot.guilds:
                try:
                    guild_data = self.bot.data_manager.get_guild(guild.id)
                    
                    # Acessa os dados como dicionário, usando .get() para evitar KeyError
                    live_role_id = guild_data['config'].get('live_role_id')
                    notify_channel_id = guild_data['config'].get('notify_channel_id')
                    
                    if not live_role_id or not notify_channel_id:
                        continue # Pula se as configurações estiverem incompletas
                    
                    live_role = guild.get_role(int(live_role_id))
                    notify_channel = guild.get_channel(int(notify_channel_id))
                    
                    if not live_role or not notify_channel:
                        continue # Pula se o cargo ou canal não forem encontrados

                    # Acessa a lista de usuários como um dicionário
                    for user_id_str, user_data in guild_data['users'].items():
                        member = guild.get_member(int(user_id_str))
                        if not member:
                            continue
                        
                        # Acessa as plataformas como chaves de dicionário, usando .get()
                        if user_data.get('twitch'):
                            twitch_data = user_data['twitch']
                            is_live, title = await self.bot.twitch_api.is_live(twitch_data['username'])
                            await self._update_platform_status(
                                member=member,
                                platform_data=twitch_data,
                                is_live=is_live,
                                title=title,
                                notify_channel=notify_channel,
                                platform_name="Twitch",
                                live_role=live_role
                            )
                            
                        if user_data.get('youtube'):
                            youtube_data = user_data['youtube']
                            is_live, title = await self.bot.youtube_api.is_live(youtube_data['username'])
                            await self._update_platform_status(
                                member=member,
                                platform_data=youtube_data,
                                is_live=is_live,
                                title=title,
                                notify_channel=notify_channel,
                                platform_name="YouTube",
                                live_role=live_role
                            )
                            
                except Exception as e:
                    logger.error(f"Erro no check_live para a guilda {guild.id}: {e}", exc_info=True)

            # Salva o estado atualizado dos dados uma única vez, após o loop de todas as guildas
            await self.bot.data_manager.save()

    async def _update_platform_status(
        self,
        member: discord.Member,
        platform_data: dict, # O tipo é um dicionário
        is_live: bool,
        title: Optional[str],
        notify_channel: discord.TextChannel,
        platform_name: str,
        live_role: discord.Role
    ):
        """Lógica central para verificar e notificar status de live"""
        
        # Atualiza o timestamp da última verificação
        platform_data['last_checked'] = datetime.now(timezone.utc).isoformat()

        # Lógica de notificação e atualização de cargo
        if is_live and not platform_data.get('is_live'):
            # Usuário entrou em live
            platform_data['is_live'] = True
            platform_data['last_live_title'] = title
            
            await self._notify_live(member, platform_name, title, notify_channel)
            await self._manage_live_role(member, live_role, True)
            
        elif not is_live and platform_data.get('is_live'):
            # Usuário saiu da live
            platform_data['is_live'] = False
            
            # Verifica se o membro ainda está em live em outra plataforma antes de remover o cargo
            other_platform_live = False
            user_data = self.bot.data_manager.get_guild(member.guild.id)['users'].get(str(member.id))
            if user_data:
                if platform_name == "Twitch" and user_data.get('youtube') and user_data['youtube'].get('is_live'):
                    other_platform_live = True
                elif platform_name == "YouTube" and user_data.get('twitch') and user_data['twitch'].get('is_live'):
                    other_platform_live = True
            
            if not other_platform_live:
                await self._manage_live_role(member, live_role, False)

    async def _notify_live(self, member: discord.Member, platform_name: str, title: str, channel: discord.TextChannel):
        """Envia uma notificação quando um usuário entra em live"""
        quotes = [
            f"Target acquired: {member.display_name} está ao vivo na {platform_name}!",
            f"Missão: Notificar a stream de {member.mention}",
            "Terminar o tédio: Stream online!"
        ]
        
        embed = discord.Embed(
            title=f"🎮 {member.display_name} está AO VIVO!",
            description=f"**{title}**\n\n{random.choice(quotes)}",
            url=self._get_stream_url(member.name, platform_name),
            color=discord.Color.brand_red() if platform_name == "YouTube" else discord.Color.purple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        
        await channel.send(f"{member.mention} está ao vivo!", embed=embed)
        logger.info(f"Notificação de live enviada para {member.display_name} ({platform_name})")

    async def _manage_live_role(self, member: discord.Member, role: discord.Role, is_live: bool):
        """Gerencia o cargo de live de forma consistente"""
        if is_live and role not in member.roles:
            await member.add_roles(role, reason="Usuário entrou em live")
            logger.info(f"Cargo '{role.name}' atribuído a {member.display_name}")
        elif not is_live and role in member.roles:
            await member.remove_roles(role, reason="Usuário não está mais em live")
            logger.info(f"Cargo '{role.name}' removido de {member.display_name}")

    def _get_stream_url(self, username: str, platform_name: str) -> str:
        """Retorna a URL da stream com base na plataforma"""
        if platform_name == "Twitch":
            return f"https://www.twitch.tv/{username}"
        elif platform_name == "YouTube":
            return f"https://www.youtube.com/channel/{username}/live"
        return ""
    
async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
