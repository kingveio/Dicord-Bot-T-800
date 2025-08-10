import aiohttp
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("T-800-TW")

class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires = 0

    async def _get_auth_token(self):
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
                    self.token = data['access_token']
                    self.token_expires = data.get('expires_in', 3600)
                    logger.info("Token de autenticação Twitch obtido")
                else:
                    logger.error(f"Falha ao obter token: {resp.status}")
                    raise Exception("Falha na autenticação Twitch")
        except Exception as e:
            logger.error(f"ERRO DE AUTENTICAÇÃO: {str(e)}")
            raise

    async def check_live_channels(self, channels: List[str]) -> Dict[str, bool]:
        try:
            if not self.token:
                await self._get_auth_token()

            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.token}"
            }
            
            async with self.session.get(
                f"https://api.twitch.tv/helix/streams?user_login={','.join(channels)}",
                headers=headers,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {stream['user_login'].lower(): True for stream in data.get('data', [])}
                elif resp.status == 401:
                    await self._get_auth_token()
                    return await self.check_live_channels(channels)
                else:
                    logger.error(f"Erro na API Twitch: {resp.status}")
                    return {}
        except Exception as e:
            logger.error(f"FALHA NO MONITORAMENTO: {str(e)}")
            return {}
