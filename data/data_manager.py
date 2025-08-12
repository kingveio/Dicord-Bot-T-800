# T-800: Módulo de memória. Gerenciando dados de usuários.
# Este é um exemplo simples. Você pode adaptá-lo para usar o Google Drive.
import json
import os

class DataManager:
    def __init__(self, filepath="data/data.json"):
        self.filepath = filepath
        self.data = self._load_data()

    def _load_data(self):
        # Carregando dados da memória. Se não existirem, inicializa uma nova.
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)
        return {"users": {}}

    def _save_data(self):
        # Salvando dados na memória.
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def add_user(self, user_id: int, twitch_name: str | None = None, youtube_name: str | None = None):
        # Adicionando um novo "alvo" (usuário) na lista de monitoramento.
        self.data["users"][str(user_id)] = {
            "twitch": twitch_name,
            "youtube": youtube_name
        }
        self._save_data()

    def get_users(self):
        # Obtendo a lista de todos os usuários para monitoramento.
        return self.data["users"]
