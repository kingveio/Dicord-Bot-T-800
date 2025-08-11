import httpx
import logging
import asyncio
import os

logger = logging.getLogger(__name__)

class KickAPI:
    BASE_URL = "https://kick.com/api/v2/channels/"
    TOKEN_URL = "https://kick.com/api/v1/oauth/token"
    
    def __init__(self):
        # Obtém as credenciais das variáveis de ambiente.
        self.client_id = os.getenv("KICK_CLIENT_ID")
        self.client_secret = os.getenv("KICK_CLIENT_SECRET")
        
        self.client = httpx.AsyncClient(timeout=10.0)
        self.access_token = None
        self.token_expires_at = 0

    async def _get_access_token(self):
        """Obtém ou renova o token de acesso da API do Kick."""
        if self.access_token and self.token_expires_at > asyncio.get_event_loop().time():
            return self.access_token

        if not self.client_id or not self.client_secret:
            logger.error("❌ KICK_CLIENT_ID ou KICK_CLIENT_SECRET não estão configurados.")
            return None

        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }

        try:
            response = await self.client.post(self.TOKEN_URL, json=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            
            self.access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = asyncio.get_event_loop().time() + expires_in
            
            logger.info("✅ Token de acesso da Kick API obtido com sucesso.")
            return self.access_token
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erro ao obter token de acesso: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao obter token de acesso: {e}")
            return None

    async def get_stream_info(self, username: str):
        """Verifica se um canal do Kick está ao vivo usando o token de acesso."""
        token = await self._get_access_token()
        if not token:
            logger.warning("🚫 Não foi possível obter o token, a requisição não será feita.")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        
        url = f"{self.BASE_URL}{username}"
        
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            is_live = data.get("livestream") is not None
            
            if is_live:
                livestream_data = data["livestream"]
                return {
                    "username": data.get("slug"),
                    "is_live": is_live,
                    "title": livestream_data.get("session_title"),
                    "category": livestream_data.get("category", {}).get("name") or "N/A",
                    "viewers": livestream_data.get("viewer_count")
                }
            else:
                return None
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erro ao acessar dados do canal '{username}': HTTP {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"❌ Erro na requisição para Kick API: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ocorreu um erro inesperado: {e}")
            return None
