import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

# Fallback para quando aiofiles não estiver disponível
try:
    import aiofiles
    USE_AIOFILES = True
except ImportError:
    USE_AIOFILES = False
    logger.warning("aiofiles não disponível - usando operações de arquivo síncronas")

DATA_CACHE = {
    "streamers": {},
    "youtube_channels": {}
}
DATA_LOCK = asyncio.Lock()
DATA_FILE = "streamers.json"

def validate_data_structure(data: Dict[str, Any]) -> bool:
    """Valida a estrutura básica dos dados"""
    try:
        return all(k in data for k in ["streamers", "youtube_channels"])
    except Exception:
        return False

async def load_data_from_drive_if_exists(drive_service: Optional['GoogleDriveService'] = None) -> None:
    """Carrega dados do Drive ou arquivo local"""
    global DATA_CACHE
    
    async def load_from_file(file_path: str) -> bool:
        try:
            if USE_AIOFILES:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
            else:
                with open(file_path, 'r') as f:
                    content = f.read()
            
            data = json.loads(content)
            if validate_data_structure(data):
                DATA_CACHE.update(data)
                return True
        except Exception as e:
            logger.error(f"Erro ao carregar {file_path}: {str(e)}")
        return False

    try:
        # 1. Tenta carregar do Google Drive
        if drive_service:
            if await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE):
                if await load_from_file(DATA_FILE):
                    logger.info("Dados carregados do Google Drive")
                    return

        # 2. Tenta carregar localmente
        if os.path.exists(DATA_FILE):
            if await load_from_file(DATA_FILE):
                logger.info("Dados carregados do arquivo local")
                return

        # 3. Cria estrutura vazia se não existir
        DATA_CACHE.update({"streamers": {}, "youtube_channels": {}})
        logger.info("Novo arquivo de dados criado")
        
    except Exception as e:
        logger.critical(f"Falha crítica ao carregar dados: {str(e)}")
        raise

async def save_data(data: Dict[str, Any], drive_service: Optional['GoogleDriveService'] = None) -> None:
    """Salva dados localmente e no Drive"""
    try:
        # 1. Salva localmente
        if USE_AIOFILES:
            async with aiofiles.open(DATA_FILE, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        else:
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)

        # 2. Envia para o Google Drive
        if drive_service:
            await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)

        logger.info("Dados salvos com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {str(e)}")
        raise

async def get_data() -> Dict[str, Any]:
    """Retorna uma cópia dos dados atuais"""
    return DATA_CACHE.copy()
