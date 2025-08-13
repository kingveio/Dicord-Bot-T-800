from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class UserPlatform:
    username: str
    last_checked: Optional[datetime] = None
    is_live: bool = False
    last_live_title: Optional[str] = None

@dataclass
class UserData:
    discord_id: int
    twitch: Optional[UserPlatform] = None
    youtube: Optional[UserPlatform] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        data = {
            "discord_id": self.discord_id,
            "created_at": self.created_at.isoformat()
        }
        if self.twitch:
            data["twitch"] = {
                "username": self.twitch.username,
                "last_checked": self.twitch.last_checked.isoformat() if self.twitch.last_checked else None,
                "is_live": self.twitch.is_live,
                "last_live_title": self.twitch.last_live_title
            }
        if self.youtube:
            data["youtube"] = {
                "username": self.youtube.username,
                "last_checked": self.youtube.last_checked.isoformat() if self.youtube.last_checked else None,
                "is_live": self.youtube.is_live,
                "last_live_title": self.youtube.last_live_title
            }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserData":
        twitch = data.get("twitch")
        youtube = data.get("youtube")
        
        return cls(
            discord_id=data["discord_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            twitch=UserPlatform(
                username=twitch["username"],
                last_checked=datetime.fromisoformat(twitch["last_checked"]) if twitch and twitch.get("last_checked") else None,
                is_live=twitch.get("is_live", False) if twitch else False,
                last_live_title=twitch.get("last_live_title") if twitch else None
            ) if twitch else None,
            youtube=UserPlatform(
                username=youtube["username"],
                last_checked=datetime.fromisoformat(youtube["last_checked"]) if youtube and youtube.get("last_checked") else None,
                is_live=youtube.get("is_live", False) if youtube else False,
                last_live_title=youtube.get("last_live_title") if youtube else None
            ) if youtube else None
        )

@dataclass
class GuildConfig:
    live_role_id: Optional[int] = None
    notify_channel_id: Optional[int] = None
    backup_enabled: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "live_role_id": self.live_role_id,
            "notify_channel_id": self.notify_channel_id,
            "backup_enabled": self.backup_enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GuildConfig":
        return cls(
            live_role_id=data.get("live_role_id"),
            notify_channel_id=data.get("notify_channel_id"),
            backup_enabled=data.get("backup_enabled", True)
        )

@dataclass
class GuildData:
    guild_id: int
    config: GuildConfig = field(default_factory=GuildConfig)
    users: Dict[int, UserData] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "guild_id": self.guild_id,
            "config": self.config.to_dict(),
            "users": {str(k): v.to_dict() for k, v in self.users.items()},
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GuildData":
        return cls(
            guild_id=data["guild_id"],
            config=GuildConfig.from_dict(data["config"]),
            users={int(k): UserData.from_dict(v) for k, v in data["users"].items()},
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None
        )
