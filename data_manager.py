import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

# Configuração do logger
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from drive_service import GoogleDriveService

# Fallback para aiofiles
try:
    import aiofiles
    USE_AIOFILES = True
except ImportError:
    USE_AIOFILES = False
    logger.warning("aiofiles não disponível - usando operações síncronas")

# Estrutura de dados global
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
    """Valida a estrutura básica dos dados."""
    try:
        required_keys = ["streamers", "youtube_channels", "monitored_users"]
        return all(k in data for k in required_keys)
    except Exception:
        return False

async def load_from_file(file_path: str) -> bool:
    """Carrega dados de um arquivo local."""
    global DATA_CACHE
    try:
        if USE_AIOFILES:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
        else:
            with open(file_path, 'r') as f:
                content = f.read()
        
        if not content:
            logger.warning("Arquivo de dados está vazio. Criando nova estrutura.")
            return False

        data = json.loads(content)
        if not validate_data_structure(data):
            logger.warning("Estrutura do arquivo de dados inválida. Criando nova estrutura.")
            return False

        async with DATA_LOCK:
            DATA_CACHE.update(data)
        return True

    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Arquivo de dados não encontrado ou corrompido: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar dados do arquivo: {e}")
        return False

async def load_data(drive_service: Optional['GoogleDriveService'] = None) -> None:
    """Carrega dados do Google Drive ou de um arquivo local."""
    try:
        if drive_service and hasattr(drive_service, 'download_file'):
            if await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE):
                if await load_from_file(DATA_FILE):
                    logger.info("Dados carregados do Google Drive")
                    return

        if os.path.exists(DATA_FILE):
            if await load_from_file(DATA_FILE):
                logger.info("Dados carregados localmente")
                return

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
    """Salva dados localmente e no Drive"""
    try:
        async with DATA_LOCK:
            if USE_AIOFILES:
                async with aiofiles.open(DATA_FILE, 'w') as f:
                    await f.write(json.dumps(DATA_CACHE, indent=2))
            else:
                with open(DATA_FILE, 'w') as f:
                    json.dump(DATA_CACHE, f, indent=2)

            if drive_service and hasattr(drive_service, 'upload_file'):
                await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)
        
        logger.info("Dados salvos com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")
        raise

async def get_data() -> Dict[str, Any]:
    """Retorna uma cópia dos dados"""
    async with DATA_LOCK:
        return DATA_CACHE.copy()
