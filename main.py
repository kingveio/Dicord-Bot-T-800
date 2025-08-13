import discord
from discord.ext import commands, tasks
from discord import app_commands
from data.data_manager import DataManager
from flask import Flask
from threading import Thread
import os
from datetime import datetime, timedelta
import asyncio
import base64

# Configuração inicial
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="t-800 ", intents=intents)
data_manager = DataManager()

# Servidor web para keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    last_backup = data_manager.data["metadata"].get("last_backup", "Nunca")
    return f"""
    <h1>T-800 Status</h1>
    <p><strong>Online desde:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Último backup:</strong> {last_backup}</p>
    <p><strong>Servidores:</strong> {len(bot.guilds)}</p>
    """
def run_flask():
    port = int(os.environ.get('PORT', 8080))  # Usa a porta do Render ou 8080 como fallback
    flask_app.run(host='0.0.0.0', port=port)

# COMANDOS DE CONFIGURAÇÃO
@bot.tree.command(name="configurar_backup", description="[ADMIN] Ativa/desativa backups automáticos")
@app_commands.default_permissions(administrator=True)
async def config_backup(interaction: discord.Interaction, ativar: bool):
    guild_data = data_manager.get_guild_data(interaction.guild.id)
    guild_data["config"]["backup_enabled"] = ativar
    data_manager._save_data()
    
    await interaction.response.send_message(
        f"✅ Backups automáticos {'ativados' if ativar else 'desativados'}!",
        ephemeral=True
    )

# COMANDOS DE USUÁRIO
@bot.tree.command(name="vincular_twitch", description="Vincula sua conta da Twitch")
@app_commands.describe(username="Seu nome de usuário na Twitch (sem URL)")
async def vincular_twitch(interaction: discord.Interaction, username: str):
    try:
        success = data_manager.link_user_channel(
            guild=interaction.guild,
            user=interaction.user,
            platform="twitch",
            channel_id=username
        )
        
        if success:
            await interaction.response.send_message(
                f"✅ Twitch **{username}** vinculada com sucesso!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Falha ao vincular conta Twitch",
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="minhas_vinculacoes", description="Mostra seus canais vinculados")
async def minhas_vinculacoes(interaction: discord.Interaction):
    try:
        platforms = data_manager.get_user_platforms(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id
        )
        
        embed = discord.Embed(
            title="Seus Canais Vinculados",
            color=discord.Color.blue()
        )
        
        if platforms.get("twitch"):
            embed.add_field(
                name="🔴 Twitch",
                value=f"[{platforms['twitch']}](https://twitch.tv/{platforms['twitch']})",
                inline=False
            )
        
        if platforms.get("youtube"):
            embed.add_field(
                name="▶️ YouTube",
                value=f"[Canal](https://youtube.com/channel/{platforms['youtube']})",
                inline=False
            )
        
        if not platforms.get("twitch") and not platforms.get("youtube"):
            embed.description = "Você não tem nenhum canal vinculado!"
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro: {str(e)}",
            ephemeral=True
        )

# COMANDOS DE ADMIN
@bot.tree.command(name="forcar_backup", description="[ADMIN] Executa um backup manual")
@app_commands.default_permissions(administrator=True)
async def forcar_backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        result = data_manager.backup_to_drive()
        
        embed = discord.Embed(
            title="📂 Resultado do Backup",
            color=discord.Color.green() if result["success"] else discord.Color.red()
        )
        
        if result["success"]:
            embed.description = f"Backup realizado com sucesso!\n**Arquivo:** {result['file_name']}"
            embed.add_field(
                name="🔗 Link",
                value=f"[Abrir no Drive]({result['file_url']})",
                inline=False
            )
        else:
            embed.description = "❌ Falha no backup"
            embed.add_field(
                name="Erro",
                value=result.get("error", "Desconhecido"),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(
            f"⚠️ Erro crítico: {str(e)}",
            ephemeral=True
        )

# TAREFAS AUTOMÁTICAS
@tasks.loop(hours=24)
async def daily_backup():
    try:
        print("⏳ Executando backup diário...")
        result = data_manager.backup_to_drive()
        
        if result["success"]:
            print(f"✅ Backup realizado: {result['file_name']}")
        else:
            print(f"❌ Falha no backup: {result.get('error', 'Desconhecido')}")
            
    except Exception as e:
        print(f"⚠️ Erro na tarefa de backup: {str(e)}")

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Inicia servidor web
    Thread(target=run_flask).start()
    
    # Sincroniza comandos
    try:
        synced = await bot.tree.sync()
        print(f'🔁 {len(synced)} comandos sincronizados')
    except Exception as e:
        print(f'❌ Erro ao sincronizar comandos: {e}')
    
    # Inicia tarefas automáticas
    daily_backup.start()
    print("🔄 Tarefas automáticas iniciadas")

# INICIALIZAÇÃO
if __name__ == "__main__":
    # Configura credenciais do Google Drive se existirem
    if os.getenv('GOOGLE_CREDENTIALS'):
        with open("credentials.json", "wb") as f:
            f.write(base64.b64decode(os.getenv('GOOGLE_CREDENTIALS')))
    
    # Verifica token
    if not os.getenv('DISCORD_TOKEN'):
        raise ValueError("❌ Token do Discord não configurado!")
    
    print("🚀 Iniciando T-800...")
    bot.run(os.getenv('DISCORD_TOKEN'))
