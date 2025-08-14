import json
import asyncio
import aiofiles
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.bot = None  # Será definido pelo bot
        self.data_dir = Path("data")
        self.filepath = self.data_dir / "streamers.json"
        self._data: Dict[str, Any] = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "guilds": {}
        }
        self._lock = asyncio.Lock()
async def save(self) -> None:
    """Salva os dados localmente e faz backup se o serviço estiver disponível"""
    async with self._lock:
        try:
            # Lógica de salvamento local (já existente)
            self._data["last_updated"] = datetime.now().isoformat()
            async with aiofiles.open(self.filepath, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self._data, indent=2, ensure_ascii=False))

            logger.info("Dados salvos com sucesso")

            # --- Adicione esta parte para o backup ---
            if hasattr(self, 'google_drive_service') and self.google_drive_service.service:
                success, message = await self.google_drive_service.upload_file(self.filepath)
                if success:
                    logger.info(f"✅ Backup no Google Drive: {message}")
                else:
                    logger.warning(f"⚠️ Falha no backup do Google Drive: {message}")
            # ----------------------------------------
        except Exception as e:
            logger.error(f"Falha ao salvar dados: {e}")
            raise
            
    async def load(self) -> None:
        """Carrega dados do arquivo local ou cria nova estrutura"""
        async with self._lock:
            # Garante que o diretório existe
            self.data_dir.mkdir(exist_ok=True)
            
            try:
                if self.filepath.exists():
                    async with aiofiles.open(self.filepath, "r", encoding="utf-8") as f:
                        loaded_data = json.loads(await f.read())
                        if self._validate_data(loaded_data):
                            self._data = loaded_data
                            logger.info("Dados carregados do arquivo local")
                        else:
                            logger.warning("Dados locais inválidos, usando estrutura padrão")
            except Exception as e:
                logger.error(f"Erro ao carregar dados: {e}")
                # Mantém a estrutura padrão se houver erro

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Valida a estrutura básica dos dados carregados"""
        return all(key in data for key in ["version", "created_at", "guilds"])

    async def save(self) -> None:
        """Salva os dados localmente"""
        async with self._lock:
            try:
                self._data["last_updated"] = datetime.now().isoformat()
                async with aiofiles.open(self.filepath, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self._data, indent=2, ensure_ascii=False))
                logger.info("Dados salvos com sucesso")
            except Exception as e:
                logger.error(f"Falha ao salvar dados: {e}")
                raise

    def get_guild(self, guild_id: int):
        """Método seguro para obter dados da guilda"""
        if not hasattr(self, '_data'):
            raise RuntimeError("Dados não carregados")
        
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data["guilds"]:
            self._create_default_guild(guild_id)
            
        return self._data["guilds"][guild_id_str]
    
    def _create_default_guild(self, guild_id):
        guild_id_str = str(guild_id)
        self._data["guilds"][guild_id_str] = {
            "config": {
                "live_role_id": None,
                "notify_channel_id": None
            },
            "users": {}
        }
        return self._data["guilds"][guild_id_str]

    async def update_guild_config(self, guild_id: int, **kwargs) -> None:
        """Atualiza configurações específicas da guilda"""
        guild_data = self.get_guild(guild_id)
        for key, value in kwargs.items():
            if key in guild_data["config"]:
                guild_data["config"][key] = value
        await self.save()

    async def link_user_platform(self, guild_id: int, user_id: int, platform: str, username: str) -> bool:
        """Vincula uma plataforma a um usuário"""
        try:
            guild_data = self.get_guild(guild_id)
            user_id_str = str(user_id)
            
            if user_id_str not in guild_data["users"]:
                guild_data["users"][user_id_str] = {}
            
            guild_data["users"][user_id_str][platform] = {
                "username": username,
                "linked_at": datetime.now().isoformat()
            }
            
            await self.save()
            return True
        except Exception as e:
            logger.error(f"Erro ao vincular plataforma: {e}")
            return False

    async def cleanup_inactive_guilds(self, active_guild_ids: list) -> int:
        """Remove guildas inativas e retorna o número de removidas"""
        inactive = [gid for gid in self._data["guilds"] if int(gid) not in active_guild_ids]
        for gid in inactive:
            del self._data["guilds"][gid]
        
        if inactive:
            await self.save()
        
        return len(inactive)
