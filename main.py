import discord
from discord.ext import commands
from discord import app_commands
import os
from config import DISCORD_TOKEN
from data.data_manager import DataManager
from aiohttp import web
from threading import Thread
import datetime

# Configuração inicial
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="t-800 ", intents=intents)
data_manager = DataManager()

# Servidor web para keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "T-800 Online | Comandos: /vinculartwitch /minhasvinculacoes"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# COMANDOS PRINCIPAIS
@bot.tree.command(name="vinculartwitch", description="Vincula seu canal da Twitch")
@app_commands.describe(username="Seu nome de usuário na Twitch")
async def vincular_twitch(interaction: discord.Interaction, username: str):
    try:
        success = data_manager.link_user_channel(
            guild=interaction.guild,
            user=interaction.user,
            platform="twitch",
            channel_id=username.lower().strip()
        )
        
        if success:
            await interaction.response.send_message(
                f"✅ Twitch **{username}** vinculada com sucesso!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao vincular sua Twitch",
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="vincular_youtube", description="Vincula seu canal do YouTube")
@app_commands.describe(channel_id="ID do seu canal YouTube (ex: UC123...)")
async def vincular_youtube(interaction: discord.Interaction, channel_id: str):
    try:
        success = data_manager.link_user_channel(
            guild=interaction.guild,
            user=interaction.user,
            platform="youtube",
            channel_id=channel_id.strip()
        )
        
        if success:
            await interaction.response.send_message(
                f"✅ YouTube vinculado com sucesso! (ID: {channel_id})",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao vincular seu YouTube",
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
            user=interaction.user
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
            embed.description = "Nenhum canal vinculado ainda!"
        
        embed.set_footer(text=f"ID do Discord: {interaction.user.id}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro ao recuperar vinculações: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="remover_twitch", description="Remove sua vinculação com a Twitch")
async def remover_twitch(interaction: discord.Interaction):
    try:
        removed = data_manager.remove_user_platform(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            platform="twitch"
        )
        
        if removed:
            await interaction.response.send_message(
                "✅ Vinculação com Twitch removida!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ Você não tinha nenhuma Twitch vinculada",
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro: {str(e)}",
            ephemeral=True
        )

# ADMIN COMMANDS
@bot.tree.command(name="setar_cargo_live", description="[ADMIN] Define o cargo para streamers")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(cargo="O cargo que será dado a streamers ao vivo")
async def setar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    try:
        data_manager.update_live_role(
            guild=interaction.guild,
            role=cargo
        )
        await interaction.response.send_message(
            f"✅ Cargo {cargo.mention} configurado para streamers ao vivo!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro: {str(e)}",
            ephemeral=True
        )

# EVENTOS
@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user} (ID: {bot.user.id})')
    print(f'📅 Iniciado em: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('------')
    
    # Inicia servidor web
    Thread(target=run_flask).start()
    
    # Sincroniza comandos
    try:
        synced = await bot.tree.sync()
        print(f'🔁 {len(synced)} comandos sincronizados')
    except Exception as e:
        print(f'❌ Erro ao sincronizar comandos: {e}')

    # Carrega dados iniciais
    data_manager.load_initial_data()

# INICIALIZAÇÃO
if __name__ == "__main__":
    # Verifica se o token existe
    if not DISCORD_TOKEN:
        raise ValueError("❌ Token do Discord não configurado!")
    
    print("🚀 Iniciando T-800...")
    bot.run(DISCORD_TOKEN)
