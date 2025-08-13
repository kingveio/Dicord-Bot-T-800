import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """Configura o sistema de logging global"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Formato padrão
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler (se especificado)
    if log_file:
        log_file.parent.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configuração básica
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado"""
    logger = logging.getLogger(name)
    logger.propagate = True  # Permite que os logs sejam tratados pelos handlers root
    return logger
