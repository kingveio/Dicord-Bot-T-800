import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import logging
from services.google_drive import GoogleDriveService
from data.models import GuildData, UserData

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
        self.drive = GoogleDriveService()
        self._data = {}
        self._lock = asyncio.Lock()
        self._initialized = True
    
    async def load(self):
        async with self._lock:
            # Try to load from local file
            if self.filepath.exists():
                try:
                    async with aiofiles.open(self.filepath, "r") as f:
                        self._data = json.loads(await f.read())
                    logger.info("Data loaded from local file")
                    return
                except Exception as e:
                    logger.error(f"Failed to load local data: {e}")
            
            # Try to download from Google Drive
            if await self.drive.download_file(self.filepath.name, str(self.filepath)):
                try:
                    async with aiofiles.open(self.filepath, "r") as f:
                        self._data = json.loads(await f.read())
                    logger.info("Data loaded from Google Drive")
                    return
                except Exception as e:
                    logger.error(f"Failed to load Drive data: {e}")
            
            # Create new data structure
            self._data = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "guilds": {}
            }
            logger.info("Created new data structure")
    
    async def save(self):
        async with self._lock:
            try:
                async with aiofiles.open(self.filepath, "w") as f:
                    await f.write(json.dumps(self._data, indent=2))
                
                if Config.is_render():
                    await self.drive.upload_file(str(self.filepath))
                
                logger.info("Data saved successfully")
            except Exception as e:
                logger.error(f"Failed to save data: {e}")
                raise
    
    def get_guild(self, guild_id: int) -> GuildData:
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data.get("guilds", {}):
            self._data.setdefault("guilds", {})[guild_id_str] = {
                "config": {},
                "users": {}
            }
        return self._data["guilds"][guild_id_str]
