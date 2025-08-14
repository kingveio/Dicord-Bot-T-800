import json
import asyncio
import aiofiles
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import os
from services.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.bot = None
        self.data_dir = Path("data")
        self.filepath = self.data_dir / "streamers.json"
        self._data: Dict[str, Any] = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "guilds": {}
        }
        self._lock = asyncio.Lock()
        self.google_drive_service: Optional[object] = None # O serviço agora é injetado

    async def init_services(self, bot):
        """Inicializa serviços que dependem do bot"""
        self.bot = bot
        if self.google_drive_service:
            logger.info("✅ Serviço Google Drive inicializado")
            await self.load()
        else:
            logger.warning("Serviço Google Drive não configurado. Backup desativado.")
            await self.load()
    
    async def load(self) -> None:
        """Carrega dados do arquivo local ou do Google Drive"""
        async with self._lock:
            self.data_dir.mkdir(exist_ok=True)
            
            if self.google_drive_service and self.google_drive_service.service:
                logger.info("Tentando carregar dados do Google Drive...")
                success, msg = await self.google_drive_service.download_file(self.filepath.name, self.filepath)
                if success:
                    logger.info(f"Dados baixados do Google Drive: {msg}")
                else:
                    logger.warning(f"Falha ao baixar do Drive: {msg}. Carregando do arquivo local, se existir.")

            try:
                if self.filepath.exists():
                    async with aiofiles.open(self.filepath, "r", encoding="utf-8") as f:
                        loaded_data = json.loads(await f.read())
                        if self._validate_data(loaded_data):
                            self._data = loaded_data
                            logger.info("Dados carregados do arquivo local")
                        else:
                            logger.warning("Dados locais inválidos, usando estrutura padrão")
                else:
                    logger.info("Nenhum arquivo de dados encontrado, usando estrutura padrão")
            except Exception as e:
                logger.error(f"Erro ao carregar dados: {e}")

    async def save(self) -> None:
        """Salva dados no arquivo local e faz backup no Google Drive"""
        async with self._lock:
            try:
                async with aiofiles.open(self.filepath, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self._data, indent=4))
                logger.info("Dados salvos localmente.")

                if self.google_drive_service and self.google_drive_service.service:
                    success, msg = await self.google_drive_service.upload_file(self.filepath)
                    if success:
                        logger.info(f"Backup no Google Drive: {msg}")
                    else:
                        logger.error(f"Falha no backup do Google Drive: {msg}")

            except Exception as e:
                logger.error(f"Erro ao salvar dados: {e}")

    def _validate_data(self, data: Dict) -> bool:
        return "guilds" in data and "version" in data

    def get_guild(self, guild_id: int) -> Dict:
        return self._data["guilds"].setdefault(str(guild_id), {"config": {}, "users": {}})

    async def update_guild_config(self, guild_id: int, **kwargs) -> None:
        guild_data = self.get_guild(guild_id)
        guild_data["config"].update(kwargs)
        await self.save()

    async def link_user_platform(self, guild_id: int, user_id: int, platform: str, username: str) -> bool:
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
            
    async def remove_account(self, guild_id: int, user_id: int, platform: Optional[str] = None) -> bool:
        guild_data = self.get_guild(guild_id)
        user_id_str = str(user_id)
        if user_id_str not in guild_data["users"]:
            return False

        if platform:
            if platform in guild_data["users"][user_id_str]:
                del guild_data["users"][user_id_str][platform]
                if not guild_data["users"][user_id_str]:
                    del guild_data["users"][user_id_str]
                await self.save()
                return True
        else:
            if user_id_str in guild_data["users"]:
                del guild_data["users"][user_id_str]
                await self.save()
                return True
        return False
