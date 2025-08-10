import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from googleapiclient.errors import HttpError

logger = logging.getLogger("T-800")

# Nome do arquivo de dados no Google Drive
DATA_FILE_NAME = "streamer_data.json"

# Estrutura padrão de dados
DEFAULT_DATA_STRUCTURE = {
    "streamers": {},
    "youtube_channels": {}
}

# Cache de dados para evitar múltiplas requisições
_DATA_CACHE = None
_LAST_FETCHED = datetime.min
_LAST_WRITE = datetime.min

async def get_cached_data(drive_service) -> Dict[str, Any]:
    """Retorna os dados do cache ou faz o download se estiver desatualizado."""
    global _DATA_CACHE, _LAST_FETCHED
    
    # Se o cache tiver menos de 1 minuto, usa-o
    if (datetime.now() - _LAST_FETCHED) < timedelta(minutes=1):
        return _DATA_CACHE.copy() if _DATA_CACHE else DEFAULT_DATA_STRUCTURE.copy()
    
    # Se não, busca os dados
    if not drive_service.service:
        logger.error("❌ Serviço do Google Drive não inicializado.")
        return DEFAULT_DATA_STRUCTURE.copy()

    try:
        data = await drive_service.download_file_to_memory(DATA_FILE_NAME)
        if data:
            _DATA_CACHE = data
            _LAST_FETCHED = datetime.now()
            return data.copy()
        else:
            logger.warning("Conteúdo do arquivo vazio ou não encontrado. Usando estrutura padrão.")
            _DATA_CACHE = DEFAULT_DATA_STRUCTURE
            _LAST_FETCHED = datetime.now()
            return DEFAULT_DATA_STRUCTURE.copy()
    except Exception as e:
        logger.error(f"Erro fatal ao obter dados: {e}")
        return DEFAULT_DATA_STRUCTURE.copy()

async def set_cached_data(data: Dict[str, Any], drive_service) -> bool:
    """Salva os dados atualizados e atualiza o cache."""
    global _DATA_CACHE, _LAST_FETCHED, _LAST_WRITE
    
    if not drive_service.service:
        logger.error("❌ Serviço do Google Drive não disponível.")
        return False
        
    # Limita a gravação para não sobrecarregar o Drive API
    if (datetime.now() - _LAST_WRITE) < timedelta(seconds=10):
        logger.warning("⚠️ Tentativa de gravação muito rápida. Operação adiada.")
        await asyncio.sleep(10) # Espera 10 segundos antes de tentar de novo

    success = await drive_service.upload_file_from_memory(json.dumps(data, indent=4), DATA_FILE_NAME)
    if success:
        _DATA_CACHE = data
        _LAST_FETCHED = datetime.now()
        _LAST_WRITE = datetime.now()
    return success
