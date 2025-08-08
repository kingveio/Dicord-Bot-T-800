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
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
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

# Verifica variáveis de ambiente necessárias
REQUIRED_ENV = ["DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"]
missing = [var for var in REQUIRED_ENV if var not in os.environ]

if missing:
    logging.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

# Configurações
TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = 60  # segundos

# ========== SERVIDOR FLASK (Keep-Alive) ==========
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot Twitch Online! Mantido por Flask + UptimeRobot."

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def start_keepalive():
    """Inicia o servidor Flask e o ping automático."""
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Se estiver no Replit, ativa ping automático
    if "REPLIT" in os.environ:
        def auto_ping():
            while True:
                try:
                    url = f"https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co"
                    requests.get(url, timeout=5)
                    logging.info("🔄 Ping automático (manter online)")
                except Exception as e:
                    logging.error("⚠️ Falha no ping: %s", e)
                time.sleep(300)  # Ping a cada 5 minutos

        Thread(target=auto_ping, daemon=True).start()

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

# ========== GERENCIAMENTO DE DADOS ==========
def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump({}, f)
            return {}

        with open(DATA_FILE) as f:
            return json.load(f)
    except Exception as e:
        logging.error("Erro ao carregar dados: %s", e)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error("Erro ao salvar dados: %s", e)

# ========== API DA TWITCH ==========
class TwitchAPI:
    def __init__(self):
        self.token = None
        self.token_expiry = None

    async def get_token(self):
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": TWITCH_CLIENT_ID,
                        "client_secret": TWITCH_SECRET,
                        "grant_type": "client_credentials"
                    }
                ) as response:
                    data = await response.json()
                    self.token = data["access_token"]
                    self.token_expiry = datetime.now() + timedelta(seconds=3300)
                    logging.info("🔑 Novo token Twitch obtido")
                    return self.token
        except Exception as e:
            logging.error("Erro ao obter token Twitch: %s", e)
            return None

    async def check_live_streams(self, usernames):
        token = await self.get_token()
        if not token:
            return set()

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(usernames)
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logging.error("Erro na API Twitch: %s", response.status)
                        return set()

                    data = await response.json()
                    return {s["user_login"].lower() for s in data.get("data", [])}
        except Exception as e:
            logging.error("Erro ao verificar streams: %s", e)
            return set()

twitch_api = TwitchAPI()

# ========== DISCORD MODAL (Adicionar Streamer) ==========
class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_name = ui.TextInput(label="Nome na Twitch", placeholder="ex: xqc", min_length=3)
    discord_member = ui.TextInput(label="Membro do Discord", placeholder="@usuário ou ID")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            twitch_username = self.twitch_name.value.lower().strip()
            member_input = self.discord_member.value.strip()

            # Extrai ID do Discord (menção, ID ou nome)
            if member_input.startswith("<@") and member_input.endswith(">"):
                discord_id = "".join(c for c in member_input if c.isdigit())
            elif member_input.isdigit() and len(member_input) >= 17:
                discord_id = member_input
            else:
                # Busca por nome/nick
                member_found = None
                async for member in interaction.guild.fetch_members(limit=None):
                    if (member_input.lower() in member.name.lower() or
                        member_input.lower() in (member.display_name or "").lower()):
                        member_found = member
                        break

                if not member_found:
                    raise ValueError("Membro não encontrado")
                discord_id = str(member_found.id)

            # Verifica se já existe
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id not in data:
                data[guild_id] = {}

            if twitch_username in data[guild_id]:
                await interaction.response.send_message(
                    f"⚠️ {twitch_username} já está vinculado a <@{data[guild_id][twitch_username]}>",
                    ephemeral=True
                )
                return

            data[guild_id][twitch_username] = discord_id
            save_data(data)

            await interaction.response.send_message(
                f"✅ <@{discord_id}> vinculado à Twitch: {twitch_username}",
                ephemeral=True
            )

        except Exception as e:
            logging.error("Erro ao adicionar streamer: %s", e)
            await interaction.response.send_message(
                f"❌ Erro: {str(e)}",
                ephemeral=True
            )

# ========== DISCORD VIEW (Painel de Controle) ==========
class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = load_data()
        guild_streamers = data.get(str(interaction.guild.id), {})

        if not guild_streamers:
            await interaction.response.send_message("❌ Nenhum streamer registrado!", ephemeral=True)
            return

        select = ui.Select(placeholder="Selecione um streamer para remover...")
        for streamer in guild_streamers:
            select.add_option(label=streamer)

        async def callback(interaction: discord.Interaction):
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id in data and select.values[0] in data[guild_id]:
                removed = select.values[0]
                del data[guild_id][removed]
                save_data(data)
                await interaction.response.send_message(
                    f"✅ Removido: {removed}",
                    ephemeral=True
                )

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        data = load_data()
        guild_streamers = data.get(str(interaction.guild.id), {})

        if not guild_streamers:
            await interaction.response.send_message("📭 Nenhum streamer registrado!", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(
                name=f"🔹 {twitch_user}",
                value=f"Discord: {member.mention if member else 'Não encontrado'}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== VERIFICADOR DE STREAMS ==========
async def check_streams():
    while True:
        try:
            data = load_data()
            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            all_streamers = set()
            for guild_streamers in data.values():
                all_streamers.update(guild_streamers.keys())

            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            live_streamers = await twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue

                live_role = discord.utils.get(guild.roles, name="Ao Vivo")
                if not live_role:
                    continue

                for twitch_user, discord_id in streamers.items():
                    try:
                        member = guild.get_member(int(discord_id))
                        if not member:
                            continue

                        is_live = twitch_user.lower() in live_streamers
                        has_role = live_role in member.roles

                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            logging.info(f"➕ Cargo adicionado para {member} ({twitch_user})")
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            logging.info(f"➖ Cargo removido de {member} ({twitch_user})")
                    except Exception as e:
                        logging.error(f"Erro ao atualizar cargo: {e}")

        except Exception as e:
            logging.error(f"Erro no verificador de streams: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ========== COMANDOS SLASH ==========
@bot.tree.command(name="streamers", description="Gerenciar notificações de streamers")
@app_commands.default_permissions(manage_guild=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🎮 Painel de Streamers** - Escolha uma opção:",
        view=StreamersView(),
        ephemeral=True
    )

# ========== COMANDOS DE TEXTO ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx: commands.Context):
    """Sincroniza comandos slash (apenas admins)"""
    try:
        await bot.tree.sync(guild=ctx.guild)
        await ctx.send("✅ Comandos sincronizados!")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx: commands.Context):
    """Configura o cargo 'Ao Vivo' (apenas mods)"""
    live_role = discord.utils.get(ctx.guild.roles, name="Ao Vivo")
    if not live_role:
        try:
            live_role = await ctx.guild.create_role(
                name="Ao Vivo",
                color=discord.Color.purple(),
                hoist=True,
                mentionable=True
            )
            await ctx.send(f"✅ Cargo criado: {live_role.mention}")
        except Exception as e:
            await ctx.send(f"❌ Erro ao criar cargo: {e}")
            return
    await ctx.send("✅ Bot configurado! Use `/streamers` para gerenciar.")

# ========== EVENTOS ==========
@bot.event
async def on_ready():
    logging.info(f"✅ Bot conectado como {bot.user.name} (ID: {bot.user.id})")
    logging.info(f"🌐 Servidores: {len(bot.guilds)}")

    # Inicia a verificação de streams
    bot.loop.create_task(check_streams())

    # Sincroniza comandos slash
    try:
        await bot.tree.sync()
        logging.info("🔗 Comandos slash sincronizados")
    except Exception as e:
        logging.error(f"⚠️ Erro ao sincronizar comandos: {e}")

# ========== INICIAR O BOT ==========
if __name__ == "__main__":
    start_keepalive()  # Ativa o keep-alive (Flask + ping automático)

    # Tenta reconectar automaticamente em caso de falha
    while True:
        try:
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"⚠️ Bot caiu: {e}. Reconectando em 60 segundos...")
            time.sleep(60)
