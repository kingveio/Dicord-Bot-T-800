from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class UserPlatform:
    username: str
    last_live_check: Optional[datetime] = None
    is_live: bool = False

@dataclass
class UserData:
    discord_id: int
    twitch: Optional[UserPlatform] = None
    youtube: Optional[UserPlatform] = None

@dataclass
class GuildConfig:
    live_role_id: Optional[int] = None
    notify_channel_id: Optional[int] = None
    backup_enabled: bool = True

@dataclass
class GuildData:
    guild_id: int
    config: GuildConfig = field(default_factory=GuildConfig)
    users: Dict[int, UserData] = field(default_factory=dict)
