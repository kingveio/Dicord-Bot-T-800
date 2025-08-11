import aiohttp
import logging

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir diretamente com a API pública do Kick."""
    BASE_URL = "https://kick.com/api/v2/channels/"

    async def get_stream_info(self, username: str):
        """Verifica se um canal do Kick está ao vivo."""
        username = username.strip().lower()  # Normaliza o nome para minúsculas

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}{username}") as resp:
                    if resp.status == 404:
                        logger.warning(f"⚠️ Canal '{username}' não existe no Kick.")
                        return None
                    elif resp.status != 200:
                        logger.error(f"❌ Erro ao acessar dados do canal '{username}': HTTP {resp.status}")
                        return None

                    data = await resp.json()

                    if not data:
                        logger.warning(f"⚠️ Nenhuma informação retornada para o canal '{username}'.")
                        return None

                    if data.get("livestream"):
                        logger.info(f"✅ Canal '{username}' está AO VIVO no Kick.")
                        return data
                    else:
                        logger.info(f"ℹ️ Canal '{username}' encontrado, mas está offline.")
                        return None

        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
            return None
