import discord
from discord.ext import commands
import os
from config import DISCORD_TOKEN
from aiohttp import web

# Configuração robusta de intents
intents = discord.Intents.all()  # Usando all() para garantir todas as permissões necessárias
bot = commands.Bot(command_prefix="t-800 ", intents=intents)

@bot.event
async def on_ready():
    print(f'T-800 logado como {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Inicia servidor web
    bot.loop.create_task(start_webserver())
    
    # Carregamento dinâmico de cogs
    loaded_extensions = []
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                loaded_extensions.append(filename)
                print(f'✅ {filename} carregado com sucesso')
            except Exception as e:
                print(f'❌ Falha ao carregar {filename}: {type(e).__name__}: {e}')

    # Sincronização de comandos slash
    try:
        print("\nSincronizando comandos slash...")
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos slash sincronizados globalmente")
        
        # Sincronização adicional para um servidor específico (opcional)
        guild_id = os.getenv('TEST_GUILD')  # Defina no .env para testes
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"✅ {len(synced_guild)} comandos sincronizados no servidor de teste")
            
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {type(e).__name__}: {e}")
        
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando não encontrado. Use `t-800 help` para ver os comandos.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Você não tem permissão para executar este comando!")
    else:
        await ctx.send(f"⚠️ Erro: {str(error)}")
        raise error
        
@bot.command(name="sync", hidden=True)
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Sincroniza comandos manualmente (apenas dono do bot)"""
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ {len(synced)} comandos sincronizados globalmente!")
    except Exception as e:
        await ctx.send(f"❌ Falha na sincronização: {e}")

@bot.command(name="terminate")
@commands.is_owner()
async def terminate(ctx):
    """Desliga o bot (apenas dono)"""
    await ctx.send("Terminando todos os processos. O T-800 está desativado.")
    await bot.close()

# Servidor web (para health checks)
async def health_check(request):
    return web.Response(text="T-800 online | Comandos: " + str(len(bot.tree.get_commands())))

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Servidor web iniciado na porta {port}")

if __name__ == "__main__":
    # Verifica se o token está configurado
    if not DISCORD_TOKEN:
        raise ValueError("Token do Discord não configurado!")
    
    print("Iniciando T-800...")
    bot.run(DISCORD_TOKEN)
