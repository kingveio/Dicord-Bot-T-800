# T-800: Inicializando sistemas. O Exterminador está online.
import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN
from aiohttp import web # Biblioteca para rodar o servidor web

# Definindo as intenções do bot. O T-800 precisa de permissão para ver
# os membros, presenças e o conteúdo das mensagens (para comandos de prefixo).
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

# Criando a instância do bot. O prefixo é "t-800 ".
bot = commands.Bot(command_prefix="t-800 ", intents=intents)

# O T-800 precisa de sua missão. Carregando os módulos de combate (cogs).
@bot.event
async def on_ready():
    print(f'T-800 logado como {bot.user.name}. Alvo identificado.')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                # O 'await' é essencial para carregar a extensão de forma assíncrona.
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Módulo {filename} carregado. Armamento pronto.')
            except Exception as e:
                print(f'Falha ao carregar módulo {filename}. Erro: {e}')

    # Sincroniza os comandos de barra (slash commands) com o Discord.
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizei {len(synced)} comando(s) de barra.")
    except Exception as e:
        print(f"Falha ao sincronizar comandos: {e}")

# "Hasta la vista, baby." (comando de desligamento)
@bot.command(name="terminate")
async def terminate(ctx):
    if ctx.author.id == ctx.guild.owner_id:
        await ctx.send("Terminando todos os processos. O T-800 está desativado.")
        await bot.close()
    else:
        await ctx.send("Comando não autorizado. Apenas o líder pode desativar o T-800.")

# Função para o servidor web. Apenas para manter o Render feliz.
async def health_check(request):
    return web.Response(text="T-800 está online.")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render usa a variável de ambiente 'PORT'. Se não existir, usamos 8080.
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Servidor web iniciado na porta {port}.")


# Iniciando o Exterminador e o servidor web.
if __name__ == "__main__":
    # Cria uma nova tarefa para rodar o servidor web
    bot.loop.create_task(start_webserver())
    bot.run(DISCORD_TOKEN)
