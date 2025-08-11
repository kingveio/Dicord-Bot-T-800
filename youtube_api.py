import os
import aiohttp
import logging
from typing import List, Dict

logger = logging.getLogger("T-800")

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def get_channel_by_name(self, channel_name: str) -> str:
        """Busca o ID de um canal pelo nome de usuário."""
        url = f"{self.base_url}/search"
        params = {
            "part": "snippet",
            "q": channel_name,
            "type": "channel",
            "key": self.api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                if "items" in data and data["items"]:
                    return data["items"][0]["id"]["channelId"]
                return None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar canal do YouTube: {e}")
            return None

    async def check_live_status(self, channel_id: str) -> bool:
        """Verifica se um canal está transmitindo ao vivo."""
        url = f"{self.base_url}/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "eventType": "live",
            "type": "video",
            "key": self.api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                if "items" in data and data["items"]:
                    for item in data["items"]:
                        if item["snippet"]["liveBroadcastContent"] == "live":
                            return True
                return False
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar live do YouTube: {e}")
            return False

    async def check_live_channels(self, channel_names: List[str]) -> Dict[str, bool]:
        """Verifica o status de live de uma lista de canais do YouTube."""
        live_status = {name: False for name in channel_names}
        
        for name in channel_names:
            channel_id = await self.get_channel_by_name(name)
            if channel_id:
                is_live = await self.check_live_status(channel_id)
                live_status[name] = is_live
            else:
                logger.warning(f"⚠️ Não foi possível encontrar o ID do canal '{name}'.")

        return live_status
