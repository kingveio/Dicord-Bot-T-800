import os
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extrai o ID do canal a partir de uma URL ou handle."""
        
        async def _search_channel_by_query(query: str, search_type: str = "forUsername") -> Optional[str]:
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'channel',
                'key': self.api_key
            }
            if search_type == "forHandle":
                 params['forHandle'] = query
            else:
                 params['forUsername'] = query

            url = f'https://googleusercontent.com/youtube/v3/search'
            
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if data.get('items'):
                        return data['items'][0]['snippet']['channelId']
            except Exception as e:
                logger.error(f"❌ Erro ao buscar ID do canal '{query}' na API do YouTube: {e}")
            return None

        # Tenta extrair o ID diretamente da URL
        match = re.search(r'(?:channel|user|c)\/([^/]+)', url)
        if match:
            return match.group(1)
        
        # Tenta o formato de handle (@nome)
        match_handle = re.search(r'@([\w-]+)', url)
        if match_handle:
            return await _search_channel_by_query(match_handle.group(1), "forHandle")
        
        # Retorna o próprio input se já for um ID válido
        if len(url) == 24 and url.startswith("UC"):
            return url
        
        return None

    async def is_channel_live(self, channel_id: str) -> bool:
        """Verifica se um canal está ao vivo."""
        url = f'https://googleusercontent.com/youtube/v3/search'
        params = {
            'key': self.api_key,
            'channelId': channel_id,
            'part': 'snippet',
            'eventType': 'live',
            'type': 'video'
        }
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return len(data.get('items', [])) > 0
        except Exception as e:
            logger.error(f"❌ Erro ao verificar live do canal {channel_id}: {e}")
            return False
