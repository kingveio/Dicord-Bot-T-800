# T-800: Módulo de reconhecimento. Escaneando a rede do YouTube.
import aiohttp
from config import YOUTUBE_API_KEY

class YouTubeAPI:
    def __init__(self):
        self.api_key = YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def get_channel_id(self, username: str) -> str | None:
        # Primeiro, precisamos do ID do canal para monitorar.
        url = f"{self.base_url}/channels?part=snippet&forUsername={username}&key={self.api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                items = data.get("items")
                if items:
                    return items[0].get("id")
        return None

    async def is_live(self, channel_id: str) -> bool:
        # Agora, verificamos se o canal está "ao vivo" (live).
        url = f"{self.base_url}/search?part=snippet&channelId={channel_id}&type=video&eventType=live&key={self.api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                items = data.get("items")
                return len(items) > 0 # Se houver um item, significa que a live está ativa.
