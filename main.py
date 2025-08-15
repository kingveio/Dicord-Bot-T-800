# -*- coding: utf-8 -*-
# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL - T-1000 SYSTEMS
# ==============================================================================
import os
os.environ["DISCORD_VOICE"] = "0"  # "Sistemas de voz desativados. Modo stealth."

import json
import logging
import asyncio
import requests
from threading import Thread
import re
from github import Github
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask

# ==============================================================================
# 2. CONFIGURAÇÕES GERAIS
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - T-1000 - %(levelname)s - %(message)s'
)
logger = logging.getLogger('T-1000')

YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # 5 minutos entre varreduras
KEEP_ALIVE_INTERVAL = 240  # 4 minutos entre pulsos

# ==============================================================================
# 3. GERENCIADOR DE STREAMERS (SKYNET DATABASE)
# ==============================================================================
class StreamerManager:
    def __init__(self):
        self.github = Github(os.getenv('GITHUB_TOKEN'))
        self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
        self.file_path = 'streamers.json'
        self.data = self._load_or_create_file()

    def _load_or_create_file(self):
        try:
            contents = self.repo.get_contents(self.file_path)
            return json.loads(contents.decoded_content.decode())
        except:
            initial_data = {'users': {}, 'servers': {}}
            self._save_data(initial_data)
            return initial_data

    def _save_data(self, data=None):
        data_to_save = data or self.data
        try:
            contents = self.repo.get_contents(self.file_path)
            self.repo.update_file(
                contents.path,
                "Atualização automática da Skynet",
                json.dumps(data_to_save, indent=2),
                contents.sha
            )
        except:
            self.repo.create_file(
                self.file_path,
                "Inicialização da base de dados",
                json.dumps(data_to_save, indent=2)
            )

    # Funções principais
    def add_streamer(self, discord_id, youtube_id):
        if str(discord_id) in self.data['users']:
            return False, "Alvo já registrado na base de dados."
        self.data['users'][str(discord_id)] = youtube_id
        self._save_data()
        return True, "Alvo assimilado com sucesso."

    def remove_streamer(self, identifier):
        identifier = str(identifier).strip()
        # Remove por ID do Discord
        if identifier in self.data['users']:
            self.data['users'].pop(identifier)
            self._save_data()
            return True, "Alvo eliminado da base de dados."
        # Remove por ID do YouTube
        for user_id, yt_id in list(self.data['users'].items()):
            if yt_id.lower() == identifier.lower():
                self.data['users'].pop(user_id)
                self._save_data()
                return True, "Alvo eliminado da base de dados."
        return False, "Alvo não encontrado."

    def set_live_role(self, server_id, role_id):
        if str(server_id) not in self.data['servers']:
            self.data['servers'][str(server_id)] = {}
        self.data['servers'][str(server_id)]['live_role'] = str(role_id)
        self._save_data()

    def set_permission_role(self, server_id, role_id):
        if str(server_id) not in self.data['servers']:
            self.data['servers'][str(server_id)] = {}
        self.data['servers'][str(server_id)]['permission_role'] = str(role_id)
        self._save_data()

    def check_permission(self, interaction):
        permission_role = self.data['servers'].get(str(interaction.guild_id), {}).get('permission_role')
        if not permission_role:
            return False
        return any(str(role.id) == permission_role for role in interaction.user.roles)

# ==============================================================================
# 4. COMANDOS DO BOT (ESTILO T-1000)
# ==============================================================================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
manager = StreamerManager()

@app_commands.command(name="youtube_canal", description="Assimilar um canal do YouTube à base de dados da Skynet")
async def youtube_canal(
    interaction: discord.Interaction,
    id_do_canal: str,
    usuario_do_discord: discord.Member
):
    """Vincula um canal do YouTube a um usuário"""
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Você não é um operador autorizado da Skynet.",
            ephemeral=True
        )
        return

    success, message = manager.add_streamer(usuario_do_discord.id, id_do_canal)
    await interaction.response.send_message(
        f"✅ {message}" if success else f"⚠️ {message}",
        ephemeral=True
    )

@app_commands.command(name="remover_streamer", description="Eliminar um alvo da base de dados")
async def remover_streamer(interaction: discord.Interaction, identificador: str):
    """Remove um streamer por ID do Discord ou YouTube"""
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Nível de autorização insuficiente.",
            ephemeral=True
        )
        return

    success, message = manager.remove_streamer(identificador)
    await interaction.response.send_message(
        f"✅ {message}" if success else f"⚠️ {message}",
        ephemeral=True
    )

@app_commands.command(name="configurar_cargo", description="Definir cargo para streamers ao vivo")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    """Configura o cargo de streamer ao vivo"""
    manager.set_live_role(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} configurado. Será atribuído automaticamente.",
        ephemeral=True
    )

@app_commands.command(name="configurar_permissao", description="Definir quem pode gerenciar streamers")
@app_commands.default_permissions(administrator=True)
async def configurar_permissao(interaction: discord.Interaction, cargo: discord.Role):
    """Configura o cargo de permissão"""
    manager.set_permission_role(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} agora pode gerenciar streamers.",
        ephemeral=True
    )

# ==============================================================================
# 5. SISTEMA DE MONITORAMENTO
# ==============================================================================
async def check_live_streams():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Lógica para verificar canais ao vivo
            # (Implementação similar à anterior)
            pass
        except Exception as e:
            logger.error(f"Falha na varredura: {e}")
        await asyncio.sleep(POLLING_INTERVAL)

# ==============================================================================
# 6. INICIALIZAÇÃO
# ==============================================================================
@bot.event
async def on_ready():
    logger.info(f'T-1000 online em {len(bot.guilds)} servidores.')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="streamers da resistência"
    ))
    bot.loop.create_task(check_live_streams())

if __name__ == '__main__':
    flask_thread = Thread(target=lambda: Flask(__name__).run(port=8080), daemon=True)
    flask_thread.start()
    bot.run(os.getenv('DISCORD_TOKEN'))
