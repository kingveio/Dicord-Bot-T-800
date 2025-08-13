import os
import logging
from typing import Optional, Tuple
import base64
import json

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    HAS_GOOGLE_DEPS = True
except ImportError:
    HAS_GOOGLE_DEPS = False
    logger.warning("Bibliotecas do Google não encontradas - funcionalidade do Drive será limitada")

class GoogleDriveService:
    def __init__(self):
        self.service = None
        if HAS_GOOGLE_DEPS:
            self.service = self._setup_service()
        else:
            logger.warning("Google Drive desativado - dependências não instaladas")

    def _setup_service(self):
        """Configura o serviço do Google Drive"""
        try:
            creds_base64 = os.getenv('GOOGLE_CREDENTIALS')
            if not creds_base64:
                logger.warning("Variável GOOGLE_CREDENTIALS não encontrada")
                return None
                
            decoded = base64.b64decode(creds_base64)
            creds_info = json.loads(decoded.decode('utf-8'))
            
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Erro ao configurar Google Drive: {e}")
            return None

    async def upload_file(self, file_path: str) -> Tuple[bool, str]:
        """Tenta fazer upload de um arquivo"""
        if not self.service:
            return False, "Serviço não configurado"
        
        try:
            file_name = os.path.basename(file_path)
            file_metadata = {
                'name': file_name,
                'parents': [os.getenv('DRIVE_FOLDER_ID')]
            }
            
            media = MediaFileUpload(file_path, mimetype='application/json')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            return True, f"Arquivo {file.get('name')} enviado com sucesso"
        except Exception as e:
            return False, str(e)

    async def download_file(self, file_name: str, save_path: str) -> Tuple[bool, str]:
        """Tenta baixar um arquivo"""
        if not self.service:
            return False, "Serviço não configurado"
        
        try:
            results = self.service.files().list(
                q=f"name='{file_name}'",
                fields="files(id, name)"
            ).execute()
            
            items = results.get('files', [])
            if not items:
                return False, "Arquivo não encontrado"
            
            request = self.service.files().get_media(fileId=items[0]['id'])
            with open(save_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return True, f"Arquivo {items[0]['name']} baixado com sucesso"
        except Exception as e:
            return False, str(e)
