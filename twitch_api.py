import os
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_token = None
        self.oauth_expires_at = 0
        self.headers = {}
        self._lock = asyncio.Lock()

    async def _get_oauth_token(self):
        """Obtém ou atualiza o token OAuth da Twitch."""
        if self.oauth_token and self.oauth_expires_at > asyncio.get_event_loop().time():
            return
        
        async with aiohttp.ClientSession() as session:
            try:
                response = await session.post(
                    'https://id.twitch.tv/oauth2/token',
                    data={
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'grant_type': 'client_credentials'
                    }
                )
                response.raise_for_status()
                data = await response.json()
                self.oauth_token = data['access_token']
                self.oauth_expires_at = asyncio.get_event_loop().time() + data['expires_in'] - 60
                self.headers = {
                    'Client-ID': self.client_id,
                    'Authorization': f'Bearer {self.oauth_token}'
                }
                logger.info("✅ Novo token OAuth da Twitch obtido com sucesso.")
            except aiohttp.ClientError as e:
                logger.error(f"❌ Erro ao obter token da Twitch: {e}")
                self.oauth_token = None

    async def get_live_streams(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Verifica quais streamers estão ao vivo na Twitch."""
        if not self.client_id or not self.client_secret:
            logger.error("❌ Credenciais da Twitch não estão configuradas.")
            return []
            
        async with self._lock:
            await self._get_oauth_token()
            if not self.oauth_token:
                return []
                
            async with aiohttp.ClientSession(headers=self.headers) as session:
                try:
                    params = [('user_login', username) for username in usernames]
                    response = await session.get(
                        'https://api.twitch.tv/helix/streams',
                        params=params
                    )
                    response.raise_for_status()
                    data = await response.json()
                    logger.info("✅ Verificação de lives da Twitch concluída.")
                    return data.get('data', [])
                except aiohttp.ClientError as e:
                    logger.error(f"❌ Erro ao verificar streams da Twitch: {e}")
                    return []
