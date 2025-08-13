import json
import os
from typing import Dict, Optional
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class DataManager:
    def __init__(self, filepath: str = "data/streamers.json"):
        """Inicializa o gerenciador de dados com tratamento robusto"""
        self.filepath = filepath
        self.backup_dir = "data/backups"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self.data = self._initialize_data()

    def _initialize_data(self) -> Dict:
        """Carrega ou cria o arquivo de dados com estrutura padrão"""
        default_structure = {
            "guilds": {},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "2.0"
            }
        }

        if not os.path.exists(self.filepath):
            self._save_data(default_structure)
            return default_structure

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Migração para estrutura v2.0 se necessário
                if "metadata" not in data:
                    data["metadata"] = default_structure["metadata"]
                    self._save_data(data)
                
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Erro ao carregar dados, criando novo: {e}")
            self._create_backup("corrupted")
            self._save_data(default_structure)
            return default_structure

    def _save_data(self, data: Optional[Dict] = None) -> None:
        """Salva os dados com tratamento de erros e backup automático"""
        data_to_save = data or self.data
        data_to_save["metadata"]["last_updated"] = datetime.now().isoformat()

        try:
            # Cria backup antes de salvar
            self._create_backup("pre_save")
            
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"❌ Falha crítica ao salvar dados: {e}")
            raise

    def _create_backup(self, reason: str = "manual") -> str:
        """Cria um backup local com timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/streamers_{timestamp}_{reason}.json"
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as source:
                with open(backup_path, 'w', encoding='utf-8') as target:
                    json.dump(json.load(source), target, indent=4)
            return backup_path
        except Exception as e:
            print(f"⚠️ Falha ao criar backup: {e}")
            return ""

    # --- Métodos Principais ---
    def get_guild_data(self, guild_id: int) -> Dict:
        """Obtém ou cria dados de um servidor"""
        guild_id_str = str(guild_id)
        
        if guild_id_str not in self.data["guilds"]:
            self.data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "users": {},
                "config": {
                    "notify_channel": None,
                    "cooldown_minutes": 5
                }
            }
            self._save_data()
        
        return self.data["guilds"][guild_id_str]

    def set_live_role_id(self, guild_id: int, role_id: int) -> None:
        """Define o cargo de live para um servidor"""
        guild_data = self.get_guild_data(guild_id)
        guild_data["live_role_id"] = str(role_id)
        self._save_data()

    def add_user(
        self,
        guild_id: int,
        user_id: int,
        twitch_name: Optional[str] = None,
        youtube_name: Optional[str] = None
    ) -> bool:
        """Adiciona/atualiza um streamer"""
        guild_data = self.get_guild_data(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str not in guild_data["users"]:
            guild_data["users"][user_id_str] = {}

        updated = False
        if twitch_name:
            guild_data["users"][user_id_str]["twitch"] = twitch_name.lower().strip()
            updated = True
        if youtube_name:
            guild_data["users"][user_id_str]["youtube"] = youtube_name.lower().strip()
            updated = True

        if updated:
            self._save_data()
        return updated

    def remove_user_platform(
        self,
        guild_id: int,
        user_id: int,
        platform: str
    ) -> bool:
        """Remove uma plataforma de um usuário"""
        guild_data = self.get_guild_data(guild_id)
        user_id_str = str(user_id)
        
        if (user_id_str in guild_data["users"] and 
            platform in guild_data["users"][user_id_str]):
            del guild_data["users"][user_id_str][platform]
            
            # Remove usuário se não tiver mais plataformas
            if not guild_data["users"][user_id_str]:
                del guild_data["users"][user_id_str]
            
            self._save_data()
            return True
        
        return False

    # --- Backup no Google Drive ---
    def backup_to_drive(self, credentials_path: str = "credentials.json") -> bool:
        """Envia backup para o Google Drive"""
        try:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            service = build('drive', 'v3', credentials=creds)
            
            backup_path = self._create_backup("drive_upload")
            if not backup_path:
                return False

            file_metadata = {
                'name': f"streamers_backup_{datetime.now().strftime('%Y%m%d')}.json",
                'parents': ['1XyZ...']  # ID da pasta no Drive
            }
            
            media = MediaFileUpload(
                backup_path,
                mimetype='application/json'
            )
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"✅ Backup enviado para o Drive (ID: {file.get('id')})")
            return True
            
        except Exception as e:
            print(f"❌ Falha no backup no Drive: {e}")
            return False

    # --- Métodos de Consulta ---
    def get_user_platforms(
        self,
        guild_id: int,
        user_id: int
    ) -> Dict[str, str]:
        """Retorna todas as plataformas de um usuário"""
        guild_data = self.get_guild_data(guild_id)
        user_id_str = str(user_id)
        return guild_data["users"].get(user_id_str, {}).copy()

    def get_all_streamers(self, guild_id: int) -> Dict:
        """Retorna todos os streamers de um servidor"""
        return self.get_guild_data(guild_id)["users"].copy()
