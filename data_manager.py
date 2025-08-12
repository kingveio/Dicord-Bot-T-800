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
    DEFAULT_DATA = {
        "monitored_users": {
            "twitch": {},
            "youtube": {}
        }
    }
    FILE_NAME = "streamers.json"
    
    try:
        # Tenta carregar localmente primeiro
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'monitored_users' in data:
                    return data
                logger.warning("⚠️ Estrutura inválida, recriando arquivo")
        
        # Tenta do Google Drive se disponível
        if drive_service and drive_service.service:
            if drive_service.download_file(FILE_NAME, FILE_NAME):
                with open(FILE_NAME, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'monitored_users' in data:
                        return data
                    logger.warning("⚠️ Estrutura inválida no Drive, recriando arquivo")
        
        # Cria novo arquivo
        with open(FILE_NAME, 'w') as f:
            json.dump(DEFAULT_DATA, f, indent=2)
            logger.info("🆕 Arquivo streamers.json criado com estrutura padrão")
        
        # Tenta enviar para o Drive
        if drive_service and drive_service.service:
            if not drive_service.upload_file(FILE_NAME, FILE_NAME):
                logger.warning("⚠️ Não foi possível enviar para o Google Drive")
        
        return DEFAULT_DATA
        
    except json.JSONDecodeError:
        logger.error("❌ Arquivo corrompido, recriando...")
        with open(FILE_NAME, 'w') as f:
            json.dump(DEFAULT_DATA, f, indent=2)
        return DEFAULT_DATA
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        return DEFAULT_DATA
