import os
import json
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger("T-800")

DEFAULT_DATA = {
    "monitored_users": {
        "twitch": {},
        "youtube": {}
    }
}

async def save_data(drive_service, data: Dict[str, Any]):
    """Salva dados no Google Drive e localmente"""
    try:
        with open("streamers.json", "w") as f:
            json.dump(data, f, indent=2)
        
        if drive_service:
            drive_service.upload_file("streamers.json", "streamers.json")
        
        logger.info("💾 Dados salvos. 'Mission accomplished.'")
    except Exception as e:
        logger.error(f"❌ Falha ao salvar: {e}")

async def load_or_create_data(drive_service) -> Dict[str, Any]:
    """Carrega dados ou cria estrutura inicial"""
    try:
        # Tenta carregar do Drive
        if drive_service and drive_service.download_file("streamers.json", "streamers.json"):
            with open("streamers.json", "r") as f:
                return json.load(f)
        
        # Cria novo arquivo
        with open("streamers.json", "w") as f:
            json.dump(DEFAULT_DATA, f, indent=2)
        
        if drive_service:
            drive_service.upload_file("streamers.json", "streamers.json")
        
        logger.info("🆕 Novo arquivo criado.")
        return DEFAULT_DATA
    
    except Exception as e:
        logger.critical(f"❌ Falha crítica: {e}")
        raise
