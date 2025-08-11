import os
import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("T-800")

class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.headers = None

    async def _get_access_token(self):
        """Obtém um novo token de acesso da API da Twitch."""
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            async with self.session.post(url, data=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("access_token")
                    self.headers = {
                        "Client-ID": self.client_id,
                        "Authorization": f"Bearer {self.access_token}"
                    }
                    logger.info("✅ Token da Twitch obtido/renovado com sucesso.")
                    return True
                else:
                    logger.error(f"❌ Erro ao obter token da Twitch: {response.status} - {await response.text()}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão ao tentar obter token da Twitch: {e}")
            return False

    async def check_live_channels(self, streamer_names: List[str]) -> Dict[str, bool]:
        """Verifica o status de live de uma lista de streamers."""
        if not self.access_token:
            await self._get_access_token()
            if not self.access_token:
                logger.error("❌ Falha crítica: Não foi possível obter o token de acesso da Twitch.")
                return {}

        url = "https://api.twitch.tv/helix/streams"
        params = {"user_login": streamer_names}
        live_status = {name.lower(): False for name in streamer_names}

        try:
            async with self.session.get(url, params=params, headers=self.headers) as response:
                if response.status == 401:
                    logger.warning("⚠️ Token da Twitch expirado. Tentando renovar...")
                    if await self._get_access_token():
                        async with self.session.get(url, params=params, headers=self.headers) as new_response:
                            if new_response.status == 200:
                                data = await new_response.json()
                                live_streams = data.get("data", [])
                                for stream in live_streams:
                                    live_status[stream['user_login'].lower()] = True
                            else:
                                logger.error(f"❌ Erro na API Twitch após renovar token: {new_response.status}")
                    else:
                        logger.error("❌ Falha ao renovar o token da Twitch. Verifique suas credenciais.")
                elif response.status == 200:
                    data = await response.json()
                    live_streams = data.get("data", [])
                    for stream in live_streams:
                        live_status[stream['user_login'].lower()] = True
                else:
                    logger.error(f"❌ Erro na API Twitch: {response.status} - {await response.text()}")
        
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão com a API da Twitch: {e}")
        
        return live_status
