# T-800: Módulo de reconhecimento. Escaneando a rede da Twitch.
import aiohttp
from config import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET

class TwitchAPI:
    def __init__(self):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.token = None

    async def _get_token(self):
        # Obtendo token de acesso, essencial para a missão.
        async with aiohttp.ClientSession() as session:
            url = f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials"
            async with session.post(url) as response:
                data = await response.json()
                self.token = data.get("access_token")

    async def is_live(self, username: str) -> bool:
        if not self.token:
            await self._get_token()

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.token}"
        }
        url = f"https://api.twitch.tv/helix/streams?user_login={username}"

        # Enviando a solicitação para a Twitch para verificar o status.
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                streams = data.get("data")
                return len(streams) > 0 # Retorna True se a lista não estiver vazia.
