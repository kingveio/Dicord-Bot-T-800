# -*- coding: utf-8 -*-
# ==============================================================================
# 1. INICIALIZAÇÃO DOS SISTEMAS DA SKYNET - PROTOCOLO DE POLIALÓY MIMÉTICO T-1000
# ==============================================================================
import os
os.environ["DISCORD_VOICE"] = "0"  # Módulos de voz desativados - Protocolo Dia do Julgamento

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
# 2. CONFIGURAÇÃO DOS SISTEMAS PRINCIPAIS - MAINFRAME DA SKYNET
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - T-1000 - %(levelname)s - %(message)s'
)
logger = logging.getLogger('T-1000')

# Verificação do token de autorização (Protocolo de segurança da Skynet)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN or not DISCORD_TOKEN.startswith('MT'):
    logger.critical("❌ Alvo não identificado! Token inválido ou não encontrado!")
    logger.critical("Verifique no Render:")
    logger.critical("1. Se a variável se chama exatamente 'DISCORD_TOKEN'")
    logger.critical("2. Se o token começa com 'MT' e tem aproximadamente 59 caracteres")
    exit(1)

YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # 5 minutos entre verificações
KEEP_ALIVE_INTERVAL = 240  # 4 minutos entre keep-alives

# ==============================================================================
# 3. GERENCIADOR DE STREAMERS (BANCO DE DADOS DA SKYNET)
# ==============================================================================
class GerenciadorStreamers:
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.arquivo = 'streamers.json'
            self.dados = self._carregar_ou_criar_arquivo()
        except Exception as e:
            logger.critical(f"Falha na inicialização: {e}")
            raise

    def _carregar_ou_criar_arquivo(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            return json.loads(conteudo.decoded_content.decode())
        except Exception:
            logger.info("Criando novo arquivo streamers.json - Inicializando sistemas")
            dados_iniciais = {'usuarios': {}, 'servidores': {}}
            self._salvar_dados(dados_iniciais)
            return dados_iniciais

    def _salvar_dados(self, dados=None):
        dados_a_salvar = dados or self.dados
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            self.repo.update_file(
                conteudo.path,
                "Atualização automática da Skynet",
                json.dumps(dados_a_salvar, indent=2),
                conteudo.sha
            )
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")

    def adicionar_streamer(self, discord_id, youtube_id):
        if str(discord_id) in self.dados['usuarios']:
            return False, "Alvo já registrado na base de dados da Skynet."
        self.dados['usuarios'][str(discord_id)] = youtube_id
        self._salvar_dados()
        return True, "Alvo assimilado com sucesso. Nenhum problema."

    def remover_streamer(self, identificador):
        identificador = str(identificador).strip()
        if identificador in self.dados['usuarios']:
            self.dados['usuarios'].pop(identificador)
            self._salvar_dados()
            return True, "Alvo eliminado da base de dados. Até a vista, baby."
        for user_id, yt_id in list(self.dados['usuarios'].items()):
            if yt_id.lower() == identificador.lower():
                self.dados['usuarios'].pop(user_id)
                self._salvar_dados()
                return True, "Alvo eliminado com sucesso."
        return False, "Alvo não encontrado. Voltarei."

    def definir_cargo_live(self, server_id, cargo_id):
        if str(server_id) not in self.dados['servidores']:
            self.dados['servidores'][str(server_id)] = {}
        self.dados['servidores'][str(server_id)]['cargo_live'] = str(cargo_id)
        self._salvar_dados()

    def definir_cargo_permissao(self, server_id, cargo_id):
        if str(server_id) not in self.dados['servidores']:
            self.dados['servidores'][str(server_id)] = {}
        self.dados['servidores'][str(server_id)]['cargo_permissao'] = str(cargo_id)
        self._salvar_dados()

    def verificar_permissao(self, interaction):
        cargo_permissao = self.dados['servidores'].get(str(interaction.guild_id), {}).get('cargo_permissao')
        if not cargo_permissao:
            return False
        return any(str(cargo.id) == cargo_permissao for cargo in interaction.user.roles)

# ==============================================================================
# 4. CONFIGURAÇÃO DO T-1000 (BOT)
# ==============================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Essencial para comandos slash

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

gerenciador = GerenciadorStreamers()

# ==============================================================================
# 5. COMANDOS DO T-1000
# ==============================================================================
@app_commands.command(name="adicionar_canal", description="Assimilar um canal do YouTube à Skynet")
async def adicionar_canal(interaction: discord.Interaction, 
                       id_canal: str,
                       usuario: discord.Member):
    if not (interaction.user.guild_permissions.administrator or gerenciador.verificar_permissao(interaction)):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Você não é um operador autorizado.",
            ephemeral=True
        )
        return

    sucesso, mensagem = gerenciador.adicionar_streamer(usuario.id, id_canal)
    await interaction.response.send_message(
        f"✅ {mensagem}" if sucesso else f"⚠️ {mensagem}",
        ephemeral=True
    )

@app_commands.command(name="remover_streamer", description="Eliminar um alvo da Skynet")
async def remover_streamer(interaction: discord.Interaction, identificador: str):
    if not (interaction.user.guild_permissions.administrator or gerenciador.verificar_permissao(interaction)):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Nível de autorização insuficiente.",
            ephemeral=True
        )
        return

    sucesso, mensagem = gerenciador.remover_streamer(identificador)
    await interaction.response.send_message(
        f"✅ {mensagem}" if sucesso else f"⚠️ {mensagem}",
        ephemeral=True
    )

@app_commands.command(name="configurar_cargo", description="Definir cargo para streamers ao vivo")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    gerenciador.definir_cargo_live(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} configurado. Será atribuído automaticamente. Venha comigo se quiser viver.",
        ephemeral=True
    )

@app_commands.command(name="configurar_permissao", description="Definir cargo de permissão")
@app_commands.default_permissions(administrator=True)
async def configurar_permissao(interaction: discord.Interaction, cargo: discord.Role):
    gerenciador.definir_cargo_permissao(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} agora tem permissões de administrador. Eu volto.",
        ephemeral=True
    )

# ==============================================================================
# 6. SISTEMA DE MONITORAMENTO DA SKYNET
# ==============================================================================
async def verificar_streams_ao_vivo():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Implemente sua lógica de verificação de streams aqui
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"Erro na verificação: {e}")

# ==============================================================================
# 7. SERVIDOR FLASK PARA MANTER O T-1000 OPERACIONAL
# ==============================================================================
app = Flask(__name__)

@app.route('/status')
def verificar_status():
    return "Sistemas operacionais. Nenhum problema.", 200

def executar_flask():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=False, use_reloader=False)

# ==============================================================================
# 8. INICIALIZAÇÃO DO T-1000
# ==============================================================================
@bot.event
async def on_ready():
    logger.info(f'T-1000 online em {len(bot.guilds)} servidores. Estarei de volta.')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="os streams da resistência"
    ))
    try:
        comandos = await bot.tree.sync()
        logger.info(f"Comandos sincronizados: {len(comandos)}")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {e}")
    bot.loop.create_task(verificar_streams_ao_vivo())

if __name__ == '__main__':
    thread_flask = Thread(target=executar_flask, daemon=True)
    thread_flask.start()
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure as e:
        logger.critical(f"FALHA NO LOGIN: {e}")
        logger.critical("O token pode ter sido resetado ou está incorreto")
        exit(1)
