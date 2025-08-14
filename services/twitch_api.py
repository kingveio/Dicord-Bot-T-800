import aiohttp
import logging
from typing import Optional, Tuple
from config import Config
import time
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.client_id = Config.TWITCH_CLIENT_ID
        self.client_secret = Config.TWITCH_CLIENT_SECRET
        self.access_token = None
        self.token_expires = 0
        self.user_cache = {}
        # O timeout da sessão principal é configurado no main.py, então não precisamos dele aqui
    
    async def _get_access_token(self) -> bool:
        """Obtém token de acesso OAuth2 da Twitch"""
        try:
            url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
            
            async with self.session.post(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.access_token = data["access_token"]
                    self.token_expires = time.time() + data.get("expires_in", 3600)
                    logger.info("✅ Token de acesso da Twitch obtido com sucesso.")
                    return True
                logger.error(f"❌ Erro ao obter token: {resp.status} - {await resp.text()}")
                return False
        except Exception as e:
            logger.error(f"❌ Falha na autenticação Twitch: {e}")
            return False
    
    async def _get_user_id(self, username: str) -> Optional[str]:
        """Obtém o ID do usuário com cache"""
        if username in self.user_cache:
            return self.user_cache[username]
            
        try:
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.access_token}"
            }
            
            user_url = f"https://api.twitch.tv/helix/users?login={username}"
            async with self.session.get(user_url, headers=headers) as resp:
                if resp.status == 401:  # Token expirado
                    logger.warning("Token da Twitch expirado. Tentando renovar...")
                    if not await self._get_access_token():
                        return None
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    
                    async with self.session.get(user_url, headers=headers) as retry_resp:
                        if retry_resp.status != 200:
                            logger.error(f"❌ Falha ao buscar ID do usuário após renovar token: {retry_resp.status}")
                            return None
                        user_data = await retry_resp.json()
                elif resp.status != 200:
                    logger.error(f"❌ Erro ao buscar ID do usuário: {resp.status}")
                    return None
                else:
                    user_data = await resp.json()
            
            if not user_data.get("data"):
                logger.info(f"❌ Usuário '{username}' não encontrado na Twitch.")
                return None
            
            user_id = user_data["data"][0].get("id")
            if user_id:
                self.user_cache[username] = user_id
            return user_id
        except Exception as e:
            logger.error(f"❌ Erro ao buscar ID do usuário: {e}")
            return None
    
    async def is_live(self, username: str) -> Tuple[bool, Optional[str]]:
        """Verifica se um streamer está online"""
        try:
            # Verifica e renova o token se necessário
            if not self.access_token or time.time() > self.token_expires - 60:
                if not await self._get_access_token():
                    return False, None
            
            user_id = await self._get_user_id(username)
            if not user_id:
                return False, None
            
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.access_token}"
            }
            
            stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            async with self.session.get(stream_url, headers=headers) as stream_resp:
                if stream_resp.status != 200:
                    logger.error(f"❌ Erro ao verificar live: {stream_resp.status}")
                    return False, None
                stream_data = await stream_resp.json()
            
            if stream_data.get("data"):
                stream_info = stream_data["data"][0]
                return True, stream_info.get("title", "Live sem título")
            
            return False, None
        except Exception as e:
            logger.error(f"❌ Erro ao verificar live Twitch: {e}")
            return False, None
