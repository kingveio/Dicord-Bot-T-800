# data/data_manager.py
# T-800: Módulo de armazenamento para o bot.
# Gerencia a leitura, escrita e backup de dados de forma assíncrona.
import os
import json
import base64
import binascii
import copy
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Counter
from dataclasses import dataclass, field
import asyncio
import logging
from contextlib import asynccontextmanager

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

# Constantes
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
CACHE_DURATION = timedelta(minutes=5)

@dataclass
class DataManagerMetrics:
    """Métricas para monitoramento do DataManager"""
    saves_count: int = 0
    loads_count: int = 0
    drive_uploads: int = 0
    drive_downloads: int = 0
    cache_hits: int = 0
    errors: Counter = field(default_factory=Counter)
    
    def log_save(self):
        self.saves_count += 1
        logger.debug(f"📊 Total saves: {self.saves_count}")
    
    def log_load(self):
        self.loads_count += 1
        logger.debug(f"📊 Total loads: {self.loads_count}")
    
    def log_cache_hit(self):
        self.cache_hits += 1
        logger.debug(f"📊 Cache hits: {self.cache_hits}")
    
    def log_error(self, operation: str):
        self.errors[operation] += 1
        logger.error(f"📊 Errors in {operation}: {self.errors[operation]}")

class GoogleDriveManager:
    """Gerencia operações específicas do Google Drive"""
    
    def __init__(self):
        self.service = self._setup_service()
        self._cache = {}
        self._cache_timestamps = {}
    
    def _setup_service(self) -> Optional[Any]:
        """Configura o serviço da API do Google Drive"""
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
    
    def _is_cache_valid(self, key: str) -> bool:
        """Verifica se o cache ainda é válido"""
        if key not in self._cache_timestamps:
            return False
        return datetime.now() - self._cache_timestamps[key] < CACHE_DURATION
    
    async def _retry_operation(self, operation, *args, **kwargs):
        """Executa uma operação com retry e backoff exponencial"""
        for attempt in range(DEFAULT_RETRY_COUNT):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                if attempt == DEFAULT_RETRY_COUNT - 1:
                    raise e
                
                delay = min(DEFAULT_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                logger.warning(f"⚠️ Tentativa {attempt + 1} falhou: {e}. Tentando novamente em {delay}s...")
                await asyncio.sleep(delay)
    
    async def get_file_id(self, file_name: str, folder_id: str) -> Optional[str]:
        """Busca o ID de um arquivo no Google Drive com cache"""
        if not self.service:
            return None
        
        cache_key = f"{file_name}:{folder_id}"
        
        # Verificar cache
        if self._is_cache_valid(cache_key):
            logger.debug(f"📋 Cache hit para {file_name}")
            return self._cache.get(cache_key)
        
        async def _search_file():
            drive_id = os.getenv('DRIVE_ID')
            if not drive_id:
                logger.warning("⚠️ Variável de ambiente 'DRIVE_ID' não definida.")
                return None

            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(None, 
                lambda: self.service.files().list(
                    q=query,
                    spaces='drive',
                    corpora='drive',
                    driveId=drive_id,
                    fields='files(id)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
            )
            
            files = response.get('files', [])
            file_id = files[0]['id'] if files else None
            
            # Atualizar cache
            self._cache[cache_key] = file_id
            self._cache_timestamps[cache_key] = datetime.now()
            
            return file_id
        
        try:
            return await self._retry_operation(_search_file)
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo no Drive: {e}")
            return None
    
    async def download_file(self, file_name: str, folder_id: str, local_path: str) -> bool:
        """Baixa um arquivo do Google Drive"""
        if not self.service:
            return False
        
        file_id = await self.get_file_id(file_name, folder_id)
        if not file_id:
            return False

        async def _download():
            logger.info(f"⬇️ Baixando '{file_name}' do Google Drive...")
            loop = asyncio.get_event_loop()
            
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            
            await loop.run_in_executor(None, self._sync_download, request, local_path)
            logger.info(f"✅ Download de '{file_name}' concluído com sucesso.")
            return True

        try:
            return await self._retry_operation(_download)
        except Exception as e:
            logger.error(f"❌ Erro ao baixar '{file_name}' do Drive: {e}")
            return False
    
    def _sync_download(self, request, local_path):
        """Execução síncrona do download"""
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
    
    async def upload_file(self, local_path: str, file_name: str, folder_id: str) -> bool:
        """Faz upload de um arquivo para o Google Drive"""
        if not self.service:
            return False

        async def _upload():
            file_id = await self.get_file_id(file_name, folder_id)
            loop = asyncio.get_event_loop()
            
            media = MediaFileUpload(local_path, mimetype='application/json', resumable=True)

            if file_id:
                logger.info(f"⬆️ Atualizando backup no Google Drive...")
                await loop.run_in_executor(None,
                    lambda: self.service.files().update(
                        fileId=file_id,
                        media_body=media,
                        supportsAllDrives=True
                    ).execute()
                )
            else:
                logger.info("⬆️ Criando novo backup no Google Drive...")
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                await loop.run_in_executor(None,
                    lambda: self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        supportsAllDrives=True
                    ).execute()
                )

            # Invalidar cache para forçar nova busca
            cache_key = f"{file_name}:{folder_id}"
            self._cache.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
            
            logger.info("✅ Backup concluído com sucesso.")
            return True

        try:
            return await self._retry_operation(_upload)
        except Exception as e:
            logger.error(f"❌ Erro ao fazer upload: {e}")
            return False

class DataManager:
    """
    Gerencia o carregamento, salvamento e backup dos dados do bot.
    Implementa padrão Singleton para garantir uma única instância.
    """
    
    _instance: Optional['DataManager'] = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls, filepath: str = "data/streamers.json") -> "DataManager":
        """
        Método principal para obter a instância do DataManager.
        Garante inicialização correta e padrão Singleton.
        """
        if cls._instance is None or not cls._initialized:
            instance = cls(filepath)
            await instance._initialize()
            cls._initialized = True
        return cls._instance

    def __init__(self, filepath: str):
        """Construtor privado. Use get_instance() para obter uma instância."""
        if hasattr(self, '_filepath'):  # Evita re-inicialização
            return
            
        self._filepath = filepath
        self._data: Optional[Dict[str, Any]] = None
        self._drive_manager = GoogleDriveManager()
        self._metrics = DataManagerMetrics()
        self._lock = asyncio.Lock()  # Para operações thread-safe

    async def _initialize(self):
        """Inicialização assíncrona dos dados"""
        if self._data is None:
            await self._load_data()

    def _ensure_initialized(self):
        """Garante que o DataManager foi inicializado corretamente"""
        if self._data is None:
            raise RuntimeError(
                "DataManager não foi inicializado. "
                "Use 'await DataManager.get_instance()' ao invés do construtor direto."
            )

    def _validate_data_structure(self, data: Dict[str, Any]) -> bool:
        """Valida a estrutura básica dos dados"""
        required_keys = ["guilds", "metadata"]
        if not all(key in data for key in required_keys):
            return False
        
        if not isinstance(data["guilds"], dict):
            return False
        
        if not isinstance(data["metadata"], dict):
            return False
            
        return True

    async def _load_data(self) -> None:
        """Carrega os dados com validação e fallbacks robustos"""
        self._metrics.log_load()
        
        # Tentar carregar arquivo local primeiro
        if os.path.exists(self._filepath):
            try:
                if USE_AIOFILES:
                    async with aiofiles.open(self._filepath, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
                else:
                    with open(self._filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                if self._validate_data_structure(data):
                    self._data = data
                    logger.info("✅ Dados carregados do arquivo local.")
                    return
                else:
                    logger.warning("⚠️ Estrutura de dados local inválida.")

            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"❌ Erro ao carregar arquivo local: {e}")
                self._metrics.log_error("local_load")

        # Tentar baixar do Google Drive
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if drive_folder_id:
            if await self._drive_manager.download_file(
                os.path.basename(self._filepath), 
                drive_folder_id, 
                self._filepath
            ):
                try:
                    if USE_AIOFILES:
                        async with aiofiles.open(self._filepath, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            data = json.loads(content)
                    else:
                        with open(self._filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                    if self._validate_data_structure(data):
                        self._data = data
                        logger.info("✅ Dados carregados do Google Drive.")
                        return

                except Exception as e:
                    logger.error(f"❌ Erro ao processar arquivo do Drive: {e}")
                    self._metrics.log_error("drive_load")

        # Criar nova estrutura se tudo falhar
        self._create_default_data()
        await self.save_data()

    def _create_default_data(self):
        """Cria estrutura de dados padrão"""
        self._data = {
            "guilds": {},
            "metadata": {
                "version": "4.1",
                "created_at": datetime.now().isoformat(),
                "last_synced": None,
                "total_saves": 0
            }
        }
        logger.info("🆕 Criada nova estrutura de dados.")

    @asynccontextmanager
    async def transaction(self):
        """Context manager para operações transacionais"""
        async with self._lock:
            self._ensure_initialized()
            backup_data = copy.deepcopy(self._data)
            try:
                yield self
                await self.save_data()
            except Exception as e:
                logger.error(f"❌ Erro na transação, revertendo: {e}")
                self._data = backup_data
                self._metrics.log_error("transaction")
                raise

    async def save_data(self) -> None:
        """Salva os dados localmente e faz backup no Drive"""
        async with self._lock:
            self._ensure_initialized()
            
            try:
                # Atualizar metadata
                self._data["metadata"]["last_synced"] = datetime.now().isoformat()
                self._data["metadata"]["total_saves"] = self._data["metadata"].get("total_saves", 0) + 1
                
                # Salvar localmente
                if USE_AIOFILES:
                    async with aiofiles.open(self._filepath, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(self._data, indent=2, ensure_ascii=False))
                else:
                    with open(self._filepath, 'w', encoding='utf-8') as f:
                        json.dump(self._data, f, indent=2, ensure_ascii=False)
                
                logger.info("✅ Dados salvos localmente.")
                self._metrics.log_save()
                
                # Backup no Drive
                drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
                if drive_folder_id and self._drive_manager.service:
                    success = await self._drive_manager.upload_file(
                        self._filepath,
                        os.path.basename(self._filepath),
                        drive_folder_id
                    )
                    if success:
                        self._metrics.drive_uploads += 1
                else:
                    logger.warning("⚠️ Backup no Drive não configurado.")

            except Exception as e:
                logger.error(f"❌ Erro ao salvar dados: {e}")
                self._metrics.log_error("save")
                raise

    @property
    def data(self) -> Dict[str, Any]:
        """Propriedade somente leitura para acessar os dados"""
        self._ensure_initialized()
        return self._data

    @property
    def metrics(self) -> DataManagerMetrics:
        """Acesso às métricas do sistema"""
        return self._metrics

    def get_guild_data(self, guild_id: int) -> Dict[str, Any]:
        """Retorna os dados da guilda, criando estrutura padrão se necessário"""
        self._ensure_initialized()
        
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data["guilds"]:
            self._data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "users": {},
                "config": {
                    "notify_channel": None
                },
                "created_at": datetime.now().isoformat()
            }
        return self._data["guilds"][guild_id_str]

    async def link_user_channel(self, guild_id: int, user_id: int, platform: str, channel_id: str) -> bool:
        """Vincula um canal de usuário com validação de dados"""
        try:
            async with self.transaction():
                guild_data = self.get_guild_data(guild_id)
                user_id_str = str(user_id)
                
                # Validar e sanitizar dados
                platform = platform.lower().strip()
                channel_id = channel_id.lower().strip()
                
                if not platform or not channel_id:
                    raise ValueError("Platform e channel_id não podem estar vazios")
                
                if user_id_str not in guild_data["users"]:
                    guild_data["users"][user_id_str] = {}
                
                guild_data["users"][user_id_str][platform] = channel_id
                logger.info(f"✅ Usuário {user_id} vinculado ao canal {channel_id} na plataforma {platform}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao vincular canal: {e}")
            self._metrics.log_error("link_user")
            return False

    async def remove_user_platform(self, guild_id: int, user_id: int, platform: str) -> bool:
        """Remove plataforma de um usuário"""
        try:
            async with self.transaction():
                guild_data = self.get_guild_data(guild_id)
                user_id_str = str(user_id)
                platform = platform.lower().strip()
                
                if (user_id_str in guild_data["users"] and 
                    platform in guild_data["users"][user_id_str]):
                    del guild_data["users"][user_id_str][platform]
                    logger.info(f"✅ Plataforma {platform} removida do usuário {user_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao remover plataforma: {e}")
            self._metrics.log_error("remove_platform")
            return False

    async def cleanup_empty_guilds(self) -> int:
        """Remove guildas vazias dos dados"""
        self._ensure_initialized()
        removed_count = 0
        
        guilds_to_remove = []
        for guild_id, guild_data in self._data["guilds"].items():
            if not guild_data.get("users") and not guild_data.get("live_role_id"):
                guilds_to_remove.append(guild_id)
        
        for guild_id in guilds_to_remove:
            del self._data["guilds"][guild_id]
            removed_count += 1
        
        if removed_count > 0:
            await self.save_data()
            logger.info(f"🧹 Removidas {removed_count} guildas vazias")
        
        return removed_count
