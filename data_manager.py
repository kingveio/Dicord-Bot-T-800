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
    "youtube_channels": {}
}
DATA_LOCK = asyncio.Lock()
DATA_FILE = "streamers.json"
AUTO_SAVE_INTERVAL = 300  # 5 minutos em segundos

def validate_data_structure_sync(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict): return False
    if "streamers" not in data or "youtube_channels" not in data: return False
    
    # Validação para streamers da Twitch
    if not isinstance(data["streamers"], dict): return False
    for guild_id, streamers in data["streamers"].items():
        if not isinstance(guild_id, str) or not isinstance(streamers, dict): return False
        for twitch_user, discord_id in streamers.items():
            if not isinstance(twitch_user, str) or not isinstance(discord_id, str): return False
    
    # Validação para canais do YouTube
    if not isinstance(data["youtube_channels"], dict): return False
    for guild_id, channels in data["youtube_channels"].items():
        if not isinstance(guild_id, str) or not isinstance(channels, dict): return False
        for youtube_id, config in channels.items():
            if not isinstance(youtube_id, str) or not isinstance(config, dict): return False
            if "notification_channel_id" not in config or not isinstance(config["notification_channel_id"], str):
                return False
            if "last_video_id" not in config and config["last_video_id"] is not None:
                return False
            if "discord_user_id" not in config and config["discord_user_id"] is not None:
                return False
    
    return True

def backup_data_sync():
    try:
        if os.path.exists(DATA_FILE):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_file = f"{DATA_FILE}.backup.{timestamp}"
            shutil.copy(DATA_FILE, backup_file)
            logger.info(f"💾 Backup local criado em {backup_file}")
    except Exception as e:
        logger.error(f"❌ Falha ao criar backup local: {e}")

async def load_data_from_drive_if_exists(drive_service) -> None:
    global DATA_CACHE
    async with DATA_LOCK:
        try:
            if drive_service and await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE):
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    if validate_data_structure_sync(data):
                        DATA_CACHE = data
                        logger.info("✅ Dados carregados com sucesso do Google Drive")
                    else:
                        logger.warning("⚠️ Dados do Drive inválidos. Carregando a partir do backup local, se existir.")
                        raise ValueError("Dados do Drive inválidos")
            elif os.path.exists(DATA_FILE):
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    if validate_data_structure_sync(data):
                        DATA_CACHE = data
                        logger.info("ℹ️ Dados carregados com sucesso do arquivo local")
                    else:
                        logger.warning("⚠️ Dados do arquivo local inválidos. Usando estrutura padrão.")
                        DATA_CACHE = {"streamers": {}, "youtube_channels": {}}
            else:
                logger.info("ℹ️ Nenhum arquivo de dados encontrado. Usando estrutura padrão.")
                DATA_CACHE = {"streamers": {}, "youtube_channels": {}}
        except Exception as e:
            logger.error(f"❌ Falha ao carregar dados. Usando estrutura padrão. Erro: {e}")
            DATA_CACHE = {"streamers": {}, "youtube_channels": {}}
        
        logger.info(f"Data Cache inicializada: {DATA_CACHE}")

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
        if validate_data_structure_sync(new_data):
            DATA_CACHE = new_data
            if persist:
                await save_data_to_drive(DATA_CACHE, drive_service)
        else:
            raise ValueError("Tentativa de salvar dados com estrutura inválida.")
