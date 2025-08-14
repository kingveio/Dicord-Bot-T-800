import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Config:
    # Configurações obrigatórias
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN")
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET")
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY")
    
    # Intervalos de verificação
    LIVE_CHECK_INTERVAL_MINUTES: int = int(os.getenv("LIVE_CHECK_INTERVAL_MINUTES", "5"))

    # Configurações opcionais
    RENDER_SERVICE_NAME: Optional[str] = os.getenv("RENDER_SERVICE_NAME")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DRIVE_FOLDER_ID: Optional[str] = os.getenv("DRIVE_FOLDER_ID")
    GOOGLE_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_CREDENTIALS")

    @classmethod
    def validate(cls):
        """Valida as configurações obrigatórias"""
        required_vars = [
            ("DISCORD_TOKEN", cls.DISCORD_TOKEN),
            ("TWITCH_CLIENT_ID", cls.TWITCH_CLIENT_ID),
            ("TWITCH_CLIENT_SECRET", cls.TWITCH_CLIENT_SECRET),
            ("YOUTUBE_API_KEY", cls.YOUTUBE_API_KEY)
        ]
        
        missing = [name for name, value in required_vars if not value]
        if missing:
            raise ValueError(f"Variáveis de ambiente ausentes: {', '.join(missing)}")

    @classmethod
    def is_render(cls) -> bool:
        """Verifica se está rodando no Render"""
        return "RENDER" in os.environ
