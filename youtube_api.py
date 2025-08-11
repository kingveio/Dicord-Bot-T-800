import aiohttp
import logging
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("T-800-YT")

class YouTubeAPI:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3/"

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extrai o ID do canal a partir de uma URL do YouTube."""
        try:
            parsed = urlparse(url)
            
            if "youtube.com" not in parsed.netloc and "youtu.be" not in parsed.netloc:
                logger.warning("URL não é do YouTube.")
                return None

            # Caso 1: URL com /channel/
            if "/channel/" in url:
                channel_id = url.split("/channel/")[1].split("/")[0]
                return channel_id
            
            # Caso 2: URL com /@ (handle)
            elif "/@" in url:
                handle = url.split("/@")[1].split("/")[0]
                logger.info(f"Identificado handle: @{handle}")
                return await self._search_channel_by_handle(handle)
            
            # Caso 3: URL com parâmetro channel_id
            elif "channel_id" in parse_qs(parsed.query):
                channel_id = parse_qs(parsed.query)["channel_id"][0]
                return channel_id
            
            return None
        except Exception as e:
            logger.error(f"❌ Falha na identificação do ID do canal: {str(e)}")
            return None

    async def _search_channel_by_handle(self, handle: str) -> Optional[str]:
        """Busca o ID do canal a partir de um handle (@)."""
        # A API agora requer o parâmetro 'forHandle' para buscas por handle.
        endpoint = f"{self.base_url}channels?part=id&forHandle={handle}&key={self.api_key}"
        try:
            async with self.session.get(endpoint, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # A resposta para a busca por handle é um pouco diferente,
                    # o ID do canal está em 'items[0].id'.
                    if data.get('items'):
                        return data['items'][0]['id']
                    else:
                        logger.warning(f"Handle '@{handle}' não encontrado.")
                        return None
                else:
                    logger.error(f"❌ Erro ao buscar handle '{handle}' na API do YouTube: {resp.status}, message='{await resp.text()}'")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube ao buscar handle '{handle}': {e}")
            return None
    
    async def is_channel_live(self, channel_id: str) -> bool:
        """Verifica se um canal está ao vivo."""
        endpoint = f"{self.base_url}search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={self.api_key}"
        try:
            async with self.session.get(endpoint, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return len(data.get('items', [])) > 0
                else:
                    logger.error(f"❌ Erro ao verificar live do canal '{channel_id}': {resp.status}, message='{await resp.text()}'")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube ao verificar live '{channel_id}': {e}")
            return False

    async def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        """Obtém informações básicas sobre um canal."""
        endpoint = f"{self.base_url}channels?part=snippet&id={channel_id}&key={self.api_key}"
        try:
            async with self.session.get(endpoint, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('items'):
                        return data['items'][0].get('snippet')
                    return None
                else:
                    logger.error(f"❌ Erro ao obter informações do canal '{channel_id}': {resp.status}, message='{await resp.text()}'")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API do YouTube ao buscar informações do canal '{channel_id}': {e}")
            return None
