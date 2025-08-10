import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta

logger = logging.getLogger("T-800")

# Nome do arquivo de dados no Google Drive
DATA_FILE_NAME = "streamer_data.json"
# ID da pasta onde o arquivo será salvo (se não existir, salva na raiz)
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
# ID do arquivo de dados no Google Drive, uma vez encontrado ou criado
FILE_ID = None

# Estrutura padrão de dados
DEFAULT_DATA_STRUCTURE = {
    "streamers": {},
    "youtube_channels": {}
}

async def _find_file(drive_service, file_name: str, folder_id: Optional[str] = None):
    """Procura por um arquivo no Google Drive."""
    query = f"name='{file_name}' and trashed=false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    
    try:
        results = await asyncio.to_thread(
            drive_service.files().list,
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute
        
        items = results.get('files', [])
        return items[0]['id'] if items else None
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo no Drive: {e}")
        return None

async def _create_file(drive_service, file_name: str, folder_id: Optional[str] = None):
    """Cria um novo arquivo no Google Drive."""
    try:
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media_body = discord.File(json.dumps(DEFAULT_DATA_STRUCTURE).encode('utf-8'))
        
        file = await asyncio.to_thread(
            drive_service.files().create,
            body=file_metadata,
            media_body=media_body,
            fields='id'
        ).execute
        
        logger.info(f"✅ Arquivo '{file_name}' criado no Google Drive. ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logger.error(f"Erro ao criar arquivo no Drive: {e}")
        return None

async def _get_file_content(drive_service, file_id: str):
    """Faz o download do conteúdo de um arquivo do Google Drive."""
    try:
        response = await asyncio.to_thread(
            drive_service.files().get_media,
            fileId=file_id
        ).execute
        return json.loads(response.decode('utf-8'))
    except HttpError as e:
        if e.resp.status == 404:
            logger.error(f"Arquivo não encontrado com o ID {file_id}. Tentando recriar...")
            return None
        logger.error(f"Erro HTTP ao baixar arquivo: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro ao baixar conteúdo do arquivo: {e}")
        return None

async def _update_file_content(drive_service, file_id: str, content: Dict[str, Any]):
    """Atualiza o conteúdo de um arquivo no Google Drive."""
    try:
        media_body = discord.File(json.dumps(content, indent=4).encode('utf-8'))
        
        await asyncio.to_thread(
            drive_service.files().update,
            fileId=file_id,
            media_body=media_body
        ).execute
        logger.info("✅ Dados salvos com sucesso no Google Drive.")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao salvar dados no Google Drive: {e}")
        return False

# Cache de dados para evitar múltiplas requisições
_DATA_CACHE = None
_LAST_FETCHED = datetime.min

async def get_cached_data() -> Dict[str, Any]:
    """Retorna os dados do cache ou faz o download se estiver desatualizado."""
    global _DATA_CACHE, _LAST_FETCHED, FILE_ID
    
    # Se o cache tiver menos de 1 minuto, usa-o
    if (datetime.now() - _LAST_FETCHED) < timedelta(minutes=1):
        return _DATA_CACHE.copy() if _DATA_CACHE else DEFAULT_DATA_STRUCTURE.copy()
    
    # Se não, busca os dados
    if FILE_ID is None:
        from discord_bot import bot as discord_bot
        drive_service = discord_bot.drive_service
        if not drive_service:
            logger.error("❌ Serviço do Google Drive não inicializado.")
            return DEFAULT_DATA_STRUCTURE.copy()
            
        FILE_ID = await _find_file(drive_service, DATA_FILE_NAME, FOLDER_ID)
        if not FILE_ID:
            FILE_ID = await _create_file(drive_service, DATA_FILE_NAME, FOLDER_ID)
            if not FILE_ID:
                return DEFAULT_DATA_STRUCTURE.copy()

    try:
        from discord_bot import bot as discord_bot
        data = await _get_file_content(discord_bot.drive_service, FILE_ID)
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
    global _DATA_CACHE, _LAST_FETCHED, FILE_ID
    
    if not drive_service or not FILE_ID:
        logger.error("❌ Serviço do Google Drive ou ID do arquivo não disponível.")
        return False
        
    success = await _update_file_content(drive_service, FILE_ID, data)
    if success:
        _DATA_CACHE = data
        _LAST_FETCHED = datetime.now()
    return success
