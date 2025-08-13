import discord
import json
import os
from typing import Dict, Optional, Union
from datetime import datetime

class DataManager:
    def __init__(self, filepath: str = "data/streamers.json"):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.data = self._load_or_initialize_data()

    def _load_or_initialize_data(self) -> Dict:
        default_data = {
            "guilds": {},
            "metadata": {
                "version": "2.1",
                "created_at": datetime.now().isoformat()
            }
        }
        
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Migração para nova estrutura se necessário
                    if "metadata" not in data:
                        data["metadata"] = default_data["metadata"]
                    return data
            return default_data
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados: {e}")
            return default_data

    def _save_data(self):
        self.data["metadata"]["last_updated"] = datetime.now().isoformat()
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # --- Vinculação Completa ---
    def link_user_channel(
        self,
        guild: discord.Guild,
        user: Union[discord.Member, discord.User],
        platform: str,
        channel_id: str
    ) -> bool:
        """Vincula um canal a um usuário com validação"""
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
        
        guild_data["users"][user_id_str][platform] = channel_id
        self._save_data()
        return True

    def get_linked_user(
        self,
        guild_id: int,
        platform: str,
        channel_id: str
    ) -> Optional[discord.User]:
        """Retorna o usuário do Discord vinculado a um canal"""
        guild_data = self.get_guild_data(guild_id)
        
        for user_id, data in guild_data["users"].items():
            if data.get(platform) == channel_id:
                return self.bot.get_user(int(user_id))
        return None

    # --- Métodos Aprimorados ---
    def get_user_platforms(
        self,
        guild_id: int,
        user: Union[discord.Member, discord.User]
    ) -> Dict:
        """Retorna todas as plataformas vinculadas com metadados"""
        guild_data = self.get_guild_data(guild_id)
        user_data = guild_data["users"].get(str(user.id), {})
        
        return {
            "twitch": user_data.get("twitch"),
            "youtube": user_data.get("youtube"),
            "discord": {
                "id": user.id,
                "name": user.name,
                "avatar": user.avatar.url if user.avatar else None
            }
        }

    def get_all_linked_users(
        self,
        guild: discord.Guild,
        platform: Optional[str] = None
    ) -> Dict:
        """Retorna todos os usuários vinculados com filtro por plataforma"""
        guild_data = self.get_guild_data(guild.id)
        result = {}
        
        for user_id, data in guild_data["users"].items():
            if not platform or platform in data:
                member = guild.get_member(int(user_id))
                if member:
                    result[user_id] = {
                        "user": member,
                        "platforms": {
                            "twitch": data.get("twitch"),
                            "youtube": data.get("youtube")
                        }
                    }
        return result

    # --- Gerenciamento de Cargos ---
    def update_live_role(
        self,
        guild: discord.Guild,
        role: discord.Role
    ) -> None:
        """Atualiza o cargo de live com metadados"""
        guild_data = self.get_guild_data(guild.id)
        guild_data["live_role_id"] = str(role.id)
        guild_data["live_role_info"] = {
            "name": role.name,
            "color": str(role.color),
            "created_at": role.created_at.isoformat()
        }
        self._save_data()

    # --- Backup Automático ---
    def create_backup(self) -> str:
        """Cria um backup com timestamp"""
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/backup_{timestamp}.json"
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)
            
        return backup_path

    def get_guild_data(self, guild_id: int) -> Dict:
        guild_id_str = str(guild_id)
        if guild_id_str not in self.data["guilds"]:
            self.data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "live_role_info": None,
                "users": {},
                "config": {
                    "notification_channel": None,
                    "cooldown": 5
                }
            }
            self._save_data()
        return self.data["guilds"][guild_id_str]
