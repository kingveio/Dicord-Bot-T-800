import json
import asyncio
import aiofiles
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from .models import GuildData, UserData, GuildConfig

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.bot = None  # Será definido pelo bot
        self.google_drive_service = None # Será definido pelo bot
        self.data_dir = Path("data")
        self.filepath = self.data_dir / "streamers.json"
        self._data: Dict[str, Any] = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "guilds": {}
        }
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        """
        Carrega dados do arquivo local.
        Se o arquivo não existir, tenta baixar o backup do Google Drive.
        """
        async with self._lock:
            self.data_dir.mkdir(exist_ok=True)
            
            # 1. Tenta carregar do arquivo local
            if self.filepath.exists():
                try:
                    async with aiofiles.open(self.filepath, "r", encoding="utf-8") as f:
                        self._data = json.loads(await f.read())
                    logger.info("✅ Dados carregados do arquivo local")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao carregar dados locais: {e}. Tentando backup...")
            else:
                logger.warning("⚠️ Arquivo local não encontrado. Tentando restaurar do backup...")

            # 2. Se o arquivo local falhar, tenta baixar do Google Drive
            if self.google_drive_service and self.google_drive_service.service:
                try:
                    success, message = await self.google_drive_service.download_file(
                        self.filepath.name, self.filepath.as_posix()
                    )
                    if success:
                        logger.info(f"✅ Backup restaurado: {message}")
                        # Após restaurar, tenta carregar novamente o arquivo
                        async with aiofiles.open(self.filepath, "r", encoding="utf-8") as f:
                            self._data = json.loads(await f.read())
                        return
                    else:
                        logger.warning(f"⚠️ Falha ao restaurar backup: {message}")
                except Exception as e:
                    logger.error(f"❌ Erro no processo de restauração do backup: {e}")

            # 3. Se tudo falhar, usa a estrutura de dados padrão
            self._data = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "guilds": {}
            }
            logger.info("ℹ️ Usando nova estrutura de dados padrão")

    async def save(self) -> None:
        """Salva os dados localmente e faz backup se o serviço estiver disponível"""
        async with self._lock:
            try:
                # Lógica de salvamento local (já existente)
                self._data["last_updated"] = datetime.now().isoformat()
                async with aiofiles.open(self.filepath, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(self._data, indent=2, ensure_ascii=False))
                
                logger.info("✅ Dados salvos com sucesso")
                
                # --- Lógica de backup ---
                if self.google_drive_service and self.google_drive_service.service:
                    success, message = await self.google_drive_service.upload_file(self.filepath)
                    if success:
                        logger.info(f"✅ Backup no Google Drive: {message}")
                    else:
                        logger.warning(f"⚠️ Falha no backup do Google Drive: {message}")
            except Exception as e:
                logger.error(f"❌ Falha ao salvar dados: {e}")
                raise

    def get_guild(self, guild_id: int) -> GuildData:
        """Retorna os dados de uma guilda ou cria uma nova entrada, retornando um objeto GuildData"""
        guild_id_str = str(guild_id)
        if guild_id_str not in self._data["guilds"]:
            self._data["guilds"][guild_id_str] = GuildData(guild_id).to_dict()
        
        return GuildData.from_dict(self._data["guilds"][guild_id_str])

    async def update_guild_config(self, guild_id: int, **kwargs) -> None:
        """Atualiza configurações específicas da guilda"""
        guild_data = self.get_guild(guild_id)
        for key, value in kwargs.items():
            if key in guild_data.config.__dict__:
                setattr(guild_data.config, key, value)
        self._data["guilds"][str(guild_id)] = guild_data.to_dict()
        await self.save()

    async def link_user_platform(self, guild_id: int, user_id: int, platform: str, username: str) -> bool:
        """Vincula uma plataforma a um usuário"""
        try:
            guild_data = self.get_guild(guild_id)
            if str(user_id) not in guild_data.users:
                guild_data.users[user_id] = UserData(discord_id=user_id)
            
            user_data = guild_data.users[user_id]
            
            if platform == "twitch":
                user_data.twitch = UserPlatform(username=username)
            elif platform == "youtube":
                user_data.youtube = UserPlatform(username=username)
            
            self._data["guilds"][str(guild_id)] = guild_data.to_dict()
            await self.save()
            return True
        except Exception as e:
            logger.error(f"Erro ao vincular plataforma: {e}")
            return False

    async def remove_account(self, guild_id: int, user_id: int, platform: Optional[str] = None) -> bool:
        """Remove a conta de uma plataforma ou todas as contas de um usuário"""
        guild_data = self.get_guild(guild_id)
        
        if user_id not in guild_data.users:
            return False

        if platform:
            user_data = guild_data.users[user_id]
            if platform == "twitch" and user_data.twitch:
                user_data.twitch = None
                self._data["guilds"][str(guild_id)] = guild_data.to_dict()
                await self.save()
                return True
            if platform == "youtube" and user_data.youtube:
                user_data.youtube = None
                self._data["guilds"][str(guild_id)] = guild_data.to_dict()
                await self.save()
                return True
        else:
            del guild_data.users[user_id]
            self._data["guilds"][str(guild_id)] = guild_data.to_dict()
            await self.save()
            return True

        return False
        
    async def cleanup_inactive_guilds(self, active_guild_ids: list) -> int:
        """Remove guildas inativas e retorna o número de removidas"""
        inactive = [gid for gid in self._data["guilds"] if int(gid) not in active_guild_ids]
        for gid in inactive:
            del self._data["guilds"][gid]
        
        if inactive:
            await self.save()
        
        return len(inactive)
