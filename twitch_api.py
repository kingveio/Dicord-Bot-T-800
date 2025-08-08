import os
import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = None
        self.lock = asyncio.Lock()

    async def get_token(self, retries=3):
        async with self.lock:
            if self.token and self.token_expiry and datetime.now() < self.token_expiry:
                return self.token
            for attempt in range(retries):
                try:
                    url = "https://id.twitch.tv/oauth2/token"
                    params = {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials"
                    }
                    async with self.session.post(url, params=params, timeout=15) as resp:
                        data = await resp.json()
                        if resp.status != 200 or "access_token" not in data:
                            logger.error(f"Falha ao obter token da Twitch: {resp.status} - {data}")
                            await asyncio.sleep(2)
                            continue
                        self.token = data["access_token"]
                        self.token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 300)
                        logger.info("✅ Token da Twitch obtido")
                        return self.token
                except Exception as e:
                    logger.error(f"Erro ao obter token (tentativa {attempt+1}): {e}")
                    await asyncio.sleep(2)
            logger.error("❌ Não foi possível obter token da Twitch após tentativas")
            return None

    async def validate_streamer(self, username: str) -> bool:
        token = await self.get_token()
        if not token: return False
        headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {token}"}
        try:
            url = f"https://api.twitch.tv/helix/users?login={username}"
            async with self.session.get(url, headers=headers, timeout=15) as resp:
                data = await resp.json()
                return len(data.get("data", [])) > 0
        except Exception as e:
            logger.error(f"Erro ao validar streamer '{username}': {e}")
            return False

    async def check_live_streams(self, usernames):
        token = await self.get_token()
        if not token: return set()
        headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {token}"}
        live = set()
        batch_size = 100
        usernames_list = list(usernames)
        for i in range(0, len(usernames_list), batch_size):
            batch = usernames_list[i:i+batch_size]
            url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
            try:
                async with self.session.get(url, headers=headers, timeout=20) as resp:
                    data = await resp.json()
                    live.update({s["user_login"].lower() for s in data.get("data", [])})
            except Exception as e:
                logger.error(f"Erro ao checar lives (batch starting {i}): {e}")
            await asyncio.sleep(0.8)
        return live
