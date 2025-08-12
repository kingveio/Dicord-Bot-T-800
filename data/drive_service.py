# T-800: Módulo de armazenamento. Gerenciando dados na nuvem.
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Substitua com o caminho para o arquivo de credenciais do Google Drive.
# Se estiver no Render, a variável de ambiente pode conter o conteúdo.
CREDENTIALS_FILE = "path/to/your/credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveService:
    def __init__(self):
        self.credentials = self._get_credentials()
        self.service = build('drive', 'v3', credentials=self.credentials)

    def _get_credentials(self):
        try:
            # Tenta carregar as credenciais de um arquivo local
            if os.path.exists(CREDENTIALS_FILE):
                return service_account.Credentials.from_service_account_file(
                    CREDENTIALS_FILE, scopes=SCOPES
                )
            # Ou, se estiver em um ambiente como o Render, pode estar em uma variável de ambiente
            # O código abaixo é um exemplo e precisa ser adaptado
            # creds_info = json.loads(os.getenv("DRIVE_PRIVATE_KEY"))
            # return service_account.Credentials.from_service_account_info(
            #     creds_info, scopes=SCOPES
            # )
            # Ou use o Google Auth para autenticação
            # from google.auth.transport.requests import Request
            # ...
        except Exception as e:
            print(f"Erro ao carregar credenciais do Google Drive: {e}")
            return None

    def upload_file(self, filename, filepath, folder_id=None):
        if not self.service:
            print("Serviço do Google Drive não inicializado.")
            return

        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(filepath, mimetype='application/json')
        try:
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print(f"Arquivo '{filename}' enviado com sucesso. ID do arquivo: {file.get('id')}")
            return file.get('id')
        except HttpError as error:
            print(f"Ocorreu um erro ao enviar o arquivo: {error}")
            return None
