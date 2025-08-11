import logging
from typing import Optional, Dict, Any
from KickApi import Kick

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API do Kick usando a biblioteca KickApi."""
    def __init__(self):
        self.kick_api = Kick()

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Verifica se um canal do Kick está ao vivo."""
        try:
            channel_data = await self.kick_api.get_channel(username)
            if channel_data and channel_data.get('livestream'):
                return channel_data
        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}' usando a biblioteca KickApi: {e}")
        
        return None
