import aiohttp
import logging

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir diretamente com a API pública do Kick."""
    BASE_URL = "https://kick.com/api/v1/channels/"

    async def get_stream_info(self, username: str):
        """Verifica se um canal do Kick está ao vivo."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}{username}") as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ Canal '{username}' não encontrado no Kick.")
                        return None
                    data = await resp.json()
                    if data.get("livestream"):
                        return data
                    return None
        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
            return None
