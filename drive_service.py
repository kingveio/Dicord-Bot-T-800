import os
import io
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import logging
from typing import Optional

logger = logging.getLogger("T-800")

class GoogleDriveService:
    def __init__(self):
        self.service = self._authenticate()
        self.file_name = "data.json"
        self.file_id = self._get_file_id()

    def _authenticate(self):
        """Autentica-se com as credenciais do Google Drive."""
        creds = None
        try:
            creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
            if not creds_json:
                logger.error("❌ Variável de ambiente GOOGLE_DRIVE_CREDENTIALS não encontrada.")
                return None
            creds_info = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(creds_info)
            service = build("drive", "v3", credentials=creds)
            logger.info("✅ Autenticação com Google Drive bem-sucedida.")
            return service
        except Exception as e:
            logger.error(f"❌ Erro na autenticação do Google Drive: {e}")
            return None

    def _get_file_id(self) -> Optional[str]:
        """Busca o ID do arquivo 'data.json' no Google Drive."""
        if not self.service:
            return None
        
        try:
            results = self.service.files().list(
                q=f"name='{self.file_name}' and trashed=false",
                spaces="drive",
                fields="files(id, name)"
            ).execute()
            items = results.get("files", [])
            if not items:
                logger.warning(f"⚠️ Arquivo '{self.file_name}' não encontrado. Ele será criado na inicialização.")
                return None
            return items[0]["id"]
        except HttpError as error:
            logger.error(f"❌ Ocorreu um erro ao buscar o arquivo: {error}")
            return None

    def create_or_update_file(self, content: str) -> Optional[str]:
        """Cria ou atualiza o arquivo 'data.json' no Google Drive."""
        if not self.service:
            return None
        
        try:
            media = MediaIoBaseUpload(io.BytesIO(content.encode()), mimetype="application/json")
            
            if self.file_id:
                # Atualiza o arquivo existente
                updated_file = self.service.files().update(
                    fileId=self.file_id,
                    media_body=media
                ).execute()
                logger.info(f"✅ Arquivo '{self.file_name}' atualizado com sucesso. ID: {updated_file.get('id')}")
                return updated_file.get("id")
            else:
                # Cria um novo arquivo
                file_metadata = {"name": self.file_name}
                new_file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()
                self.file_id = new_file.get("id")
                logger.info(f"✅ Arquivo '{self.file_name}' criado com sucesso. ID: {self.file_id}")
                return self.file_id
        except HttpError as error:
            logger.error(f"❌ Ocorreu um erro ao criar/atualizar o arquivo: {error}")
            return None

    def download_file(self) -> Optional[dict]:
        """Faz o download do arquivo 'data.json' do Google Drive."""
        if not self.service or not self.file_id:
            logger.warning("⚠️ Não foi possível fazer o download. Serviço ou ID do arquivo ausente.")
            return None
        
        try:
            file_content = self.service.files().get(fileId=self.file_id).execute()
            logger.info(f"✅ Iniciando download do arquivo '{self.file_name}'...")
            file_bytes = io.BytesIO()
            downloader = MediaIoBaseDownload(file_bytes, file_content)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            file_bytes.seek(0)
            data = json.load(file_bytes)
            logger.info("✅ Download do arquivo concluído e dados carregados.")
            return data
        except HttpError as error:
            logger.error(f"❌ Ocorreu um erro ao baixar o arquivo: {error}")
            return None
        except json.JSONDecodeError:
            logger.error("❌ Erro ao decodificar o arquivo JSON. O arquivo pode estar corrompido.")
            return None
