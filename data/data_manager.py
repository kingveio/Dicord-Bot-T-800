# data/data_manager.py
# T-800: Módulo de armazenamento. Gerenciando dados na nuvem.
import os
import json
import base64
import binascii
from datetime import datetime
from typing import Dict, Optional, Union
import discord
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from io import BytesIO

class DataManager:
    """
    Gerencia os dados de streamers e configurações de guildas para um bot do Discord.
    Nesta versão, o Google Drive é a fonte de dados primária, e os dados
    são lidos e salvos na nuvem.
    """
    def __init__(self, filepath: str = "data/streamers.json"):
        """
        Inicializa o gerenciador de dados, configurando diretórios e o Google Drive.
        """
        self.filepath = filepath
        self.drive_service = None
        self.streamers_file_id = None
        
        # Garante que o diretório de dados exista para o cache local
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Configura o serviço do Google Drive e carrega os dados
        self._setup_google_drive()
        if self.drive_service:
            self.data = self._load_data_from_drive()
        else:
            self.data = {} # Dados vazios se o Drive não puder ser acessado

    def _setup_google_drive(self):
        """
        Decodifica as credenciais da conta de serviço do Google Drive de uma
        variável de ambiente Base64 e configura o serviço da API.
        """
        print("🔧 Configurando credenciais e serviço do Google Drive...")
        creds_base64 = os.getenv('GOOGLE_CREDENTIALS')
        if not creds_base64:
            print("⚠️ Variável de ambiente 'GOOGLE_CREDENTIALS' não encontrada.")
            return

        try:
            decoded = base64.b64decode(creds_base64)
            creds_info = json.loads(decoded.decode('utf-8'))
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            self.drive_service = build('drive', 'v3', credentials=creds)
            print("✅ Serviço do Google Drive configurado com sucesso.")
        except Exception as e:
            print(f"❌ Erro ao configurar Google Drive: {e}")

    def _find_streamers_file(self) -> Optional[str]:
        """
        Procura pelo arquivo 'streamers.json' na pasta do Google Drive.
        Retorna o ID do arquivo se encontrado, senão retorna None.
        """
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if not drive_folder_id:
            print("❌ Erro: DRIVE_FOLDER_ID faltando para encontrar o arquivo.")
            return None

        try:
            # Busca pelo arquivo 'streamers.json' dentro da pasta especificada
            query = f"name='streamers.json' and mimeType='application/json' and '{drive_folder_id}' in parents and trashed=false"
            response = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = response.get('files', [])
            if files:
                print(f"🔎 Arquivo 'streamers.json' encontrado com ID: {files[0]['id']}")
                return files[0]['id']
            else:
                print("⚠️ Arquivo 'streamers.json' não encontrado no Google Drive. Um novo será criado.")
                return None
        except HttpError as e:
            print(f"❌ Erro HTTP ao buscar arquivo: {e}")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado ao buscar arquivo: {e}")
            return None
            
    def _create_streamers_file(self, default_data: Dict) -> Optional[str]:
        """
        Cria um novo arquivo 'streamers.json' com os dados padrão no Google Drive.
        Retorna o ID do novo arquivo se a criação for bem-sucedida.
        """
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if not drive_folder_id:
            print("❌ Erro: DRIVE_FOLDER_ID faltando para criar o arquivo.")
            return None

        try:
            file_metadata = {
                'name': 'streamers.json',
                'parents': [drive_folder_id],
                'mimeType': 'application/json'
            }
            
            media = MediaFileUpload(
                BytesIO(json.dumps(default_data, indent=4).encode('utf-8')),
                mimetype='application/json',
                resumable=True
            )
            
            new_file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            print(f"✅ Novo arquivo 'streamers.json' criado no Google Drive. ID: {new_file['id']}")
            return new_file['id']
        except HttpError as e:
            print(f"❌ Erro HTTP ao criar arquivo: {e}")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado ao criar arquivo: {e}")
            return None

    def _load_data_from_drive(self) -> Dict:
        """
        Tenta carregar os dados do Google Drive. Se o arquivo não existe,
        cria um novo e retorna os dados padrão.
        """
        self.streamers_file_id = self._find_streamers_file()
        default_data = {
            "guilds": {},
            "metadata": {
                "version": "4.0",
                "created_at": datetime.now().isoformat(),
                "last_synced": None
            }
        }
        
        if self.streamers_file_id:
            try:
                print("⬇️ Baixando dados do Google Drive...")
                request = self.drive_service.files().get_media(
                    fileId=self.streamers_file_id,
                    supportsAllDrives=True
                )
                
                # Usa BytesIO para lidar com o conteúdo binário
                file_content = BytesIO(request.execute())
                data = json.load(file_content)
                print("✅ Dados baixados e carregados com sucesso.")
                
                data["metadata"]["last_synced"] = datetime.now().isoformat()
                self._save_data_locally(data) # Salva uma cópia local para uso temporário
                return data

            except HttpError as e:
                print(f"❌ Erro HTTP ao baixar arquivo: {e}")
                self.streamers_file_id = self._create_streamers_file(default_data)
                self._save_data_locally(default_data)
                return default_data
            except json.JSONDecodeError as e:
                print(f"⚠️ Erro ao decodificar JSON do arquivo do Drive. Criando novo arquivo. Detalhe: {e}")
                self.streamers_file_id = self._create_streamers_file(default_data)
                self._save_data_locally(default_data)
                return default_data
            except Exception as e:
                print(f"❌ Erro inesperado ao carregar dados do Drive: {e}")
                self.streamers_file_id = self._create_streamers_file(default_data)
                self._save_data_locally(default_data)
                return default_data
        else:
            print("🆕 Arquivo não encontrado no Drive. Criando novo.")
            self.streamers_file_id = self._create_streamers_file(default_data)
            self._save_data_locally(default_data)
            return default_data
            
    def _save_data_locally(self, data: Dict):
        """
        Salva os dados no arquivo JSON localmente como cache.
        """
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar dados localmente: {e}")
            
    def _upload_data_to_drive(self, data: Dict):
        """
        Atualiza o arquivo 'streamers.json' existente no Google Drive.
        """
        if not self.drive_service or not self.streamers_file_id:
            print("⚠️ Serviço do Drive ou ID do arquivo ausente. Upload ignorado.")
            return

        try:
            print("⬆️ Sincronizando dados com o Google Drive...")
            media = MediaFileUpload(
                BytesIO(json.dumps(data, indent=4).encode('utf-8')),
                mimetype='application/json',
                resumable=True
            )
            
            self.drive_service.files().update(
                fileId=self.streamers_file_id,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            print(f"✅ Dados sincronizados com sucesso no Google Drive.")
            self.data["metadata"]["last_synced"] = datetime.now().isoformat()
            self._save_data_locally(self.data)
            
        except HttpError as e:
            print(f"❌ Erro HTTP ao sincronizar dados: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado ao sincronizar dados: {e}")
            
    def get_guild_data(self, guild_id: int) -> Dict:
        """
        Retorna os dados de uma guilda específica, criando-os se não existirem
        e sincronizando a alteração com o Google Drive.
        """
        guild_id_str = str(guild_id)
        if guild_id_str not in self.data["guilds"]:
            self.data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "users": {},
                "config": {
                    "notify_channel": None,
                    "backup_enabled": True
                }
            }
            self._upload_data_to_drive(self.data)
        return self.data["guilds"][guild_id_str]

    def link_user_channel(
        self,
        guild: discord.Guild,
        user: Union[discord.Member, discord.User],
        platform: str,
        channel_id: str
    ) -> bool:
        """
        Vincula um canal de uma plataforma a um usuário e sincroniza com o Drive.
        """
        try:
            guild_data = self.get_guild_data(guild.id)
            user_id_str = str(user.id)
            
            if user_id_str not in guild_data["users"]:
                guild_data["users"][user_id_str] = {
                    "discord_info": {
                        "name": user.name,
                        "display_name": user.display_name,
                        "avatar": str(user.avatar.url) if user.avatar else None
                    }
                }
            
            guild_data["users"][user_id_str][platform] = channel_id.lower().strip()
            self._upload_data_to_drive(self.data)
            return True
        except Exception as e:
            print(f"⚠️ Erro ao vincular canal: {e}")
            return False

    def remove_user_platform(
        self,
        guild_id: int,
        user_id: int,
        platform: str
    ) -> bool:
        """
        Remove um canal de uma plataforma de um usuário e sincroniza com o Drive.
        """
        try:
            guild_data = self.get_guild_data(guild_id)
            user_id_str = str(user_id)
            
            if user_id_str in guild_data["users"] and platform in guild_data["users"][user_id_str]:
                del guild_data["users"][user_id_str][platform]
                
                if not any(key in guild_data["users"][user_id_str] for key in ["twitch", "youtube"]):
                    del guild_data["users"][user_id_str]
                
                self._upload_data_to_drive(self.data)
                return True
            return False
        except KeyError as e:
            print(f"⚠️ Erro ao remover plataforma: {e}")
            return False

    def get_user_platforms(self, guild_id: int, user_id: int) -> Dict:
        """
        Retorna as plataformas vinculadas a um usuário específico.
        """
        try:
            guild_data = self.get_guild_data(guild_id)
            user_data = guild_data["users"].get(str(user_id), {})
            return {
                "twitch": user_data.get("twitch"),
                "youtube": user_data.get("youtube")
            }
        except Exception as e:
            print(f"⚠️ Erro ao obter plataformas: {e}")
            return {"twitch": None, "youtube": None}
