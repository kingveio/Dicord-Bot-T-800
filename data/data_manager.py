# data/data_manager.py
# T-800: Módulo de armazenamento para o bot.
# Gerencia a leitura, escrita e backup de dados de forma assíncrona.
import os
import json
import base64
import binascii
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from io import BytesIO

# Configuração do logger
logger = logging.getLogger(__name__)

# Fallback para aiofiles
try:
    import aiofiles
    USE_AIOFILES = True
except ImportError:
    USE_AIOFILES = False
    logger.warning("⚠️ 'aiofiles' não disponível. Usando operações de arquivo síncronas. "
                   "Considere instalá-lo com 'pip install aiofiles' para melhor performance.")

class DataManager:
    """
    Gerencia o carregamento, salvamento e backup dos dados do bot.
    O arquivo local 'streamers.json' é a fonte de dados primária,
    e o Google Drive é usado para backups.
    """
    
    @classmethod
    async def create(cls, filepath: str = "data/streamers.json") -> "DataManager":
        """
        Método de fábrica assíncrono para criar e inicializar uma instância de DataManager.
        """
        instance = cls(filepath)
        await instance._load_data()
        return instance

    def __init__(self, filepath: str):
        """
        Construtor síncrono. A inicialização de dados é feita no método create().
        """
        self.filepath = filepath
        self.drive_service = self._setup_google_drive_service()
        self.data: Dict[str, Any] = {} # Inicializa a estrutura de dados como vazia.

    def _setup_google_drive_service(self) -> Optional[Any]:
        """
        Configura o serviço da API do Google Drive usando credenciais de uma variável de ambiente.
        """
        logger.info("🔧 Configurando credenciais e serviço do Google Drive...")
        creds_base64 = os.getenv('GOOGLE_CREDENTIALS')
        if not creds_base64:
            logger.warning("⚠️ Variável de ambiente 'GOOGLE_CREDENTIALS' não encontrada.")
            return None
        try:
            decoded = base64.b64decode(creds_base64)
            creds_info = json.loads(decoded.decode('utf-8'))
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            service = build('drive', 'v3', credentials=creds)
            logger.info("✅ Serviço do Google Drive configurado com sucesso.")
            return service
        except (binascii.Error, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Erro ao decodificar as credenciais Base64 ou JSON inválido: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao configurar Google Drive: {e}")
            return None

    def _get_drive_file_id(self, file_name: str, folder_id: str) -> Optional[str]:
        """
        Procura o ID de um arquivo no Google Drive dentro de uma pasta específica.
        """
        try:
            drive_id = os.getenv('DRIVE_ID')
            if not drive_id:
                logger.warning("⚠️ Variável de ambiente 'DRIVE_ID' não definida. Pulando busca em shared drive.")
                return None
            
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            response = self.drive_service.files().list(
                q=query,
                spaces='drive',
                corpora='drive',
                driveId=drive_id,
                fields='files(id)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = response.get('files', [])
            if files:
                return files[0]['id']
            return None
        except HttpError as e:
            logger.error(f"❌ Erro HTTP ao buscar arquivo no Drive: {e.content.decode('utf-8')}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar arquivo no Drive: {e}")
            return None

    def _download_from_drive(self, file_name: str, folder_id: str) -> bool:
        """
        Baixa um arquivo do Google Drive para o disco local.
        Esta é uma operação síncrona.
        """
        file_id = self._get_drive_file_id(file_name, folder_id)
        if not file_id:
            return False

        try:
            logger.info(f"⬇️ Baixando '{file_name}' do Google Drive...")
            request = self.drive_service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            with open(self.filepath, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            logger.info(f"✅ Download de '{file_name}' concluído com sucesso.")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao baixar '{file_name}' do Drive: {e}")
            return False

    async def _load_data(self) -> None:
        """
        Carrega os dados do arquivo local de forma assíncrona. Se o arquivo não existir localmente,
        tenta baixá-lo do Google Drive. Se não for possível, inicializa uma nova estrutura de dados.
        """
        if os.path.exists(self.filepath):
            try:
                if USE_AIOFILES:
                    async with aiofiles.open(self.filepath, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        self.data = json.loads(content)
                else:
                    with open(self.filepath, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)

                logger.info("✅ Dados carregados do arquivo local.")
                return

            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"❌ Erro ao carregar arquivo local '{self.filepath}': {e}")
                
        # Se o arquivo local não existe ou está corrompido, tenta o Drive.
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if self.drive_service and drive_folder_id:
            if await asyncio.to_thread(self._download_from_drive, os.path.basename(self.filepath), drive_folder_id):
                try:
                    if USE_AIOFILES:
                         async with aiofiles.open(self.filepath, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            self.data = json.loads(content)
                    else:
                        with open(self.filepath, 'r', encoding='utf-8') as f:
                            self.data = json.load(f)

                    logger.info("✅ Dados carregados do Google Drive.")
                    return
                except Exception as e:
                    logger.error(f"❌ Erro ao carregar arquivo baixado do Drive: {e}")
        
        # Se tudo falhar, inicializa uma nova estrutura
        default_data = {
            "guilds": {},
            "metadata": {
                "version": "4.0",
                "created_at": datetime.now().isoformat(),
                "last_synced": None
            }
        }
        logger.info("🆕 Nenhuma fonte de dados encontrada. Criando nova estrutura de dados.")
        self.data = default_data
        await self.save_data()

    async def save_data(self) -> None:
        """
        Salva os dados no arquivo local e faz upload para o Google Drive.
        """
        try:
            self.data["metadata"]["last_synced"] = datetime.now().isoformat()
            
            # Salvar localmente de forma assíncrona se aiofiles estiver disponível
            if USE_AIOFILES:
                async with aiofiles.open(self.filepath, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(self.data, indent=4, ensure_ascii=False))
            else:
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            logger.info("✅ Dados salvos localmente com sucesso.")
            
            # Fazer upload para o Drive
            drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
            if self.drive_service and drive_folder_id:
                await asyncio.to_thread(self._upload_to_drive, self.filepath, os.path.basename(self.filepath), drive_folder_id)
            else:
                logger.warning("⚠️ Serviço do Google Drive não está configurado ou 'DRIVE_FOLDER_ID' está ausente. Backup ignorado.")

        except Exception as e:
            logger.error(f"❌ Erro ao salvar dados: {e}")
            raise

    def _upload_to_drive(self, local_filepath: str, file_name: str, folder_id: str) -> None:
        """
        Faz upload de um arquivo local para o Google Drive.
        Esta é uma operação síncrona.
        """
        try:
            file_id = self._get_drive_file_id(file_name, folder_id)
            media = MediaFileUpload(local_filepath, mimetype='application/json', resumable=True)
            
            if file_id:
                logger.info(f"⬆️ Atualizando backup no Google Drive (ID: {file_id})...")
                self.drive_service.files().update(
                    fileId=file_id,
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
            else:
                logger.info("⬆️ Criando novo backup no Google Drive...")
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
            
            logger.info("✅ Backup concluído com sucesso.")

        except HttpError as e:
            logger.error(f"❌ Erro HTTP ao fazer upload: {e.content.decode('utf-8')}")
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao fazer upload: {e}")


    def get_guild_data(self, guild_id: int) -> Dict:
        """Retorna os dados da guilda, mas não os salva. Isso precisa ser feito separadamente."""
        guild_id_str = str(guild_id)
        if guild_id_str not in self.data["guilds"]:
            self.data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "users": {},
                "config": {
                    "notify_channel": None
                }
            }
        return self.data["guilds"][guild_id_str]

    async def link_user_channel(self, guild_id: int, user_id: int, platform: str, channel_id: str) -> bool:
        try:
            guild_data = self.get_guild_data(guild_id)
            user_id_str = str(user_id)
            if user_id_str not in guild_data["users"]:
                guild_data["users"][user_id_str] = {}
            guild_data["users"][user_id_str][platform] = channel_id.lower().strip()
            await self.save_data()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao vincular canal: {e}")
            return False

    async def remove_user_platform(self, guild_id: int, user_id: int, platform: str) -> bool:
        try:
            guild_data = self.get_guild_data(guild_id)
            user_id_str = str(user_id)
            if user_id_str in guild_data["users"] and platform in guild_data["users"][user_id_str]:
                del guild_data["users"][user_id_str][platform]
                await self.save_data()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao remover plataforma: {e}")
            return False
