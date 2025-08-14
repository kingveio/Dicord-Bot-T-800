import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone
import random
import asyncio
from typing import Optional # <<< Adicione esta linha
from data.models import UserPlatform
from config import Config

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
        
        for guild in self.bot.guilds:
            try:
                guild_data = self.bot.data_manager.get_guild(guild.id)
                
                # Acessa os atributos do objeto config, não do dicionário
                live_role_id = guild_data['config'].get('live_role_id')
                notify_channel_id = guild_data.config.notify_channel_id
                
                if not live_role_id or not notify_channel_id:
                    continue # Pula se as configurações estiverem incompletas
                
                live_role = guild.get_role(live_role_id)
                notify_channel = guild.get_channel(notify_channel_id)
                
                if not live_role or not notify_channel:
                    continue # Pula se o cargo ou canal não forem encontrados

                for user_id, user_data in guild_data.users.items():
                    member = guild.get_member(user_id)
                    if not member:
                        continue
                    
                    if user_data.twitch:
                        is_live, title = await self.bot.twitch_api.is_live(user_data.twitch.username)
                        await self._update_platform_status(
                            member=member,
                            platform_data=user_data.twitch,
                            is_live=is_live,
                            title=title,
                            notify_channel=notify_channel,
                            platform_name="Twitch",
                            live_role=live_role
                        )
                        
                    if user_data.youtube:
                        is_live, title = await self.bot.youtube_api.is_live(user_data.youtube.username)
                        await self._update_platform_status(
                            member=member,
                            platform_data=user_data.youtube,
                            is_live=is_live,
                            title=title,
                            notify_channel=notify_channel,
                            platform_name="YouTube",
                            live_role=live_role
                        )
                        
                # Salva o estado atualizado dos dados após o loop
                self.bot.data_manager._data["guilds"][str(guild.id)] = guild_data.to_dict()
                await self.bot.data_manager.save()

            except Exception as e:
                logger.error(f"Erro no check_live para a guilda {guild.id}: {e}", exc_info=True)

    async def _update_platform_status(
        self,
        member: discord.Member,
        platform_data: UserPlatform,
        is_live: bool,
        title: Optional[str],
        notify_channel: discord.TextChannel,
        platform_name: str,
        live_role: discord.Role
    ):
        """Lógica central para verificar e notificar status de live"""
        
        # Atualiza o timestamp da última verificação
        platform_data.last_checked = datetime.now(timezone.utc)

        # Lógica de notificação e atualização de cargo
        if is_live and not platform_data.is_live:
            # Usuário entrou em live
            platform_data.is_live = True
            platform_data.last_live_title = title
            
            await self._notify_live(member, platform_name, title, notify_channel)
            await self._manage_live_role(member, live_role, True)
            
        elif not is_live and platform_data.is_live:
            # Usuário saiu da live
            platform_data.is_live = False
            
            # Verifica se o membro ainda está em live em outra plataforma antes de remover o cargo
            other_platform_live = (platform_name == "Twitch" and member.youtube and member.youtube.is_live) or \
                                  (platform_name == "YouTube" and member.twitch and member.twitch.is_live)
            
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
            return f"https://www.youtube.com/@{username}/live"
        return ""
    
async def setup(bot):
    await bot.add_cog(LiveMonitor(bot))
