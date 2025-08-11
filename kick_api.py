import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API do Kick."""
    def __init__(self):
        # Adiciona um conjunto completo de cabeçalhos para simular uma requisição de navegador real.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
            'Referer': 'https://kick.com/',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Verifica se um canal do Kick está ao vivo e retorna as informações da live."""
        api_url = f"https://kick.com/api/v2/channels/{username}"
        try:
            async with self.session.get(api_url) as response:
                response.raise_for_status()
                data = await response.json()
                if data.get('is_live'):
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao processar dados do Kick para '{username}': {e}")
        
        return None
