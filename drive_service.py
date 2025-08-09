import os
import io
import logging
from typing import Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service_account_info = self._get_service_account_info()
        self.service = self._authenticate()
        self.timeout = 30  # seconds

    def _get_service_account_info(self) -> Dict[str, Any]:
        private_key = os.environ["DRIVE_PRIVATE_KEY"]
        
        # Corrige a formatação da chave privada
        if '\\n' in private_key:
            private_key = private_key.replace('\\n', '\n')
        elif not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
            private_key = '-----BEGIN PRIVATE KEY-----\n' + private_key + '\n-----END PRIVATE KEY-----'
        
        return {
            "type": "service_account",
            "project_id": os.environ.get("DRIVE_PROJECT_ID", "bot-t-800"),
            "private_key_id": os.environ["DRIVE_PRIVATE_KEY_ID"],
            "private_key": private_key,
            "client_email": os.environ.get("DRIVE_CLIENT_EMAIL", "discord-bot-t-800@bot-t-800.iam.gserviceaccount.com"),
            "client_id": os.environ["DRIVE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("DRIVE_CLIENT_X509", "")
        }

    def _authenticate(self):
        try:
            creds = service_account.Credentials.from_service_account_info(
                self.service_account_info,
                scopes=self.SCOPES
            )
            return build('drive', 'v3', credentials=creds, cache_discovery=False)
        except Exception as e:
            logger.error(f"Falha na autenticação com o Google Drive. Verifique suas credenciais.")
            logger.error(f"Detalhes do erro: {str(e)}")
            raise

    def find_file(self, file_name: str) -> Optional[Dict[str, Any]]:
        try:
            query = f"name='{file_name}' and '{os.environ['DRIVE_FOLDER_ID']}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            files = results.get('files', [])
            return files[0] if files else None
        except HttpError as e:
            logger.error(f"Erro ao buscar arquivo no Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar arquivo: {e}")
            return None

    def download_file(self, file_name: str, save_path: str) -> bool:
        file = self.find_file(file_name)
        if not file:
            return False
            
        try:
            request = self.service.files().get_media(fileId=file['id'])
            fh = io.FileIO(save_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.debug(f"Download {int(status.progress() * 100)}% completo")
                
            return True
        except HttpError as e:
            logger.error(f"Erro ao baixar arquivo do Drive: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao baixar arquivo: {e}")
            return False

    def upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        try:
            file_metadata = {
                'name': file_name,
                'parents': [os.environ['DRIVE_FOLDER_ID']]
            }
            media = MediaFileUpload(
                file_path,
                mimetype='application/json',
                resumable=True
            )
            
            existing = self.find_file(file_name)
            if existing:
                file = self.service.files().update(
                    fileId=existing['id'],
                    media_body=media
                ).execute()
            else:
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
            return file.get('id')
        except HttpError as e:
            logger.error(f"Erro ao enviar arquivo para o Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar arquivo: {e}")
            return None
