import asyncio
import json
import logging
from typing import Dict
from googleapiclient.errors import HttpError
from drive_service import GoogleDriveService

logger = logging.getLogger("T-800")

# Inicializa o serviço do Google Drive globalmente.
# Isso garante que ele seja criado apenas uma vez.
drive_service = GoogleDriveService()
DATA_FILE_PATH = "data.json"

# Estrutura de dados padrão caso o arquivo não exista.
DEFAULT_DATA = {
    "monitored_users": {
        "twitch": {},
        "youtube": {}
    }
}

async def get_data() -> Dict:
    """Carrega os dados do Google Drive. Se não houver arquivo, retorna um dicionário padrão."""
    try:
        data = drive_service.download_file()
        if data is None:
            logger.warning("⚠️ Arquivo de dados não encontrado ou falha no download. Usando dados padrão.")
            return DEFAULT_DATA
        return data
    except Exception as e:
        logger.error(f"❌ Erro ao carregar dados: {e}")
        return DEFAULT_DATA

async def save_data(data: Dict):
    """Salva os dados no Google Drive."""
    try:
        # Serializa os dados em JSON.
        json_data = json.dumps(data, indent=4)
        
        # Chama o serviço do Drive para criar ou atualizar o arquivo.
        file_id = drive_service.create_or_update_file(json_data)
        if file_id:
            logger.info("✅ Dados salvos com sucesso no Google Drive.")
        else:
            logger.error("❌ Falha ao salvar os dados no Google Drive.")
            
    except HttpError as error:
        logger.error(f"❌ Erro HTTP ao salvar dados: {error}")
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao salvar dados: {e}")
