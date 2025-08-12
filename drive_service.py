import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger("T-800")

class DriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service = self._authenticate()
        
    def _authenticate(self):
        try:
            creds = service_account.Credentials.from_service_account_info(
                {
                    "type": "service_account",
                    "private_key": os.getenv("DRIVE_PRIVATE_KEY").replace('\\n', '\n'),
                    "client_email": os.getenv("DRIVE_CLIENT_EMAIL"),
                    "token_uri": "https://oauth2.googleapis.com/token",
                },
                scopes=self.SCOPES
            )
            return build('drive', 'v3', credentials=creds, static_discovery=False)
        except Exception as e:
            logger.error(f"❌ Falha na autenticação: {e}")
            return None

    def find_file(self, file_name: str):
        if not self.service:
            return None
            
        try:
            results = self.service.files().list(
                q=f"name='{file_name}' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()
            
            files = results.get('files', [])
            return files[0] if files else None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo: {e}")
            return None

    def download_file(self, file_name: str, local_path: str) -> bool:
        file_info = self.find_file(file_name)
        if not file_info:
            return False
            
        try:
            request = self.service.files().get_media(fileId=file_info['id'])
            fh = io.FileIO(local_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            return True
        except Exception as e:
            logger.error(f"❌ Download falhou: {e}")
            return False

    def upload_file(self, file_path: str, file_name: str) -> bool:
        try:
            file_metadata = {
                'name': file_name,
                'parents': [os.getenv("DRIVE_FOLDER_ID")]
            }
            media = MediaFileUpload(file_path, resumable=True)
            
            existing = self.find_file(file_name)
            if existing:
                self.service.files().update(
                    fileId=existing['id'],
                    media_body=media
                ).execute()
            else:
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            return True
        except Exception as e:
            logger.error(f"❌ Upload falhou: {e}")
            return False
