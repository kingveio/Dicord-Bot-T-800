import os
import logging
import pickle
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
        self.creds = None
        self.service = self._authenticate()

    def _authenticate(self):
        """Autentica usando OAuth e salva o token para uso futuro"""
        if os.path.exists('token.json'):
            import json
            with open('token.json', 'r') as token_file:
                from google.oauth2.credentials import Credentials
                self.creds = Credentials.from_authorized_user_info(json.load(token_file), self.SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token_file:
                token_file.write(self.creds.to_json())

        return build('drive', 'v3', credentials=self.creds)

    def find_file(self, file_name: str) -> Optional[Dict[str, Any]]:
        query = f"name='{file_name}' and trashed=false"
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()
            items = results.get('files', [])
            return items[0] if items else None
        except Exception as e:
            logger.error(f"Erro ao buscar arquivo no Drive: {e}")
            return None

    def download_file(self, file_name: str, local_path: str) -> bool:
        file_info = self.find_file(file_name)
        if not file_info:
            logger.info(f"Arquivo '{file_name}' não encontrado no Google Drive.")
            return False

        request = self.service.files().get_media(fileId=file_info['id'])
        file_handle = open(local_path, 'wb')
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        try:
            while not done:
                status, done = downloader.next_chunk()
            file_handle.close()
            logger.info(f"✅ Download de '{file_name}' concluído.")
            return True
        except Exception as e:
            logger.error(f"Erro ao baixar arquivo do Drive: {e}")
            return False

    def upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        try:
            file_metadata = {'name': file_name}
            media = MediaFileUpload(file_path, mimetype='application/json', resumable=True)

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
        except Exception as e:
            logger.error(f"Erro ao enviar arquivo para o Drive: {e}")
            return None
