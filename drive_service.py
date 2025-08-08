import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service_account_info = {
            "type": "service_account",
            "project_id": os.environ.get("DRIVE_PROJECT_ID", "bot-t-800"),
            "private_key_id": os.environ["DRIVE_PRIVATE_KEY_ID"],
            "private_key": os.environ["DRIVE_PRIVATE_KEY"].replace('\\n', '\n'),
            "client_email": os.environ.get("DRIVE_CLIENT_EMAIL", "discord-bot-t-800@bot-t-800.iam.gserviceaccount.com"),
            "client_id": os.environ["DRIVE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("DRIVE_CLIENT_X509", "")
        }
        self.service = self._authenticate()

    def _authenticate(self):
        creds = service_account.Credentials.from_service_account_info(
            self.service_account_info,
            scopes=self.SCOPES
        )
        return build('drive', 'v3', credentials=creds)

    def find_file(self, file_name):
        query = f"name='{file_name}' and '{os.environ['DRIVE_FOLDER_ID']}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0] if files else None

    def download_file(self, file_name, save_path):
        file = self.find_file(file_name)
        if not file:
            return False
        request = self.service.files().get_media(fileId=file['id'])
        fh = io.FileIO(save_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return True

    def upload_file(self, file_path, file_name):
        file_metadata = {'name': file_name, 'parents': [os.environ['DRIVE_FOLDER_ID']]}
        media = MediaFileUpload(file_path, mimetype='application/json', resumable=True)
        existing = self.find_file(file_name)
        if existing:
            file = self.service.files().update(fileId=existing['id'], media_body=media).execute()
        else:
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
