import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN
from aiohttp import web

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="t-800 ", intents=intents)

@bot.event
async def on_ready():
    print(f'T-800 logado como {bot.user.name}. Alvo identificado.')
    
    # Inicia servidor web
    bot.loop.create_task(start_webserver())
    
    # Carrega cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Módulo {filename} carregado. Armamento pronto.')
            except Exception as e:
                print(f'Falha ao carregar módulo {filename}. Erro: {e}')

    try:
        synced = await bot.tree.sync()
        print(f"Sincronizei {len(synced)} comando(s) de barra.")
    except Exception as e:
        print(f"Falha ao sincronizar comandos: {e}")

@bot.command(name="terminate")
async def terminate(ctx):
    if ctx.author.id == ctx.guild.owner_id:
        await ctx.send("Terminando todos os processos. O T-800 está desativado.")
        await bot.close()
    else:
        await ctx.send("Comando não autorizado. Apenas o líder pode desativar o T-800.")

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

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
