import httpx
import logging
import asyncio
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API pública do Kick, usando o fluxo de autenticação."""
    BASE_URL = "https://kick.com/api/v1/channels/"
    TOKEN_URL = "https://id.kick.com/oauth/token"

    def __init__(self):
        self.client_id = os.getenv("KICK_CLIENT_ID")
        self.client_secret = os.getenv("KICK_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=10.0)
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
                response = await self.client.post(self.TOKEN_URL, data=data, headers=headers)
                response.raise_for_status()
                token_data = response.json()
                
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = asyncio.get_event_loop().time() + expires_in - 60
                
                logger.info("✅ Token de acesso da Kick API obtido com sucesso.")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Erro ao obter token de acesso: HTTP {e.response.status_code} - Resposta: {e.response.text}")
                self.access_token = None
                return False
            except Exception as e:
                logger.error(f"❌ Erro inesperado ao obter token de acesso: {e}")
                self.access_token = None
                return False

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Verifica se um canal do Kick está ao vivo."""
        username = username.strip().lower()

        if not await self._get_access_token():
            logger.warning("🚫 Não foi possível obter o token, a requisição não será feita.")
            return None

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            response = await self.client.get(f"{self.BASE_URL}{username}", headers=headers)
            
            if response.status_code == 404:
                logger.warning(f"⚠️ Canal '{username}' não existe no Kick.")
                return None
            elif response.status_code != 200:
                logger.error(f"❌ Erro ao acessar dados do canal '{username}': HTTP {response.status_code} - Resposta: {response.text}")
                return None

            data = response.json()

            if data.get("livestream"):
                logger.info(f"✅ Canal '{username}' está AO VIVO no Kick.")
                return data
            else:
                logger.info(f"ℹ️ Canal '{username}' encontrado, mas está offline.")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
            return None
