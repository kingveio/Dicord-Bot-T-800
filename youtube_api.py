import logging
import aiohttp
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def get_latest_video(self, channel_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/search"
        params = {
            "key": self.api_key,
            "channelId": channel_id,
            "part": "snippet",
            "order": "date",
            "type": "video",
            "maxResults": 1
        }
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and "items" in data and data["items"]:
                        item = data["items"][0]
                        published_at_str = item["snippet"]["publishedAt"]
                        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                        
                        return {
                            "id": item["id"]["videoId"],
                            "title": item["snippet"]["title"],
                            "published_at": published_at,
                            "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                        }
                    else:
                        logger.info(f"Nenhum vídeo encontrado para o canal {channel_id}.")
                        return None
                else:
                    logger.error(f"Erro na API do YouTube para o canal {channel_id}: {resp.status} - {await resp.text()}")
                    return None
        except Exception as e:
            logger.error(f"Erro na requisição da API do YouTube: {e}")
            return None

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        # Extrai ID de URLs de canal padrão
        match = re.search(r'(?:youtube\.com/channel/|youtube\.com/c/|youtube\.com/user/|youtube\.com/@)([^/]+)', url)
        if match:
            part = match.group(1)
            # Se a URL já contiver um ID de canal (começando com 'UC'), retorna
            if part.startswith('UC'):
                return part
            
            # Se for um nome de usuário, busca o ID real
            search_url = f"{self.base_url}/channels"
            params = {
                "key": self.api_key,
                "part": "snippet",
                "forUsername": part
            }
            try:
                async with self.session.get(search_url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and "items" in data and data["items"]:
                            return data["items"][0]["id"]
            except Exception as e:
                logger.error(f"Erro ao buscar channel ID para o username {part}: {e}")
                
        # Se for um ID direto
        if len(url) == 24 and url.startswith('UC'):
            return url
        
        return None
