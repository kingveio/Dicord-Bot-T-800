import aiohttp
import logging
from typing import Optional, Tuple  # Adicionando import
from config import Config

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self):
        self.api_key = Config.YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    async def get_channel_id(self, username: str) -> Optional[str]:
        """Obtém o ID do canal a partir do nome de usuário"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/channels?part=id&forUsername={username}&key={self.api_key}"
                async with session.get(url) as resp:
                    data = await resp.json()
                    return data.get("items", [{}])[0].get("id")
        except Exception as e:
            logger.error(f"Erro ao buscar ID do canal YouTube: {e}")
            return None
    
    async def is_live(self, channel_identifier: str, is_username: bool = True) -> Tuple[bool, Optional[str]]:
        """Verifica se um canal está transmitindo ao vivo"""
        try:
            channel_id = channel_identifier
            if is_username:
                channel_id = await self.get_channel_id(channel_identifier)
                if not channel_id:
                    return False, None
            
            async with aiohttp.ClientSession() as session:
                url = (
                    f"{self.base_url}/search?part=snippet&channelId={channel_id}"
                    f"&eventType=live&type=video&key={self.api_key}"
                )
                async with session.get(url) as resp:
                    data = await resp.json()
                
                if data.get("items"):
                    live_info = data["items"][0]["snippet"]
                    return True, live_info.get("title", "Live sem título")
                return False, None
        except Exception as e:
            logger.error(f"Erro ao verificar live YouTube: {e}")
            return False, None
