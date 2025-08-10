import asyncio
import json
import logging
from typing import Dict, Any, Optional
from drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

# Instância global do serviço do Google Drive
drive_service = GoogleDriveService()
DATA_FILE = "streamers.json"

# Estrutura de dados padrão para quando o arquivo não existe
DEFAULT_DATA = {
    "monitored_users": {
        "twitch": {},
        "youtube": {}
    }
}

async def get_data() -> Dict[str, Any]:
    """Carrega dados do Google Drive. Retorna dados padrão se o arquivo não existir."""
    try:
        if not drive_service.service:
            logger.warning("Serviço do Google Drive não disponível. Usando dados padrão.")
            return DEFAULT_DATA

        data = await drive_service.download_file_to_memory(DATA_FILE)
        if data is None:
            logger.info("Arquivo de dados não encontrado no Drive. Usando dados padrão.")
            return DEFAULT_DATA
        
        # Valida a estrutura
        if not all(k in data["monitored_users"] for k in ["twitch", "youtube"]):
            data["monitored_users"] = DEFAULT_DATA["monitored_users"]
            logger.warning("Estrutura de dados desatualizada. Usando formato padrão.")
        
        logger.info("Dados carregados com sucesso do Google Drive.")
        return data
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar dados do Drive: {e}")
        return DEFAULT_DATA

async def save_data(data: Dict[str, Any]):
    """Salva os dados no Google Drive."""
    try:
        if not drive_service.service:
            logger.warning("Serviço do Google Drive não disponível. Dados não serão salvos.")
            return
            
        json_data = json.dumps(data, indent=2)
        await drive_service.upload_file_from_memory(json_data, DATA_FILE)
        
        logger.info("✅ Dados salvos com sucesso no Google Drive.")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar dados no Drive: {e}")
