import aiohttp
import logging
import asyncio
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API pública do Kick, usando o fluxo de autenticação."""
    BASE_URL = "https://kick.com/api/v1/channels/"  # <--- URL CORRIGIDA PARA V1
    TOKEN_URL = "https://id.kick.com/oauth/token"

    def __init__(self):
        self.client_id = os.getenv("KICK_CLIENT_ID")
        self.client_secret = os.getenv("KICK_CLIENT_SECRET")
        self.access_token = None
        self.token_expires_at = 0
        self._lock = asyncio.Lock()

    async def _get_access_token(self):
        """Obtém ou renova o token de acesso da API do Kick."""
        if self.access_token and self.token_expires_at > asyncio.get_event_loop().time():
            return True

        if not self.client_id or not self.client_secret:
            logger.error("❌ KICK_CLIENT_ID ou KICK_CLIENT_SECRET não estão configurados.")
            return False

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }

        async with self._lock:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.TOKEN_URL, data=data, headers=headers) as response:
                        response.raise_for_status()
                        token_data = await response.json()
                        
                        self.access_token = token_data.get("access_token")
                        expires_in = token_data.get("expires_in", 3600)
                        # Define a expiração 60 segundos antes para garantir que o token seja renovado a tempo.
                        self.token_expires_at = asyncio.get_event_loop().time() + expires_in - 60
                        
                        logger.info("✅ Token de acesso da Kick API obtido com sucesso.")
                        return True
            except aiohttp.ClientError as e:
                logger.error(f"❌ Erro ao obter token de acesso: {e}")
                self.access_token = None
                return False
            except Exception as e:
                logger.error(f"❌ Erro inesperado ao obter token de acesso: {e}")
                self.access_token = None
                return False

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Verifica se um canal do Kick está ao vivo."""
        username = username.strip().lower()

        # Primeiro, obtém o token de acesso
        if not await self._get_access_token():
            logger.warning("🚫 Não foi possível obter o token, a requisição não será feita.")
            return None

        # Agora, utiliza o token de acesso na requisição
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{self.BASE_URL}{username}") as resp:
                    if resp.status == 404:
                        logger.warning(f"⚠️ Canal '{username}' não existe no Kick.")
                        return None
                    elif resp.status != 200:
                        # Loga a resposta para ajudar na depuração
                        logger.error(f"❌ Erro ao acessar dados do canal '{username}': HTTP {resp.status} - Resposta: {await resp.text()}")
                        return None

                    data = await resp.json()

                    if data.get("livestream"):
                        logger.info(f"✅ Canal '{username}' está AO VIVO no Kick.")
                        return data
                    else:
                        logger.info(f"ℹ️ Canal '{username}' encontrado, mas está offline.")
                        return None

        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
            return None
