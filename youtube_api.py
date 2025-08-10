import os
import re
import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extrai o ID do canal a partir de uma URL ou handle."""
        
        # Tenta extrair o ID diretamente da URL
        match = re.search(r'(?:channel|user|c)\/([^/]+)', url)
        if match:
            return match.group(1)
        
        # Tenta o formato de handle (@nome)
        match_handle = re.search(r'@([\w-]+)', url)
        if match_handle:
            return await self._search_channel_by_query(match_handle.group(1), "forHandle")
        
        # Retorna o próprio input se já for um ID válido
        if len(url) == 24 and url.startswith("UC"):
            return url
        
        # Tenta buscar o username
        match_username = re.search(r'youtube\.com\/([\w-]+)', url)
        if match_username and not url.startswith('https://www.youtube.com/channel/'):
            return await self._search_channel_by_query(match_username.group(1), "forUsername")

        return None
    
    async def _search_channel_by_query(self, query: str, search_type: str) -> Optional[str]:
        api_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'channel',
            'maxResults': 1,
            'key': self.api_key
        }

        if search_type == "forHandle":
            params['forHandle'] = query
            del params['q'] # A API do YouTube requer 'forHandle' ou 'q', mas não ambos
        elif search_type == "forUsername":
            params['forUsername'] = query
            del params['q']

        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(api_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                if data.get('items'):
                    return data['items'][0]['snippet']['channelId']
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro ao buscar ID do canal '{query}' na API do YouTube: {e}")
        except asyncio.TimeoutError:
            logger.error(f"❌ Requisição de busca de canal '{query}' expirou.")
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar ID do canal '{query}': {e}")
        
        return None
