import os
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.service = self._setup_service()
    
    def _setup_service(self):
        creds_base64 = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_base64:
            logger.warning("Google Drive credentials not found")
            return None
            
        try:
            decoded = base64.b64decode(creds_base64)
            creds_info = json.loads(decoded.decode("utf-8"))
            
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Failed to setup Google Drive: {e}")
            return None
    
    async def upload_file(self, file_path: str) -> bool:
        if not self.service:
            return False
            
        folder_id = os.getenv("DRIVE_FOLDER_ID")
        if not folder_id:
            return False
            
        try:
            file_name = Path(file_path).name
            file_metadata = {
                "name": file_name,
                "parents": [folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype="application/json",
                resumable=True
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False
    
    async def download_file(self, file_name: str, save_path: str) -> bool:
        if not self.service:
            return False
            
        folder_id = os.getenv("DRIVE_FOLDER_ID")
        if not folder_id:
            return False
            
        try:
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.service.files().list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)"
                ).execute()
            )
            
            items = results.get("files", [])
            if not items:
                return False
                
            file_id = items[0]["id"]
            
            request = self.service.files().get_media(fileId=file_id)
            with open(save_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    
            return True
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return False
