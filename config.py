# T-800: Inserindo chip de processamento... Carregando diretivas de missão.
import os
from dotenv import load_dotenv

# O T-800 não armazena dados sensíveis no código-fonte.
# Carregamos as credenciais do ambiente de execução.
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
