import httpx
import logging
import asyncio
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com a API pública do Kick, usando o fluxo de autenticação."""
    USER_URL = "https://kick.com/api/v1/users/"
    LIVE_STREAMS_URL = "https://api.kick.com/public/v1/livestreams"
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
            # Etapa 1: Obter o ID do usuário a partir do nome de usuário
            user_response = await self.client.get(f"{self.USER_URL}{username}")
            if user_response.status_code != 200:
                if user_response.status_code == 404:
                    logger.warning(f"⚠️ Canal '{username}' não existe no Kick.")
                else:
                    logger.error(f"❌ Erro ao obter ID do canal '{username}': HTTP {user_response.status_code} - Resposta: {user_response.text}")
                return None
            
            user_data = user_response.json()
            user_id = user_data.get("id")

            if not user_id:
                logger.warning(f"⚠️ ID de usuário não encontrado para o canal '{username}'.")
                return None
                
            # Etapa 2: Usar o ID para verificar se o canal está ao vivo
            live_streams_response = await self.client.get(f"{self.LIVE_STREAMS_URL}?broadcaster_user_id={user_id}", headers=headers)
            
            if live_streams_response.status_code != 200:
                logger.error(f"❌ Erro ao acessar dados do canal '{username}': HTTP {live_streams_response.status_code} - Resposta: {live_streams_response.text}")
                return None

            live_streams_data = live_streams_response.json()

            if live_streams_data.get("data"):
                livestream_data = live_streams_data["data"][0]
                logger.info(f"✅ Canal '{username}' está AO VIVO no Kick.")
                return livestream_data
            else:
                logger.info(f"ℹ️ Canal '{username}' encontrado, mas está offline.")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao verificar stream do Kick para '{username}': {e}")
            return None
