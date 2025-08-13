# T-800: Inicializando sistemas. O Exterminador está online.
import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN
from aiohttp import web

# Definindo as intenções do bot.
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

# Criando a instância do bot.
bot = commands.Bot(command_prefix="t-800 ", intents=intents)

# O T-800 precisa de sua missão. Carregando os módulos de combate (cogs).
@bot.event
async def on_ready():
    print(f'T-800 logado como {bot.user.name}. Alvo identificado.')
    
    # 1. Inicia o servidor web assim que o bot estiver pronto
    #    Agora, o 'bot.loop' está disponível.
    bot.loop.create_task(start_webserver())
    
    # 2. Carrega os cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Módulo {filename} carregado. Armamento pronto.')
            except Exception as e:
                print(f'Falha ao carregar módulo {filename}. Erro: {e}')

    # 3. Sincroniza os comandos de barra (slash commands) com o Discord.
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizei {len(synced)} comando(s) de barra.")
    except Exception as e:
        print(f"Falha ao sincronizar comandos: {e}")

# ... (outras funções do bot) ...

# Função para o servidor web.
async def health_check(request):
    return web.Response(text="T-800 está online.")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Servidor web iniciado na porta {port}.")


# Iniciando o Exterminador.
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
