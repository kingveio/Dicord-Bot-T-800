import discord
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DiscordService:
    def __init__(self, bot: discord.Client):
        self.bot = bot
    
    async def get_guild(self, guild_id: int) -> Optional[discord.Guild]:
        """Obtém uma guilda pelo ID com tratamento de erros"""
        try:
            return self.bot.get_guild(guild_id)
        except Exception as e:
            logger.error(f"Erro ao buscar guilda {guild_id}: {e}")
            return None
    
    async def assign_role(self, member: discord.Member, role_id: int) -> bool:
        """Atribui um cargo a um membro com verificação"""
        try:
            role = member.guild.get_role(role_id)
            if not role:
                logger.warning(f"Cargo {role_id} não encontrado")
                return False
            
            if role not in member.roles:
                await member.add_roles(role)
                logger.info(f"Cargo {role.name} atribuído a {member.display_name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao atribuir cargo: {e}")
            return False
    
    async def remove_role(self, member: discord.Member, role_id: int) -> bool:
        """Remove um cargo de um membro com verificação"""
        try:
            role = member.guild.get_role(role_id)
            if not role:
                return False
            
            if role in member.roles:
                await member.remove_roles(role)
                logger.info(f"Cargo {role.name} removido de {member.display_name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao remover cargo: {e}")
            return False
    
    async def send_notification(self, channel_id: int, message: str) -> bool:
        """Envia notificação para um canal específico"""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(message)
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            return False
