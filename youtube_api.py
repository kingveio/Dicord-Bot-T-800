import aiohttp
import logging
from typing import List, Dict

logger = logging.getLogger("T-800")

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def _get_channel_ids_by_name(self, channel_names: List[str]) -> Dict[str, str]:
        """Resolve nomes de canais para IDs de canais."""
        channel_ids = {}
        for name in channel_names:
            url = f"{self.base_url}/channels"
            params = {
                "key": self.api_key,
                "part": "snippet",
                "forUsername": name
            }
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("items", [])
                        if items:
                            channel_ids[name.lower()] = items[0]["id"]
            except aiohttp.ClientError as e:
                logger.error(f"❌ Erro ao buscar ID do canal {name} do YouTube: {e}")
        return channel_ids

    async def get_channel_live_status(self, channel_names: List[str]) -> Dict[str, bool]:
        """Verifica o status de live de uma lista de canais do YouTube."""
        live_status = {name.lower(): False for name in channel_names}
        
        channel_ids = await self._get_channel_ids_by_name(channel_names)
        if not channel_ids:
            return live_status
            
        url = f"{self.base_url}/search"
        params = {
            "key": self.api_key,
            "part": "snippet",
            "eventType": "live",
            "type": "video",
            "channelId": ",".join(channel_ids.values())
        }

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    live_videos = data.get("items", [])
                    
                    id_to_name = {v: k for k, v in channel_ids.items()}
                    
                    for item in live_videos:
                        channel_id = item["snippet"]["channelId"]
                        channel_name = id_to_name.get(channel_id)
                        if channel_name:
                            live_status[channel_name] = True
                else:
                    logger.error(f"❌ Erro na API do YouTube: {response.status} - {await response.text()}")
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube: {e}")
            
        return live_status
