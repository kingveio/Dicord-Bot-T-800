import aiohttp
import logging
from typing import Optional, Dict
from urllib.parse import urlparse

logger = logging.getLogger("T-800-YT")

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3/"

    async def get_channel_id(self, url: str) -> Optional[str]:
        try:
            # Implementação otimizada
            parsed = urlparse(url)
            if "youtube.com" not in parsed.netloc:
                return None

            if "/channel/" in url:
                return url.split("/channel/")[1].split("/")[0]
            elif "/@" in url:
                handle = url.split("/@")[1].split("/")[0]
                return await self._search_channel(handle)
            
            return None
        except Exception as e:
            logger.error(f"FALHA NA IDENTIFICAÇÃO: {str(e)}")
            return None

    async def _search_channel(self, query: str) -> Optional[str]:
        endpoint = f"{self.base_url}search?part=snippet&q={query}&type=channel&maxResults=1&key={self.api_key}"
        try:
            async with self.session.get(endpoint, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('items', [{}])[0].get('id', {}).get('channelId')
        except Exception as e:
            logger.error(f"FALHA NA BUSCA: {str(e)}")
            return None
