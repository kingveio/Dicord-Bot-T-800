import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger("T-800")

class DriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service = self._authenticate()
        logger.info("✅ Conexão com Google Drive estabelecida.")

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
        return build('drive', 'v3', credentials=creds)

    def upload_file(self, file_path: str, file_name: str) -> bool:
        try:
            file_metadata = {'name': file_name, 'parents': [os.getenv("DRIVE_FOLDER_ID")]}
            media = MediaFileUpload(file_path, resumable=True)
            
            existing = self.find_file(file_name)
            if existing:
                self.service.files().update(fileId=existing['id'], media_body=media).execute()
            else:
                self.service.files().create(body=file_metadata, media_body=media).execute()
            
            logger.info(f"📤 Arquivo {file_name} enviado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"❌ Erro no upload: {e}")
            return False

    def find_file(self, file_name: str):
        try:
            results = self.service.files().list(
                q=f"name='{file_name}' and '{os.getenv('DRIVE_FOLDER_ID')}' in parents",
                fields="files(id, name)"
            ).execute()
            return results.get('files', [{}])[0]
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo: {e}")
            return None

async def load_or_create_data(drive_service) -> dict:
    try:
        data = {"monitored_users": {"twitch": {}, "youtube": {}}}
        file_name = "streamers.json"
        
        # Tenta carregar localmente primeiro
        if os.path.exists(file_name):
            with open(file_name, "r") as f:
                return json.load(f)
                
        # Se não existir localmente, tenta do Drive
        if drive_service and drive_service.service:
            file_info = drive_service.find_file(file_name)
            if file_info:
                request = drive_service.service.files().get_media(fileId=file_info['id'])
                with open(file_name, "wb") as f:
                    downloader = MediaIoBaseDownload(f, request)
                    while not downloader.next_chunk()[1]: pass
                with open(file_name, "r") as f:
                    return json.load(f)
        
        # Se não existir em nenhum lugar, cria novo
        with open(file_name, "w") as f:
            json.dump(data, f, indent=2)
            
        if drive_service and drive_service.service:
            try:
                drive_service.upload_file(file_name, file_name)
            except Exception as e:
                logger.warning(f"⚠️ Falha ao enviar para o Drive: {e}")
        
        return data
        
    except Exception as e:
        logger.critical(f"❌ Falha crítica: {e}")
        return {"monitored_users": {"twitch": {}, "youtube": {}}}  # Fallback
