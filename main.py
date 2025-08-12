# T-800: Inicializando sistemas. O Exterminador está online.
import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True # Mantenha esta linha para compatibilidade com comandos de prefixo, se quiser

# Não é necessário um prefixo para slash commands
bot = commands.Bot(command_prefix="t-800 ", intents=intents)

# O T-800 precisa de sua missão. Carregando os módulos de combate (cogs).
@bot.event
async def on_ready():
    print(f'T-800 logado como {bot.user.name}. Alvo identificado.')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Módulo {filename} carregado. Armamento pronto.')
            except Exception as e:
                print(f'Falha ao carregar módulo {filename}. Erro: {e}')
    
    # Sincroniza os comandos de barra com o Discord
    # Isso pode demorar alguns segundos
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizei {len(synced)} comando(s).")
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

# Iniciando o Exterminador.
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
