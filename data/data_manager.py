import json
import asyncio
import aiofiles
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import asdict
import os

from services.google_drive import GoogleDriveService
from data.models import GuildData, UserData, GuildConfig

logger = logging.getLogger(__name__)

class DataManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.filepath = Path("data/streamers.json")
        self.filepath.parent.mkdir(exist_ok=True)
        self.drive_service = GoogleDriveService()
        self._data = {"guilds": {}, "metadata": {"version": "1.2", "created_at": datetime.now().isoformat()}}
        self._lock = asyncio.Lock()
        self._initialized = True
    
    async def load(self) -> None:
        """Carrega dados do arquivo local ou do Google Drive"""
        async with self._lock:
            # Tentar carregar localmente primeiro
            if await self._load_local():
                return
                
            # Tentar carregar do Google Drive
            if await self._load_from_drive():
                return
                
            # Criar nova estrutura se ambos falharem
            logger.info("Criando nova estrutura de dados")
            self._data = {
                "guilds": {},
                "metadata": {
                    "version": "1.2",
                    "created_at": datetime.now().isoformat(),
                    "last_backup": None
                }
            }
    
    async def _load_local(self) -> bool:
        """Tenta carregar dados do arquivo local"""
        try:
            if not self.filepath.exists():
                return False
                
            async with aiofiles.open(self.filepath, "r") as f:
                content = await f.read()
                self._data = json.loads(content)
                logger.info("Dados carregados do arquivo local")
                return True
        except Exception as e:
            logger.error(f"Erro ao carregar dados locais: {e}")
            return False
    
    async def _load_from_drive(self) -> bool:
        """Tenta baixar e carregar dados do Google Drive"""
        try:
            if not self.drive_service.service:
                return False
                
            if await self.drive_service.download_file(self.filepath.name, str(self.filepath)):
                async with aiofiles.open(self.filepath, "r") as f:
                    content = await f.read()
                    self._data = json.loads(content)
                    logger.info("Dados carregados do Google Drive")
                    return True
            return False
        except Exception as e:
            logger.error(f"Erro ao carregar do Drive: {e}")
            return False
    
    async def save(self) -> None:
        """Salva dados localmente e faz backup no Drive"""
        async with self._lock:
            self._data["metadata"]["last_updated"] = datetime.now().isoformat()
            
            # Salvar localmente
            try:
                async with aiofiles.open(self.filepath, "w") as f:
                    await f.write(json.dumps(self._data, indent=2))
                logger.info("Dados salvos localmente")
            except Exception as e:
                logger.error(f"Erro ao salvar localmente: {e}")
                raise
            
            # Fazer backup no Drive se configurado
            if self.drive_service.service and os.getenv("DRIVE_FOLDER_ID"):
                try:
                    success = await self.drive_service.upload_file(str(self.filepath))
                    if success:
                        self._data["metadata"]["last_backup"] = datetime.now().isoformat()
                        logger.info("Backup no Drive realizado")
                except Exception as e:
                    logger.error(f"Erro no backup no Drive: {e}")
    
    def get_guild(self, guild_id: int) -> GuildData:
        """Obtém ou cria dados de uma guilda"""
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data["guilds"]:
            self._data["guilds"][guild_id_str] = GuildData(guild_id).to_dict()
        return GuildData.from_dict(self._data["guilds"][guild_id_str])
    
    async def update_guild(self, guild_data: GuildData) -> None:
        """Atualiza os dados de uma guilda"""
        self._data["guilds"][str(guild_data.guild_id)] = guild_data.to_dict()
        await self.save()
    
    async def update_guild_config(self, guild_id: int, **kwargs) -> None:
        """Atualiza a configuração de uma guilda"""
        guild = self.get_guild(guild_id)
        for key, value in kwargs.items():
            if hasattr(guild.config, key):
                setattr(guild.config, key, value)
        await self.update_guild(guild)
    
    async def link_user_platform(self, guild_id: int, user_id: int, platform: str, username: str) -> bool:
        """Vincula uma plataforma a um usuário"""
        try:
            guild = self.get_guild(guild_id)
            user = guild.users.get(user_id, UserData(discord_id=user_id))
            
            if platform == "twitch":
                user.twitch = UserPlatform(username=username.lower().strip())
            elif platform == "youtube":
                user.youtube = UserPlatform(username=username.lower().strip())
            else:
                return False
                
            guild.users[user_id] = user
            await self.update_guild(guild)
            return True
        except Exception as e:
            logger.error(f"Erro ao vincular plataforma: {e}")
            return False
    
    async def remove_user_platform(self, guild_id: int, user_id: int, platform: str) -> bool:
        """Remove o vínculo de uma plataforma"""
        try:
            guild = self.get_guild(guild_id)
            if user_id not in guild.users:
                return False
                
            if platform == "twitch":
                guild.users[user_id].twitch = None
            elif platform == "youtube":
                guild.users[user_id].youtube = None
            else:
                return False
                
            # Remove o usuário se não tiver mais plataformas
            if guild.users[user_id].twitch is None and guild.users[user_id].youtube is None:
                del guild.users[user_id]
                
            await self.update_guild(guild)
            return True
        except Exception as e:
            logger.error(f"Erro ao remover plataforma: {e}")
            return False
    
    async def cleanup_inactive_guilds(self, active_guild_ids: List[int]) -> int:
        """Remove guildas inativas e retorna o número de removidas"""
        inactive_guilds = [
            guild_id for guild_id in self._data["guilds"]
            if int(guild_id) not in active_guild_ids
        ]
        
        for guild_id in inactive_guilds:
            del self._data["guilds"][guild_id]
        
        if inactive_guilds:
            await self.save()
        
        return len(inactive_guilds)
