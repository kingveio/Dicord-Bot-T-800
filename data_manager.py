import logging
import json
from io import BytesIO
import asyncio
from google_drive_service import GoogleDriveService

# Configuração do logger
logger = logging.getLogger("T-800")

# O nome do arquivo de dados no Google Drive
DATA_FILE_NAME = "t800_data.json"

# Instância global do serviço do Google Drive
gdrive_service = None

# Estrutura de dados padrão
DEFAULT_DATA = {
    "monitored_users": {
        "twitch": {},
        "youtube": {}
    }
}

def _get_gdrive_service():
    """Retorna a instância do GoogleDriveService, inicializando se necessário."""
    global gdrive_service
    if gdrive_service is None:
        gdrive_service = GoogleDriveService()
    return gdrive_service

async def initialize_data():
    """
    Inicializa o arquivo de dados do bot. Se o arquivo não existir no Google Drive,
    cria um novo com a estrutura padrão.
    """
    try:
        service = _get_gdrive_service()
        data_content = await service.download_file(DATA_FILE_NAME)
        if data_content is None:
            logger.info("⚠️ Arquivo de dados não encontrado. Criando um novo.")
            await save_data(DEFAULT_DATA)
        else:
            logger.info("✅ Arquivo de dados carregado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar o arquivo de dados: {e}", exc_info=True)
        raise

async def get_data():
    """
    Baixa e retorna o conteúdo do arquivo de dados.
    """
    try:
        service = _get_gdrive_service()
        data_content = await service.download_file(DATA_FILE_NAME)
        if data_content:
            return json.loads(data_content.decode('utf-8'))
        return DEFAULT_DATA
    except Exception as e:
        logger.error(f"❌ Falha ao obter dados: {e}", exc_info=True)
        return DEFAULT_DATA

async def save_data(data: dict):
    """
    Salva o conteúdo do dicionário de dados no arquivo.
    """
    try:
        service = _get_gdrive_service()
        data_content = json.dumps(data, indent=4).encode('utf-8')
        await service.upload_file(DATA_FILE_NAME, data_content)
        logger.info("✅ Dados salvos com sucesso.")
    except Exception as e:
        logger.error(f"❌ Falha ao salvar dados: {e}", exc_info=True)
        raise
