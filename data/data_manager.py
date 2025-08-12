# T-800: Módulo de memória. Gerenciando dados de usuários por servidor.
import json
import os

class DataManager:
    def __init__(self, filepath="data/data.json"):
        self.filepath = filepath
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)
        return {"guilds": {}}

    def _save_data(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def get_guild_data(self, guild_id: int):
        guild_id_str = str(guild_id)
        if guild_id_str not in self.data["guilds"]:
            self.data["guilds"][guild_id_str] = {
                "live_role_id": None,
                "users": {}
            }
            self._save_data()
        return self.data["guilds"][guild_id_str]

    def set_live_role_id(self, guild_id: int, role_id: int):
        guild_data = self.get_guild_data(guild_id)
        guild_data["live_role_id"] = role_id
        self._save_data()

    def add_user(self, guild_id: int, user_id: int, twitch_name: str | None = None, youtube_name: str | None = None):
        guild_data = self.get_guild_data(guild_id)
        user_id_str = str(user_id)
        if user_id_str not in guild_data["users"]:
            guild_data["users"][user_id_str] = {}
        
        if twitch_name:
            guild_data["users"][user_id_str]["twitch"] = twitch_name
        if youtube_name:
            guild_data["users"][user_id_str]["youtube"] = youtube_name
            
        self._save_data()
