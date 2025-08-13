import json
import asyncio
import aiofiles
import logging
from pathlib import Path
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.data_dir = Path("data")
        self.filepath = self.data_dir / "streamers.json"
        self._data = None
        self._lock = asyncio.Lock()

    async def load(self):
        """Carrega dados com fallback: Drive -> Local -> Novo"""
        async with self._lock:
            # Garante que o diretório existe
            self.data_dir.mkdir(exist_ok=True)
            
            # Tenta carregar localmente
            if await self._load_local():
                return
                
            # Se não existir local, cria novo
            self._data = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "guilds": {}
            }
            await self.save()

    async def _load_local(self) -> bool:
        """Tenta carregar do arquivo local"""
        try:
            if not self.filepath.exists():
                return False
                
            async with aiofiles.open(self.filepath, "r") as f:
                self._data = json.loads(await f.read())
                logger.info("Dados carregados localmente")
                return True
        except Exception as e:
            logger.error(f"Erro ao carregar dados locais: {e}")
            return False

    async def save(self):
        """Salva os dados localmente"""
        async with self._lock:
            try:
                async with aiofiles.open(self.filepath, "w") as f:
                    await f.write(json.dumps(self._data, indent=2))
                logger.info("Dados salvos localmente")
            except Exception as e:
                logger.error(f"Erro ao salvar dados: {e}")
                raise

    def get_guild(self, guild_id: int):
        """Obtém dados da guilda (não assíncrono)"""
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data["guilds"]:
            self._data["guilds"][guild_id_str] = {
                "config": {
                    "live_role_id": None,
                    "notify_channel_id": None
                },
                "users": {},
                "created_at": datetime.now().isoformat()
            }
        return self._data["guilds"][guild_id_str]

    async def update_guild(self, guild_id: int, data: dict):
        """Atualiza dados da guilda"""
        async with self._lock:
            self._data["guilds"][str(guild_id)] = data
            await self.save()
