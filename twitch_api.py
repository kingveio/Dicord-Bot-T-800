import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
from aiohttp import ClientSession

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self, session: ClientSession, client_id: str, client_secret: str):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0

    async def _get_access_token(self) -> Optional[str]:
        if self.access_token and self.token_expiry > asyncio.get_event_loop().time():
            return self.access_token

        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.access_token = result.get("access_token")
                    self.token_expiry = asyncio.get_event_loop().time() + result.get("expires_in", 3600) - 10
                    return self.access_token
                else:
                    logger.error(f"Erro ao obter token da Twitch: {resp.status} - {await resp.text()}")
                    return None
        except Exception as e:
            logger.error(f"Erro na requisição do token da Twitch: {e}")
            return None

    async def get_live_streams(self, user_logins: List[str]) -> List[Dict[str, Any]]:
        if not user_logins:
            return []

        token = await self._get_access_token()
        if not token:
            logger.error("Não foi possível obter o token de acesso da Twitch.")
            return []

        params = [f"user_login={login}" for login in user_logins]
        url = f"https://api.twitch.tv/helix/streams?{'&'.join(params)}"
        
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}"
        }

        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                else:
                    logger.error(f"Erro na requisição de streams da Twitch: {resp.status} - {await resp.text()}")
                    return []
        except Exception as e:
            logger.error(f"Erro na requisição de streams da Twitch: {e}")
            return []
