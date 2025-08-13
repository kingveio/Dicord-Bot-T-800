import re
import discord
from datetime import timedelta
from typing import Optional, Union, Tuple, List  # Adicionando List aqui

async def send_embed(
    destination: Union[discord.abc.Messageable, discord.Interaction],
    title: str = "",
    description: str = "",
    color: Union[discord.Color, int] = discord.Color.blue(),
    **kwargs
) -> discord.Message:
    """Envia uma embed de forma consistente"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    
    # Tratamento para Interaction ou Messageable
    if isinstance(destination, discord.Interaction):
        if destination.response.is_done():
            return await destination.followup.send(embed=embed, **kwargs)
        else:
            await destination.response.send_message(embed=embed, **kwargs)
            return await destination.original_response()
    else:
        return await destination.send(embed=embed, **kwargs)

def format_duration(seconds: int) -> str:
    """Formata segundos em string legível (ex: 2h30m)"""
    periods = [
        ('dia', 86400),
        ('hora', 3600),
        ('minuto', 60),
        ('segundo', 1)
    ]
    
    parts = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            plural = 's' if period_value > 1 else ''
            parts.append(f"{period_value} {period_name}{plural}")
    
    return ' '.join(parts[:3]) or '0 segundos'

def parse_time(time_str: str) -> Optional[timedelta]:
    """Converte strings como '1h30m' em timedelta"""
    time_dict = {
        'd': 86400,
        'h': 3600,
        'm': 60,
        's': 1
    }
    
    try:
        seconds = 0
        for match in re.finditer(r'(\d+)([dhms])', time_str.lower()):
            num, unit = match.groups()
            seconds += int(num) * time_dict[unit]
        return timedelta(seconds=seconds)
    except (ValueError, AttributeError):
        return None

def split_long_message(
    text: str,
    max_length: int = 2000,
    delimiter: str = "\n"
) -> List[str]:
    """Divide mensagens longas em partes que cabem nos limites do Discord"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        split_at = text.rfind(delimiter, 0, max_length)
        if split_at == -1:
            split_at = max_length
        
        part = text[:split_at].strip()
        if part:
            parts.append(part)
        text = text[split_at:].strip()
    
    return parts
