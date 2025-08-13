import aiohttp
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self):
        self.client_id = Config.TWITCH_CLIENT_ID
        self.client_secret = Config.TWITCH_CLIENT_SECRET
        self.access_token = None
        self.token_expires = 0
    
    async def _get_access_token(self) -> bool:
        """Obtém token de acesso OAuth2 da Twitch"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://id.twitch.tv/oauth2/token"
                params = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
                }
                
                async with session.post(url, params=params) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        self.access_token = data["access_token"]
                        self.token_expires = data.get("expires_in", 0)
                        return True
                    logger.error(f"Erro ao obter token: {data.get('message')}")
                    return False
        except Exception as e:
            logger.error(f"Falha na autenticação Twitch: {e}")
            return False
    
    async def is_live(self, username: str) -> Tuple[bool, Optional[str]]:
        """Verifica se um streamer está online"""
        try:
            if not self.access_token:
                if not await self._get_access_token():
                    return False, None
            
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with aiohttp.ClientSession() as session:
                # Primeiro obtém o ID do usuário
                user_url = f"https://api.twitch.tv/helix/users?login={username}"
                async with session.get(user_url, headers=headers) as resp:
                    if resp.status == 401:  # Token expirado
                        if not await self._get_access_token():
                            return False, None
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        async with session.get(user_url, headers=headers) as retry_resp:
                            user_data = await retry_resp.json()
                    else:
                        user_data = await resp.json()
                
                user_id = user_data.get("data", [{}])[0].get("id")
                if not user_id:
                    return False, None
                
                # Verifica o status do stream
                stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
                async with session.get(stream_url, headers=headers) as stream_resp:
                    stream_data = await stream_resp.json()
                
                if stream_data.get("data"):
                    stream_info = stream_data["data"][0]
                    return True, stream_info.get("title", "Live sem título")
                return False, None
        except Exception as e:
            logger.error(f"Erro ao verificar live Twitch: {e}")
            return False, None
