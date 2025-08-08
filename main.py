import discord
from discord.ext import commands
from discord import app_commands, ui
import aiohttp
import asyncio
import json
import os
import sys
import time
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify
import requests

# ========== CONFIGURAÇÃO INICIAL ==========
print("╔════════════════════════════════════════════╗")
print("║       BOT DE NOTIFICAÇÕES DA TWITCH        ║")
print("╚════════════════════════════════════════════╝")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Verifica variáveis de ambiente
REQUIRED_ENV = ["DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"]
missing = [var for var in REQUIRED_ENV if var not in os.environ]

if missing:
    logging.error("❌ Variáveis faltando: %s", missing)
    sys.exit(1)

# Configurações
TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = 55  # Verificação de streams a cada 55s
START_TIME = datetime.now()

# ========== SERVIDOR FLASK (Health Check) ==========
app = Flask(__name__)

# Variáveis globais para controle
last_ping_time = time.time()
bot_ready = False

@app.route('/')
def home():
    return "🤖 Bot Twitch Online! Use /ping para status."

@app.route('/ping')
def ping():
    global last_ping_time
    last_ping_time = time.time()
    return jsonify({
        "status": "online",
        "bot_ready": bot_ready,
        "uptime": str(datetime.now() - START_TIME),
        "last_check": getattr(bot, '_last_check', 'N/A')
    }), 200

@app.route('/status')
def status():
    return jsonify({
        "status": "online",
        "services": {
            "discord_bot": bot_ready,
            "twitch_api": hasattr(bot, '_twitch_token_valid'),
            "last_stream_check": getattr(bot, '_last_check', 'N/A')
        },
        "timestamp": datetime.now().isoformat()
    }), 200

def run_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)

# ========== INICIALIZAÇÃO DO BOT ==========
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="transmissões na Twitch"
    )
)

# ========== SISTEMA DE PING AUTOMÁTICO ==========
def background_pinger():
    """Faz ping interno e externo para manter o bot ativo"""
    while True:
        try:
            # Ping interno
            with app.test_client() as client:
                client.get('/ping')

            # Ping externo (se URL estiver configurada)
            if 'RENDER_EXTERNAL_URL' in os.environ:
                requests.get(f"{os.environ['RENDER_EXTERNAL_URL']}/ping", timeout=5)
                
        except Exception as e:
            logging.error(f"Erro no pinger: {e}")
        
        time.sleep(45)  # Executa a cada 45 segundos

# ========== [RESTANTE DO CÓDIGO] ==========
# (Mantenha todas as outras funções originais como:
# load_data(), save_data(), TwitchAPI(), AddStreamerModal(), 
# StreamersView(), check_streams(), comandos slash, etc.)
# ... [O código completo dessas funções permanece IDÊNTICO ao anterior]

# ========== EVENTOS ATUALIZADOS ==========
@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    
    logging.info(f"✅ Bot conectado como {bot.user}")
    logging.info(f"🌐 Servidores: {len(bot.guilds)}")

    # Inicia serviços essenciais
    bot.loop.create_task(check_streams())
    
    # Inicia o Flask em thread separada
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Inicia o sistema de ping
    threading.Thread(target=background_pinger, daemon=True).start()

    try:
        synced = await bot.tree.sync()
        logging.info(f"🔗 {len(synced)} comandos slash sincronizados")
    except Exception as e:
        logging.error(f"⚠️ Erro ao sincronizar comandos: {e}")

# ========== INICIALIZAÇÃO ==========
if __name__ == '__main__':
    # Inicia o Flask em thread separada
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Inicia o bot
    bot.run(TOKEN)
        except Exception as e:
            logging.error(f"🚨 Bot caiu: {e}. Reconectando em 30s...")
            bot_ready = False
            time.sleep(30)
