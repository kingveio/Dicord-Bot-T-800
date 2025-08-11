# data_manager.py
# ...
# Estrutura de dados global
DATA_CACHE: Dict[str, Any] = {
    "streamers": {},
    "monitored_users": {
        "twitch": {},
        "youtube": {}  # <-- Adicione esta linha
    }
}
# ...

async def load_data_from_drive_if_exists(drive_service: Optional[GoogleDriveService] = None) -> None:
    # ...
    # Altere esta parte para garantir que 'youtube' seja adicionado se não existir
    async with DATA_LOCK:
        if "youtube" not in DATA_CACHE["monitored_users"]:
             DATA_CACHE["monitored_users"]["youtube"] = {}
        # ...

    logger.info("Nova estrutura de dados criada")

    except Exception as e:
        logger.critical(f"Falha crítica ao carregar dados: {e}")
        raise
# ...
