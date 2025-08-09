import os
import json
import asyncio
import aiofiles
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

# Estrutura global de dados
DATA_CACHE = {
    "streamers": {},
    "youtube_channels": {}
}
DATA_LOCK = asyncio.Lock()
DATA_FILE = "streamers.json"

def validate_data_structure_sync(data: Dict[str, Any]) -> bool:
    """Valida a estrutura do arquivo de dados"""
    if not isinstance(data, dict):
        return False
    
    required_sections = {"streamers", "youtube_channels"}
    if not all(section in data for section in required_sections):
        return False

    # Valida estrutura dos streamers da Twitch
    if not all(
        isinstance(guild_id, str) and isinstance(streamers, dict)
        for guild_id, streamers in data["streamers"].items()
    ):
        return False

    # Valida estrutura dos canais do YouTube
    if not all(
        isinstance(guild_id, str) and isinstance(channels, dict)
        for guild_id, channels in data["youtube_channels"].items()
    ):
        return False

    return True

async def load_data_from_drive_if_exists(drive_service: 'GoogleDriveService') -> None:
    """Carrega dados do Google Drive ou cria novo arquivo se não existir"""
    global DATA_CACHE
    
    async with DATA_LOCK:
        try:
            # Tenta carregar do Google Drive
            if drive_service and await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE):
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    if validate_data_structure_sync(data):
                        DATA_CACHE = data
                        logger.info("✅ Dados carregados do Google Drive")
                        return
                    else:
                        logger.warning("⚠️ Dados do Drive inválidos")

            # Fallback para arquivo local
            if os.path.exists(DATA_FILE):
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    if validate_data_structure_sync(data):
                        DATA_CACHE = data
                        logger.info("ℹ️ Dados carregados do arquivo local")
                        return

            # Cria nova estrutura se não existir
            DATA_CACHE = {"streamers": {}, "youtube_channels": {}}
            logger.info("ℹ️ Nova estrutura de dados criada")
            
        except Exception as e:
            logger.error(f"❌ Falha ao carregar dados: {str(e)}")
            DATA_CACHE = {"streamers": {}, "youtube_channels": {}}

async def save_data_to_drive(data: Dict[str, Any], drive_service: 'GoogleDriveService') -> None:
    """Salva dados localmente e no Google Drive"""
    global DATA_CACHE
    
    async with DATA_LOCK:
        if not validate_data_structure_sync(data):
            logger.error("❌ Tentativa de salvar dados inválidos")
            raise ValueError("Estrutura de dados inválida")

        try:
            # Salva localmente
            async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Envia para o Google Drive
            if drive_service:
                file_id = await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)
                logger.info(f"📤 Dados salvos no Drive (ID: {file_id})")
            
            DATA_CACHE = data
            
        except Exception as e:
            logger.error(f"❌ Falha ao salvar dados: {str(e)}")
            raise

async def get_cached_data() -> Dict[str, Any]:
    """Retorna uma cópia dos dados em cache"""
    async with DATA_LOCK:
        return json.loads(json.dumps(DATA_CACHE))

async def set_cached_data(new_data: Dict[str, Any], drive_service: Optional['GoogleDriveService'] = None) -> None:
    """Atualiza os dados em cache e persiste no storage"""
    global DATA_CACHE
    
    async with DATA_LOCK:
        if validate_data_structure_sync(new_data):
            DATA_CACHE = new_data
            await save_data_to_drive(DATA_CACHE, drive_service)
        else:
            logger.error("❌ Tentativa de atualizar com dados inválidos")
            raise ValueError("Estrutura de dados inválida")

async def backup_data() -> None:
    """Cria backup local dos dados"""
    async with DATA_LOCK:
        try:
            if os.path.exists(DATA_FILE):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{DATA_FILE}.backup_{timestamp}"
                shutil.copy(DATA_FILE, backup_file)
                logger.info(f"💾 Backup local criado: {backup_file}")
        except Exception as e:
            logger.error(f"❌ Falha ao criar backup: {str(e)}")
