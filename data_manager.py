import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

# Definição global explícita
DATA_CACHE: Dict[str, Any] = {
    "streamers": {},
    "youtube_channels": {},
    "monitored_users": {
        "twitch": {},
        "youtube": {}
    }
}
DATA_LOCK = asyncio.Lock()
DATA_FILE = "streamers.json"

def validate_data_structure(data: Dict[str, Any]) -> bool:
    try:
        required_keys = ["streamers", "youtube_channels", "monitored_users"]
        return all(k in data for k in required_keys)
    except Exception:
        return False

async def load_data_from_drive_if_exists(drive_service: Optional['GoogleDriveService'] = None) -> None:
    global DATA_CACHE
    
    async def load_from_file(file_path: str) -> bool:
        try:
            content = ""
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                
                if not content.strip():
                    logger.warning(f"Arquivo {file_path} vazio")
                    return False
                
                data = json.loads(content)
                if validate_data_structure(data):
                    async with DATA_LOCK:
                        DATA_CACHE.update(data)
                    return True
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido em {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro ao carregar {file_path}: {e}")
            return False

    try:
        # Tenta carregar do Google Drive
        if drive_service and hasattr(drive_service, 'download_file'):
            if drive_service.download_file(DATA_FILE, DATA_FILE):
                if await load_from_file(DATA_FILE):
                    logger.info("Dados carregados do Google Drive")
                    return

        # Tenta carregar localmente
        if await load_from_file(DATA_FILE):
            logger.info("Dados carregados localmente")
            return

        # Cria estrutura vazia se necessário
        async with DATA_LOCK:
            DATA_CACHE.update({
                "streamers": {},
                "youtube_channels": {},
                "monitored_users": {
                    "twitch": {},
                    "youtube": {}
                }
            })
        logger.info("Nova estrutura de dados criada")

    except Exception as e:
        logger.critical(f"Falha crítica ao carregar dados: {e}")
        raise

async def save_data(drive_service: Optional['GoogleDriveService'] = None) -> None:
    try:
        async with DATA_LOCK:
            async with aiofiles.open(DATA_FILE, 'w') as f:
                await f.write(json.dumps(DATA_CACHE, indent=2))

            if drive_service and hasattr(drive_service, 'upload_file'):
                await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)
        
        logger.info("Dados salvos com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")
        raise

async def get_data() -> Dict[str, Any]:
    return DATA_CACHE.copy()
