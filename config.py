import os
from dotenv import load_dotenv
from typing import Optional
import base64
import json

load_dotenv()

class Config:
    # Discord
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN")
    
    # Twitch
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET")
    
    # Google Drive (opcional)
    DRIVE_FOLDER_ID: Optional[str] = os.getenv("DRIVE_FOLDER_ID")
    GOOGLE_CREDENTIALS: Optional[dict] = None
    
    # Geral
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RENDER_SERVICE_NAME: Optional[str] = os.getenv("RENDER_SERVICE_NAME")

    @classmethod
    def validate(cls):
        required = [
            ("DISCORD_TOKEN", cls.DISCORD_TOKEN),
            ("TWITCH_CLIENT_ID", cls.TWITCH_CLIENT_ID),
            ("TWITCH_CLIENT_SECRET", cls.TWITCH_CLIENT_SECRET)
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Variáveis ausentes: {', '.join(missing)}")

        # Decodifica credenciais do Google se existirem
        if os.getenv("GOOGLE_CREDENTIALS"):
            try:
                decoded = base64.b64decode(os.getenv("GOOGLE_CREDENTIALS"))
                cls.GOOGLE_CREDENTIALS = json.loads(decoded.decode('utf-8'))
            except Exception as e:
                raise ValueError(f"Erro ao decodificar GOOGLE_CREDENTIALS: {e}")

    @classmethod
    def is_render(cls) -> bool:
        return "RENDER" in os.environ
