import os
import io
import asyncio
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from google.auth.exceptions import DefaultCredentialsError
import logging

logger = logging.getLogger(__name__)

class DriveService:
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_FILE = 'service_account.json'

    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        if os.path.exists(self.SERVICE_ACCOUNT_FILE):
            try:
                self.creds = Credentials.from_service_account_file(
                    self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
                )
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("✅ Autenticação com o Google Drive bem-sucedida.")
            except DefaultCredentialsError as e:
                logger.error(f"❌ Erro de autenticação: {e}")
        else:
            logger.warning("⚠️ Arquivo de conta de serviço não encontrado. O Google Drive não será utilizado.")

    def is_authenticated(self):
        return self.service is not None

    async def _execute_async(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def find_file(self, file_name):
        if not self.is_authenticated(): return None
        try:
            results = await self._execute_async(
                self.service.files().list(
                    q=f"name='{file_name}' and trashed=false",
                    spaces='drive',
                    fields='files(id)'
                ).execute
            )
            items = results.get('files', [])
            return items[0]['id'] if items else None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo '{file_name}': {e}")
            return None

    async def upload_file(self, file_path, mime_type):
        if not self.is_authenticated(): return
        try:
            file_metadata = {'name': os.path.basename(file_path)}
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            file = await self._execute_async(
                self.service.files().create(
                    body=file_metadata, media_body=media, fields='id'
                ).execute
            )
            logger.info(f"✅ Arquivo '{file_path}' enviado. ID: {file.get('id')}")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar arquivo '{file_path}': {e}")

    async def update_file(self, file_id, new_file_path):
        if not self.is_authenticated(): return
        try:
            media = MediaFileUpload(new_file_path, resumable=True)
            await self._execute_async(
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute
            )
            logger.info(f"✅ Arquivo ID '{file_id}' atualizado com '{new_file_path}'.")
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar arquivo ID '{file_id}': {e}")

    async def download_file(self, file_id):
        if not self.is_authenticated(): return None
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, request)
            done = False
            while not done:
                status, done = await self._execute_async(downloader.next_chunk)
            file_stream.seek(0)
            return file_stream.read().decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Erro ao baixar arquivo ID '{file_id}': {e}")
            return None
