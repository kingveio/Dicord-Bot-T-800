import os
import base64
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import asyncio

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.service = self._initialize_service()
        self.drive_folder_id = os.getenv("DRIVE_FOLDER_ID")
    
    def _initialize_service(self):
        """Configura o serviço do Google Drive com credenciais pessoais"""
        try:
            creds_base64 = os.getenv("GOOGLE_CREDENTIALS")
            if not creds_base64:
                raise ValueError("Variável GOOGLE_CREDENTIALS não encontrada")
            
            decoded = base64.b64decode(creds_base64)
            creds_info = json.loads(decoded.decode("utf-8"))
            
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Falha na inicialização do Google Drive: {e}")
            return None
    
    async def upload_file(self, file_path: str) -> Tuple[bool, str]:
        """Faz upload de um arquivo para o Google Drive pessoal"""
        if not self.service or not self.drive_folder_id:
            return False, "Serviço não inicializado"
        
        try:
            file_name = Path(file_path).name
            file_metadata = {
                "name": file_name,
                "parents": [self.drive_folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype="application/json",
                resumable=True
            )
            
            def _sync_upload():
                return self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,name,webViewLink"
                ).execute()
            
            file = await asyncio.get_event_loop().run_in_executor(None, _sync_upload)
            logger.info(f"Upload realizado: {file.get('name')} (ID: {file.get('id')})")
            return True, file.get("webViewLink")
        except HttpError as e:
            error_msg = f"Erro HTTP {e.resp.status}: {e._get_reason()}"
            logger.error(f"Falha no upload: {error_msg}")
            return False, error_msg
        except Exception as e:
            logger.error(f"Erro inesperado no upload: {e}")
            return False, str(e)
    
    async def download_file(self, file_name: str, save_path: str) -> Tuple[bool, str]:
        """Baixa um arquivo do Google Drive pessoal"""
        if not self.service or not self.drive_folder_id:
            return False, "Serviço não inicializado"
        
        try:
            query = f"name='{file_name}' and '{self.drive_folder_id}' in parents and trashed=false"
            
            def _sync_search():
                return self.service.files().list(
                    q=query,
                    spaces="drive",
                    fields="files(id,name)"
                ).execute()
            
            results = await asyncio.get_event_loop().run_in_executor(None, _sync_search)
            files = results.get("files", [])
            
            if not files:
                return False, "Arquivo não encontrado"
            
            file_id = files[0]["id"]
            
            def _sync_download():
                request = self.service.files().get_media(fileId=file_id)
                with open(save_path, "wb") as f:
                    downloader = MediaIoBaseDownload(f, request)
                    while not downloader.next_chunk()[1]:
                        pass
            
            await asyncio.get_event_loop().run_in_executor(None, _sync_download)
            logger.info(f"Download realizado: {files[0]['name']}")
            return True, save_path
        except HttpError as e:
            error_msg = f"Erro HTTP {e.resp.status}: {e._get_reason()}"
            logger.error(f"Falha no download: {error_msg}")
            return False, error_msg
        except Exception as e:
            logger.error(f"Erro inesperado no download: {e}")
            return False, str(e)
