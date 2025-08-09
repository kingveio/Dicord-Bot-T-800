import os
import json
import asyncio
import shutil
import logging
from datetime import datetime
import aiofiles
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

DATA_CACHE = {
    "streamers": {},
    "configs": {},
    "youtube_channels": {}
}
DATA_LOCK = asyncio.Lock()
DATA_FILE = "streamers.json"
AUTO_SAVE_INTERVAL = 300

def validate_data_structure_sync(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict): return False
    if "streamers" not in data or "configs" not in data or "youtube_channels" not in data: return False
    
    if not isinstance(data["streamers"], dict): return False
    for guild_id, streamers in data["streamers"].items():
        if not isinstance(guild_id, str) or not isinstance(streamers, dict): return False
        for twitch_user, discord_id in streamers.items():
            if not isinstance(twitch_user, str) or not isinstance(discord_id, str): return False
    
    if not isinstance(data["configs"], dict): return False
    for guild_id, config in data["configs"].items():
        if not isinstance(guild_id, str) or not isinstance(config, dict): return False
        if "notification_channel_id" in config and not isinstance(config["notification_channel_id"], str):
            return False
    
    if not isinstance(data["youtube_channels"], dict): return False
    for guild_id, channels in data["youtube_channels"].items():
        if not isinstance(guild_id, str) or not isinstance(channels, dict): return False
        for youtube_id, config in channels.items():
            if not isinstance(youtube_id, str) or not isinstance(config, dict): return False
            if "notification_channel_id" not in config or not isinstance(config["notification_channel_id"], str): return False
            if "last_video_id" not in config: return False
    
    return True

def backup_data_sync():
    try:
        if os.path.exists(DATA_FILE):
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"{DATA_FILE}.{timestamp}")
            shutil.copy(DATA_FILE, backup_file)
            logger.info(f"✅ Backup criado: {backup_file}")
    except Exception as e:
        logger.error(f"❌ Erro no backup: {str(e)}")

async def migrate_old_data(data: Dict[str, Any]) -> Dict[str, Any]:
    if "streamers" in data and "configs" in data and "youtube_channels" in data:
        return data
    
    new_data = {
        "streamers": data.get("streamers", {}),
        "configs": data.get("configs", {}),
        "youtube_channels": data.get("youtube_channels", {})
    }
    
    return new_data

async def load_data_from_drive_if_exists(drive_service):
    global DATA_CACHE
    async with DATA_LOCK:
        try:
            downloaded = await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE)
            if downloaded:
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    content = (await f.read()).strip()
                if not content:
                    DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}
                    logger.warning("⚠️ Arquivo do Drive vazio, usando estrutura vazia")
                else:
                    data = json.loads(content)
                    data = await migrate_old_data(data)
                    if not validate_data_structure_sync(data):
                        raise ValueError("Estrutura de dados inválida no Drive")
                    DATA_CACHE = data
                    logger.info("✅ Dados carregados do Drive para cache")
            else:
                if os.path.exists(DATA_FILE):
                    async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                        content = (await f.read()).strip()
                    if content:
                        data = json.loads(content)
                        DATA_CACHE = await migrate_old_data(data)
                    else:
                        DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}
                    logger.info("ℹ️ Dados carregados do arquivo local para cache")
                else:
                    DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}
                    logger.info("ℹ️ Nenhum arquivo de dados encontrado; cache inicializado vazio")
        except Exception as e:
            logger.error(f"❌ Falha ao carregar dados do Drive: {e}")
            try:
                if os.path.exists(DATA_FILE):
                    async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                        content = (await f.read()).strip()
                    if content:
                        data = json.loads(content)
                        DATA_CACHE = await migrate_old_data(data)
                    else:
                        DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}
                    logger.info("ℹ️ Fallback para arquivo local realizado")
                else:
                    DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}
            except Exception as e2:
                logger.error(f"❌ Fallback local falhou: {e2}")
                DATA_CACHE = {"streamers": {}, "configs": {}, "youtube_channels": {}}

async def save_data_to_drive(data: Dict[str, Any], drive_service) -> None:
    global DATA_CACHE
    async with DATA_LOCK:
        if not validate_data_structure_sync(data):
            raise ValueError("Dados não passaram na validação de estrutura")
        
        await asyncio.to_thread(backup_data_sync)
        async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        
        try:
            file_id = await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)
            logger.info(f"📤 Upload concluído (file id: {file_id})")
        except Exception as e:
            logger.error(f"❌ Falha ao enviar para o Google Drive: {e}")

async def get_cached_data() -> Dict[str, Any]:
    async with DATA_LOCK:
        return json.loads(json.dumps(DATA_CACHE))

async def set_cached_data(new_data: Dict[str, Any], drive_service, persist: bool = True) -> None:
    global DATA_CACHE
    async with DATA_LOCK:
        DATA_CACHE = new_data
    if persist:
        await save_data_to_drive(new_data, drive_service)
