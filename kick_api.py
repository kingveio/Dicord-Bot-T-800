import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API do Kick."""
    def __init__(self):
        self.session = aiohttp.ClientSession()

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
