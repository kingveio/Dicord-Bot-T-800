import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN
from flask import Flask
from threading import Thread
import time
import asyncio

# Configuração do servidor Flask para keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return """
    <h1>T-800 Online</h1>
    <p>Bot Status: <span style="color: green;">Operacional</span></p>
    <p>Uptime: {:.2f} horas</p>
    """.format(time.time() - start_time / 3600)

@flask_app.route('/ping')
def ping():
    return {"status": "active", "bot": "online"}, 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# Configuração do Bot
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix="t-800 ",
    intents=intents,
    reconnect=True  # Habilita auto-reconexão
)

# Variável global para controle de uptime
start_time = time.time()

@bot.event
async def on_ready():
    print(f'\n✅ Bot conectado como {bot.user} (ID: {bot.user.id})')
    print(f'📅 Iniciado em: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print('------')
    
    # Inicia o servidor Flask em segundo plano
    Thread(target=run_flask).start()
    
    # Carrega todos os cogs
    await load_cogs()
    
    # Sincroniza comandos slash
    await sync_commands()

async def load_cogs():
    """Carrega dinamicamente todos os cogs"""
    loaded = []
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                loaded.append(filename)
            except Exception as e:
                print(f'❌ Falha ao carregar {filename}: {type(e).__name__}: {e}')
    
    if loaded:
        print(f'✅ Cogs carregados: {", ".join(loaded)}')

async def sync_commands():
    """Sincroniza comandos slash globalmente e em servidor teste"""
    try:
        # Sincronização global
        synced = await bot.tree.sync()
        print(f'🔁 {len(synced)} comandos slash sincronizados globalmente')
        
        # Sincronização adicional para servidor de teste (opcional)
        if os.getenv('TEST_GUILD'):
            test_guild = discord.Object(id=int(os.getenv('TEST_GUILD')))
            await bot.tree.sync(guild=test_guild)
            print(f'🔁 Comandos sincronizados no servidor de teste')
    except Exception as e:
        print(f'❌ Erro ao sincronizar comandos: {type(e).__name__}: {e}')

@bot.command(name="sync", hidden=True)
@commands.is_owner()
async def sync(ctx):
    """Força a sincronização dos comandos slash"""
    try:
        synced = await bot.tree.sync()
        await ctx.send(f'✅ {len(synced)} comandos sincronizados!')
    except Exception as e:
        await ctx.send(f'❌ Falha: {e}')

@bot.command(name="uptime", hidden=True)
async def uptime(ctx):
    """Mostra o tempo online do bot"""
    uptime_seconds = int(time.time() - start_time)
    await ctx.send(f"⏱️ Bot online há {uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m")

@bot.event
async def on_disconnect():
    print('⚠️ Bot desconectado! Tentando reconectar...')

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'⚠️ Erro no evento {event}: {args}')

# Handler global de exceções
async def main():
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginError:
        print("❌ Token inválido! Verifique seu DISCORD_TOKEN")
    except Exception as e:
        print(f"❌ Falha crítica: {type(e).__name__}: {e}")
        print("🔄 Reiniciando em 60 segundos...")
        await asyncio.sleep(60)
        await main()  # Reinicia o bot

if __name__ == "__main__":
    # Verificação básica do token
    if not DISCORD_TOKEN:
        raise ValueError("❌ DISCORD_TOKEN não configurado!")
    
    print("🚀 Iniciando T-800...")
    asyncio.run(main())
