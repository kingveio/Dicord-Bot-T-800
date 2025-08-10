import os
import io
import json
import logging
from typing import Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service_account_info = self._get_service_account_info()
        self.service = self._authenticate()
        self.timeout = 30

    def _get_service_account_info(self) -> Optional[Dict[str, Any]]:
        try:
            private_key = os.environ["DRIVE_PRIVATE_KEY"]
            if '\\n' in private_key:
                private_key = private_key.replace('\\n', '\n')
            
            return {
                "type": "service_account",
                "project_id": os.environ.get("DRIVE_PROJECT_ID", "bot-t-800"),
                "private_key_id": os.environ["DRIVE_PRIVATE_KEY_ID"],
                "private_key": private_key,
                "client_email": os.environ["DRIVE_CLIENT_EMAIL"],
                "client_id": os.environ["DRIVE_CLIENT_ID"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ['DRIVE_CLIENT_EMAIL']}"
            }
        except KeyError as e:
            logger.error(f"Variável de ambiente ausente: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao processar credenciais: {e}")
            return None

    def _authenticate(self):
        if not self.service_account_info:
            return None
        try:
            creds = service_account.Credentials.from_service_account_info(
                self.service_account_info, scopes=self.SCOPES
            )
            logger.info("✅ Autenticação com Google Drive bem-sucedida.")
            return build('drive', 'v3', credentials=creds, cache_discovery=False, static_discovery=False)
        except Exception as e:
            logger.error(f"❌ Erro na autenticação do Google Drive: {e}")
            return None

    def find_file_id(self, file_name: str) -> Optional[str]:
        if not self.service: return None
        try:
            query = f"name='{file_name}' and trashed=false and '{os.environ['DRIVE_FOLDER_ID']}' in parents"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id)',
                pageSize=1
            ).execute()
            files = results.get('files', [])
            return files[0]['id'] if files else None
        except HttpError as e:
            logger.error(f"Erro ao buscar ID do arquivo: {e}")
            return None

    async def download_file_to_memory(self, file_name: str) -> Optional[Dict[str, Any]]:
        file_id = self.find_file_id(file_name)
        if not file_id:
            logger.warning(f"Arquivo '{file_name}' não encontrado no Drive")
            return None
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            data = json.load(fh)
            return data
        except HttpError as e:
            logger.error(f"Erro HTTP ao baixar arquivo: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao baixar e processar arquivo: {e}")
            return None

    async def upload_file_from_memory(self, content: str, file_name: str) -> bool:
        if not self.service: return False
        
        try:
            file_id = self.find_file_id(file_name)
            media = MediaIoBaseUpload(io.BytesIO(content.encode()), mimetype='application/json', resumable=True)
            
            if file_id:
                # Atualiza arquivo existente
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
            else:
                # Cria novo arquivo
                file_metadata = {
                    'name': file_name,
                    'parents': [os.environ['DRIVE_FOLDER_ID']]
                }
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            return True
        except HttpError as e:
            logger.error(f"Erro HTTP ao fazer upload: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo: {e}")
            return False
