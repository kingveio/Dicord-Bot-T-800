import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Set, Optional
import aiohttp

logger = logging.getLogger(__name__)

class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.lock = asyncio.Lock()
        self.retry_queue = asyncio.Queue()
        self.max_retries = 3
        self.retry_delay = 5

    async def get_token(self, retries: int = 3) -> Optional[str]:
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
                        if resp.status != 200:
                            logger.error(f"Falha ao obter token da Twitch: {resp.status}")
                            await asyncio.sleep(2)
                            continue
                            
                        data = await resp.json()
                        if "access_token" not in data:
                            logger.error(f"Resposta inesperada da Twitch: {data}")
                            await asyncio.sleep(2)
                            continue
                            
                        self.token = data["access_token"]
                        self.token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 300)
                        logger.info("✅ Token da Twitch obtido")
                        return self.token
                        
                except asyncio.TimeoutError:
                    logger.error(f"Timeout ao obter token (tentativa {attempt+1})")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Erro ao obter token (tentativa {attempt+1}): {e}")
                    await asyncio.sleep(2)
                    
            logger.error("❌ Não foi possível obter token da Twitch após tentativas")
            return None

    async def process_retry_queue(self):
        while True:
            try:
                task = await self.retry_queue.get()
                if task is None:  # Sentinel value to stop the loop
                    break
                    
                username, future, attempt = task
                if attempt >= self.max_retries:
                    future.set_result(False)
                    continue
                    
                try:
                    result = await self._check_single_stream(username)
                    future.set_result(result)
                except Exception as e:
                    logger.error(f"Falha na retentativa {attempt+1} para {username}: {e}")
                    await asyncio.sleep(self.retry_delay)
                    await self.retry_queue.put((username, future, attempt + 1))
            except Exception as e:
                logger.error(f"Erro no processamento da fila de retentativas: {e}")

    async def _check_single_stream(self, username: str) -> bool:
        token = await self.get_token()
        if not token:
            return False
            
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}"
        }
        url = f"https://api.twitch.tv/helix/streams?user_login={username}"
        
        try:
            async with self.session.get(url, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return any(s["user_login"].lower() == username.lower() for s in data.get("data", []))
                elif resp.status == 401:  # Token expired
                    self.token = None
                    return False
                else:
                    logger.error(f"Resposta inesperada ao verificar {username}: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Erro ao verificar streamer {username}: {e}")
            return False

    async def check_live_streams(self, usernames: Set[str]) -> Set[str]:
        if not usernames:
            return set()
            
        token = await self.get_token()
        if not token:
            return set()
            
        headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {token}"}
        live = set()
        batch_size = 100
        usernames_list = list(usernames)
        
        for i in range(0, len(usernames_list), batch_size):
            batch = usernames_list[i:i+batch_size]
            url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
            
            try:
                async with self.session.get(url, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        live.update({s["user_login"].lower() for s in data.get("data", [])})
                    elif resp.status == 401:  # Token expired
                        self.token = None
                        token = await self.get_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                            continue
                        else:
                            break
                    else:
                        logger.error(f"Resposta inesperada ao verificar lives: {resp.status}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout ao verificar batch de lives (batch starting {i})")
            except Exception as e:
                logger.error(f"Erro ao checar lives (batch starting {i}): {e}")
                
            await asyncio.sleep(0.8)
            
        return live
