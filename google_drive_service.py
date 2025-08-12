import os
import json
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from io import BytesIO
from datetime import datetime

# Configuração do logger
logger = logging.getLogger("T-800")

class GoogleDriveService:
    def __init__(self):
        """
        Inicializa o serviço do Google Drive.
        Carrega as credenciais da variável de ambiente e constrói o objeto de serviço.
        """
        self._service = self._authenticate()
        self.folder_id = os.environ.get("DRIVE_FOLDER_ID")
        if not self.folder_id:
            logger.error("❌ A variável de ambiente 'DRIVE_FOLDER_ID' não está configurada.")
            raise EnvironmentError("Variável de ambiente 'DRIVE_FOLDER_ID' ausente.")

        logger.info("✅ Serviço do Google Drive inicializado.")

    def _authenticate(self):
        """
        Autentica usando a chave da conta de serviço e retorna o objeto de serviço do Drive.
        """
        try:
            service_account_info = json.loads(os.environ.get("DRIVE_SERVICE_KEY"))
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.critical(f"❌ Falha na autenticação do Google Drive: {e}")
            raise

    async def upload_file(self, file_name: str, file_content: bytes):
        """
        Atualiza um arquivo no Google Drive. Se não existir, cria um novo.
        """
        try:
            file_id = await self._find_file(file_name)
            media = discord.File(BytesIO(file_content), filename=file_name).file

            if file_id:
                # Atualiza arquivo existente
                updated_file = self._service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                logger.info(f"✅ Arquivo '{file_name}' atualizado com sucesso. ID: {updated_file['id']}")
            else:
                # Cria novo arquivo
                file_metadata = {
                    'name': file_name,
                    'parents': [self.folder_id]
                }
                new_file = self._service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                logger.info(f"✅ Arquivo '{file_name}' criado com sucesso. ID: {new_file['id']}")
        except HttpError as e:
            logger.error(f"❌ Erro ao interagir com o Google Drive: {e.content.decode()}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao interagir com o Google Drive: {e}", exc_info=True)
            raise

    async def download_file(self, file_name: str):
        """
        Baixa o conteúdo de um arquivo do Google Drive.
        """
        try:
            file_id = await self._find_file(file_name)
            if file_id:
                request = self._service.files().get_media(fileId=file_id)
                file_content = request.execute()
                logger.info(f"✅ Arquivo '{file_name}' baixado com sucesso.")
                return file_content
            else:
                logger.warning(f"⚠️ Arquivo '{file_name}' não encontrado no Google Drive.")
                return None
        except HttpError as e:
            logger.error(f"❌ Erro ao baixar arquivo do Google Drive: {e.content.decode()}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao baixar arquivo do Google Drive: {e}", exc_info=True)
            raise
            
    async def _find_file(self, file_name: str):
        """
        Busca um arquivo por nome dentro da pasta especificada.
        """
        query = f"name='{file_name}' and '{self.folder_id}' in parents and trashed=false"
        results = self._service.files().list(
            q=query,
            spaces='drive',
            fields='files(id)'
        ).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
