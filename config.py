import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Config:
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN")
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET")
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY")
    GOOGLE_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_CREDENTIALS")
    DRIVE_FOLDER_ID: Optional[str] = os.getenv("DRIVE_FOLDER_ID")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RENDER_SERVICE_NAME: Optional[str] = os.getenv("RENDER_SERVICE_NAME")
    SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", 10))
    @classmethod
    def validate(cls):
        required = [
            ("DISCORD_TOKEN", cls.DISCORD_TOKEN),
            ("TWITCH_CLIENT_ID", cls.TWITCH_CLIENT_ID),
            ("TWITCH_CLIENT_SECRET", cls.TWITCH_CLIENT_SECRET),
            ("YOUTUBE_API_KEY", cls.YOUTUBE_API_KEY)
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    @classmethod
    def is_render(cls) -> bool:
        return "RENDER" in os.environ
