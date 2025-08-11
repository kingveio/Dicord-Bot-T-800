import json
import logging
from typing import Dict, Any
from googleapiclient.errors import HttpError

from .drive_service import DriveService

logger = logging.getLogger(__name__)

DATA_CACHE: Dict[str, Any] = {
    "streamers": {},
    "monitored_users": {
        "twitch": {}
    }
}
DATA_FILE_NAME = "streamers.json"


def validate_data_structure(data: Dict[str, Any]) -> bool:
    """Valida a estrutura básica dos dados."""
    try:
        required_keys = ["streamers", "monitored_users"]
        return all(k in data for k in required_keys)
    except Exception:
        return False


async def get_data(drive_service: DriveService = None) -> Dict[str, Any]:
    """Tenta carregar os dados do arquivo ou do Google Drive, se disponível."""
    global DATA_CACHE
    try:
        if drive_service and drive_service.is_authenticated():
            file_id = await drive_service.find_file(DATA_FILE_NAME)
            if file_id:
                content = await drive_service.download_file(file_id)
                DATA_CACHE = json.loads(content)
                logger.info("✅ Dados carregados do Google Drive. Missão concluída.")
            else:
                logger.info("⚠️ Arquivo de dados não encontrado no Google Drive. Criando um novo.")
                DATA_CACHE = {
                    "monitored_users": {
                        "twitch": {}
                    }
                }
        elif os.path.exists(DATA_FILE_NAME):
            with open(DATA_FILE_NAME, "r", encoding="utf-8") as f:
                DATA_CACHE = json.load(f)
            logger.info("✅ Dados carregados localmente. Missão concluída.")
        else:
            logger.info("⚠️ Arquivo de dados local não encontrado. Criando um novo.")

        if not validate_data_structure(DATA_CACHE):
            raise ValueError("Estrutura de dados inválida. Redefinindo o cache.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ Erro ao carregar dados: {e}. Alerta: Falha na operação. Reiniciando dados.")
        DATA_CACHE = {
            "monitored_users": {
                "twitch": {}
            }
        }
        await save_data(drive_service)
    except HttpError as e:
        logger.error(f"❌ Erro da API do Google Drive: {e}. Alerta: Falha na operação.")

    return DATA_CACHE


async def save_data(drive_service: DriveService = None):
    """Salva os dados no arquivo local e no Google Drive, se disponível."""
    try:
        with open(DATA_FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(DATA_CACHE, f, indent=4)
        logger.info("✅ Dados salvos localmente. Missão concluída.")

        if drive_service and drive_service.is_authenticated():
            file_id = await drive_service.find_file(DATA_FILE_NAME)
            if file_id:
                await drive_service.update_file(file_id, DATA_FILE_NAME)
                logger.info("✅ Dados atualizados no Google Drive. Missão concluída.")
            else:
                await drive_service.upload_file(DATA_FILE_NAME, "application/json")
                logger.info("✅ Dados enviados para o Google Drive. Missão concluída.")

    except Exception as e:
        logger.error(f"❌ Erro ao salvar dados: {e}. Alerta: Falha na operação.")

async def initialize_data() -> DriveService:
    """Inicializa o serviço do Drive e carrega os dados."""
    drive_service = DriveService()
    await get_data(drive_service)
    return drive_service
