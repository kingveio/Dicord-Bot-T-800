import os
import json
import base64
from datetime import datetime
from typing import Dict, Optional, Union
import discord
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from data.data_manager import DataManager

class DataManager:
    def __init__(self, filepath: str = "data/streamers.json"):
        """Inicializa o gerenciador de dados"""
        self.filepath = filepath
        self.backup_dir = "data/backups"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self._setup_google_drive()
        self.data = self._load_or_initialize_data()

    def _setup_google_drive(self):
        """Configura as credenciais do Google Drive"""
        try:
            creds_base64 = os.getenv('GOOGLE_CREDENTIALS')
            if creds_base64:
                with open("credentials.json", "wb") as f:
                    f.write(base64.b64decode(creds_base64))
        except Exception as e:
            print(f"⚠️ Erro ao configurar Google Drive: {e}")

    def _load_or_initialize_data(self) -> Dict:
        """Carrega ou cria o arquivo de dados com estrutura padrão"""
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
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados: {e}")
            self._create_backup("corrupted")
            self._save_data(default_data)
            return default_data

    def _save_data(self, data: Optional[dict] = None):
        """Salva os dados no arquivo JSON"""
        save_data = data if data is not None else self.data
        save_data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar dados: {e}")
            raise

    def _create_backup(self, reason: str) -> str:
        """Cria um backup local com timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/backup_{timestamp}_{reason}.json"
        try:
            with open(self.filepath, 'r') as src, open(backup_path, 'w') as dst:
                json.dump(json.load(src), dst, indent=4)
            return backup_path
        except Exception as e:
            print(f"⚠️ Falha ao criar backup: {e}")
            return ""

    def backup_to_drive(self) -> Dict:
        """Realiza backup completo para o Google Drive"""
        result = {
            "success": False,
            "file_id": None,
            "file_url": None,
            "timestamp": datetime.now().isoformat()
        }

        if not os.path.exists("credentials.json"):
            result["error"] = "Credenciais do Google Drive não encontradas"
            return result

        try:
            # 1. Criar backup local
            backup_path = self._create_backup("drive")
            if not backup_path:
                result["error"] = "Falha ao criar backup local"
                return result

            # 2. Configurar serviço do Google Drive
            creds = service_account.Credentials.from_service_account_file(
                "credentials.json",
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            service = build('drive', 'v3', credentials=creds)

            # 3. Upload do arquivo
            file_metadata = {
                'name': os.path.basename(backup_path),
                'parents': [os.getenv('DRIVE_FOLDER_ID')]
            }
            media = MediaFileUpload(backup_path, mimetype='application/json')
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink'
            ).execute()

            # 4. Atualizar status
            self.data["metadata"]["last_backup"] = result["timestamp"]
            self._save_data()

            result.update({
                "success": True,
                "file_id": file['id'],
                "file_url": file.get('webViewLink'),
                "file_name": file['name']
            })

        except HttpError as e:
            result["error"] = f"Erro do Google Drive: {e}"
        except Exception as e:
            result["error"] = f"Erro inesperado: {e}"

        return result

    # Métodos principais de gerenciamento de dados
    def get_guild_data(self, guild_id: int) -> Dict:
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
        
        # Backup automático após modificação importante
        if guild_data["config"]["backup_enabled"]:
            self.backup_to_drive()
            
        return True

    def remove_user_platform(
        self,
        guild_id: int,
        user_id: int,
        platform: str
    ) -> bool:
        guild_data = self.get_guild_data(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str in guild_data["users"] and platform in guild_data["users"][user_id_str]:
            del guild_data["users"][user_id_str][platform]
            
            # Remove user data if no platforms left
            if not guild_data["users"][user_id_str].get("twitch") and not guild_data["users"][user_id_str].get("youtube"):
                del guild_data["users"][user_id_str]
            
            self._save_data()
            return True
        return False

    def get_user_platforms(self, guild_id: int, user_id: int) -> Dict:
        guild_data = self.get_guild_data(guild_id)
        user_data = guild_data["users"].get(str(user_id), {})
        return {
            "twitch": user_data.get("twitch"),
            "youtube": user_data.get("youtube")
        }
