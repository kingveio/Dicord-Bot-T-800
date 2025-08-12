import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("T-800")

class DriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service = None
        try:
            self.service = self._authenticate()
            logger.info("✅ Conexão com Google Drive estabelecida.")
        except Exception as e:
            logger.warning(f"⚠️ Falha no Google Drive: {e}. Usando armazenamento local.")

    def _authenticate(self):
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

    def find_file(self, file_name: str):
        try:
            if not self.service:
                return None
                
            results = self.service.files().list(
                q=f"name='{file_name}' and '{os.getenv('DRIVE_FOLDER_ID')}' in parents",
                fields="files(id, name)",
                supportsAllDrives=True  # Adicionado para Shared Drives
            ).execute()
            return results.get('files', [None])[0]
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo: {e}")
            return None
