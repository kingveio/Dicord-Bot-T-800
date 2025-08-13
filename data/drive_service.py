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

# A classe DataManager foi ajustada para ter uma função de backup funcional para o Google Drive pessoal.
class DataManager:
    """
    Gerencia os dados de streamers e configurações de guildas para um bot do Discord,
    incluindo a funcionalidade de backup para o Google Drive.
    """
    def __init__(self, filepath: str = "data/streamers.json"):
        """
        Inicializa o gerenciador de dados, configurando diretórios e o Google Drive.
        """
        self.filepath = filepath
        self.backup_dir = "data/backups"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Tenta configurar as credenciais do Google Drive a partir de uma variável de ambiente.
        self._setup_google_drive()
        
        # Carrega ou inicializa os dados.
        self.data = self._load_or_initialize_data()

    def _setup_google_drive(self):
        """
        Decodifica as credenciais da conta de serviço do Google Drive de uma
        variável de ambiente Base64 e salva-as em um arquivo local.
        """
        print("🔧 Configurando credenciais do Google Drive...")
        creds_base64 = os.getenv('GOOGLE_CREDENTIALS')
        if not creds_base64:
            print("⚠️ Variável de ambiente 'GOOGLE_CREDENTIALS' não encontrada.")
            return

        try:
            # Tenta decodificar a string Base64.
            decoded = base64.b64decode(creds_base64)
            with open("credentials.json", "wb") as f:
                f.write(decoded)
            print("✅ Credenciais do Google Drive configuradas com sucesso.")
        except (binascii.Error, ValueError) as e:
            print(f"❌ Erro ao decodificar as credenciais Base64: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado ao configurar Google Drive: {e}")

    def _load_or_initialize_data(self) -> Dict:
        """
        Carrega o arquivo de dados JSON ou cria um novo com a estrutura padrão.
        """
        default_data = {
            "guilds": {},
            "metadata": {
                "version": "3.0",
                "created_at": datetime.now().isoformat(),
                "last_backup": None
            }
        }
        
        if not os.path.exists(self.filepath):
            self._save_data(default_data)
            return default_data

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "metadata" not in data:
                    data["metadata"] = default_data["metadata"]
                    self._save_data(data)
                return data
        except json.JSONDecodeError as e:
            print(f"⚠️ Erro ao carregar dados (JSON inválido): {e}")
            self._create_backup("corrupted")
            self._save_data(default_data)
            return default_data
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados: {e}")
            self._create_backup("corrupted")
            self._save_data(default_data)
            return default_data

    def _save_data(self, data: Optional[dict] = None):
        """
        Salva os dados no arquivo JSON.
        """
        save_data = data if data is not None else self.data
        
        if not isinstance(save_data, dict):
            raise ValueError("Dados devem ser um dicionário")
        
        save_data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar dados: {e}")
            raise

    def _create_backup(self, reason: str) -> str:
        """
        Cria um backup local com timestamp.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/backup_{timestamp}_{reason}.json"
        try:
            with open(self.filepath, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
                json.dump(json.load(src), dst, indent=4, ensure_ascii=False)
            return backup_path
        except Exception as e:
            print(f"⚠️ Falha ao criar backup local: {e}")
            return ""

    def backup_to_drive(self) -> Dict:
        """
        Faz upload do arquivo de dados para um Google Drive pessoal usando
        uma conta de serviço com acesso a uma pasta compartilhada.
        """
        result = {"success": False, "error": None, "file_name": None, "file_url": None}

        # Verificação inicial de credenciais e variáveis de ambiente
        if not os.path.exists("credentials.json"):
            result["error"] = "Arquivo de credenciais não encontrado."
            print("❌ Erro: credentials.json não existe.")
            return result
        
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        
        if not drive_folder_id:
            result["error"] = "Variável de ambiente DRIVE_FOLDER_ID não está definida."
            print("❌ Erro: DRIVE_FOLDER_ID faltando.")
            return result
        
        try:
            # 1. Configuração do serviço com o escopo correto
            creds = service_account.Credentials.from_service_account_file(
                "credentials.json",
                scopes=['https://www.googleapis.com/auth/drive'], # Escopo mais amplo e necessário
            )
            service = build('drive', 'v3', credentials=creds)

            # 2. Upload para o Drive pessoal
            print("⬆️ Iniciando upload do backup para o Google Drive pessoal...")
            print(f"    > Usando Folder ID: {drive_folder_id}")
            
            file_name = f"backup_{datetime.now().strftime('%Y-%m-%d')}.json"
            file_metadata = {
                'name': file_name,
                'parents': [drive_folder_id],
            }
            
            media = MediaFileUpload(
                self.filepath,
                mimetype='application/json',
                resumable=True
            )
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # Atualiza os metadados e o resultado
            result["success"] = True
            result["file_id"] = file.get('id')
            result["file_name"] = file_name
            result["file_url"] = file.get('webViewLink')
            self.data["metadata"]["last_backup"] = datetime.now().isoformat()
            self._save_data() # Atualiza o metadado no arquivo local.
            print(f"✅ Backup enviado com sucesso! ID do arquivo: {file.get('id')}")
            
        except HttpError as e:
            # Aprimoramento para capturar a mensagem de erro específica do Google.
            try:
                error_content = json.loads(e.content.decode('utf-8'))
                error_msg = f"Erro HTTP {e.resp.status}: {error_content.get('error', {}).get('message', 'Mensagem de erro não disponível.')}"
            except (json.JSONDecodeError, AttributeError):
                error_msg = f"Erro HTTP {e.resp.status}: {e.reason}"

            result["error"] = error_msg
            print(f"❌ Erro HTTP ao fazer backup: {error_msg}")
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Erro inesperado ao fazer backup: {e}")
        
        return result

    def get_guild_data(self, guild_id: int) -> Dict:
        """
        Retorna os dados de uma guilda específica, criando-os se não existirem.
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
            self._save_data()
        return self.data["guilds"][guild_id_str]

    def link_user_channel(
        self,
        guild: discord.Guild,
        user: Union[discord.Member, discord.User],
        platform: str,
        channel_id: str
    ) -> bool:
        """
        Vincula um canal de uma plataforma (Twitch/YouTube) a um usuário em uma guilda.
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
            self._save_data()
            
            if guild_data["config"]["backup_enabled"]:
                self.backup_to_drive()
                
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
        Remove um canal de uma plataforma de um usuário.
        """
        try:
            guild_data = self.get_guild_data(guild_id)
            user_id_str = str(user_id)
            
            if user_id_str in guild_data["users"] and platform in guild_data["users"][user_id_str]:
                del guild_data["users"][user_id_str][platform]
                
                # Se o usuário não tiver mais plataformas vinculadas, remove-o completamente.
                if not any(key in guild_data["users"][user_id_str] for key in ["twitch", "youtube"]):
                    del guild_data["users"][user_id_str]
                
                self._save_data()
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
