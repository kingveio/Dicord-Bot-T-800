import os
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List, Set
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3/"

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        if len(path_parts) >= 2 and path_parts[0] == 'channel':
            return path_parts[1]
        elif len(path_parts) >= 2 and path_parts[0] == 'c':
            channel_name = path_parts[1]
            return await self._search_channel_by_name(channel_name)
        elif len(path_parts) >= 1 and path_parts[0].startswith('@'):
            channel_handle = path_parts[0][1:]
            return await self._search_channel_by_name(channel_handle)
        elif parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            if 'channel' in query_params:
                return query_params['channel'][0]
        
        return None

    async def _search_channel_by_name(self, name: str) -> Optional[str]:
        endpoint = f"{self.base_url}search?part=snippet&q={name}&type=channel&maxResults=1&key={self.api_key}"
        try:
            async with self.session.get(endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                if data.get('items'):
                    return data['items'][0]['id']['channelId']
        except aiohttp.ClientError as e:
            logger.error(f"Erro na API do YouTube ao buscar canal por nome: {e}")
        return None

    async def get_latest_video(self, channel_id: str) -> Optional[Dict[str, str]]:
        endpoint = f"{self.base_url}search?part=snippet&channelId={channel_id}&maxResults=1&order=date&type=video&key={self.api_key}"
        try:
            async with self.session.get(endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                if data and data.get('items'):
                    video = data['items'][0]
                    return {
                        "id": video['id']['videoId'],
                        "title": video['snippet']['title'],
                        "url": f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                    }
        except aiohttp.ClientError as e:
            logger.error(f"Erro na API do YouTube ao buscar último vídeo: {e}")
        return None

    async def is_channel_live(self, channel_id: str) -> bool:
        endpoint = f"{self.base_url}search?part=snippet&channelId={channel_id}&maxResults=1&type=video&eventType=live&key={self.api_key}"
        try:
            async with self.session.get(endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                return bool(data and data.get('items'))
        except aiohttp.ClientError as e:
            logger.error(f"Erro na API do YouTube ao verificar live: {e}")
            return False
