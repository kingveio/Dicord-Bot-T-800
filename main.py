# main.py
# T-800: Bot Discord para monitoramento de streamers.
# Interage com a classe DataManager para persistência de dados.

import os
import discord
import asyncio
import logging
from data_manager import DataManager # Importa a classe do nosso Canvas
from discord import app_commands

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações do Discord
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    logger.error("❌ Variável de ambiente 'DISCORD_TOKEN' não definida. O bot não pode ser iniciado.")
    exit()

# Definir intents (intenções) para o bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class BotClient(discord.Client):
    """
    Cliente principal do bot.
    """
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.data_manager: DataManager = None

    async def on_ready(self):
        """
        Evento disparado quando o bot está pronto e conectado ao Discord.
        """
        logger.info(f'✅ Bot conectado como {self.user} (ID: {self.user.id})')
        
        # Sincronizar comandos da árvore de comandos
        synced = await self.tree.sync()
        logger.info(f'🔁 {len(synced)} comandos sincronizados')

        # Inicializar a classe DataManager de forma assíncrona
        self.data_manager = await DataManager.create()
        
        # Iniciar a tarefa de verificação de streams em segundo plano
        self.loop.create_task(self.check_streams_background_task())

    async def check_streams_background_task(self):
        """
        Tarefa em segundo plano para verificar streams ao vivo.
        É um exemplo simplificado e precisa ser implementado.
        """
        await self.wait_until_ready()
        while not self.is_closed():
            logger.info("🔄 Verificando streams...")
            
            # TODO: Implementar a lógica real de verificação de streams aqui.
            # Exemplo: chamar a API da Twitch ou YouTube
            
            # Acessar os dados da guilda
            for guild_id_str, guild_data in self.data_manager.data.get("guilds", {}).items():
                guild = self.get_guild(int(guild_id_str))
                if guild:
                    # Enviar uma mensagem de teste para o canal de notificação
                    notify_channel_id = guild_data['config']['notify_channel']
                    if notify_channel_id:
                        channel = guild.get_channel(int(notify_channel_id))
                        if channel:
                            logger.debug(f"ℹ️ Verificando guilda {guild.name}")
                            # await channel.send("Teste: Verificação de stream concluída.")

            await asyncio.sleep(300)  # Espera 5 minutos

# Cria uma instância do bot
client = BotClient(intents=intents)

@client.tree.command(name="link", description="Vincula seu canal de streamer com o bot.")
@app_commands.describe(plataforma="A plataforma do seu canal (twitch, youtube).", canal="O nome do seu canal.")
async def link_channel_command(interaction: discord.Interaction, plataforma: str, canal: str):
    """
    Comando para vincular o canal de um usuário.
    """
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    if plataforma.lower() not in ["twitch", "youtube"]:
        await interaction.response.send_message("❌ Plataforma inválida. Use 'twitch' ou 'youtube'.", ephemeral=True)
        return
        
    success = await client.data_manager.link_user_channel(guild_id, user_id, plataforma, canal)
    
    if success:
        await interaction.response.send_message(
            f"✅ Seu canal do {plataforma} ({canal}) foi vinculado com sucesso! Agora você receberá notificações.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Ocorreu um erro ao vincular seu canal. Tente novamente mais tarde.",
            ephemeral=True
        )

@client.tree.command(name="unlink", description="Desvincula seu canal de uma plataforma.")
@app_commands.describe(plataforma="A plataforma que você deseja desvincular (twitch, youtube).")
async def unlink_channel_command(interaction: discord.Interaction, plataforma: str):
    """
    Comando para desvincular o canal de um usuário.
    """
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    if plataforma.lower() not in ["twitch", "youtube"]:
        await interaction.response.send_message("❌ Plataforma inválida. Use 'twitch' ou 'youtube'.", ephemeral=True)
        return

    success = await client.data_manager.remove_user_platform(guild_id, user_id, plataforma)
    
    if success:
        await interaction.response.send_message(
            f"✅ Seu canal do {plataforma} foi desvinculado com sucesso.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Você não tem um canal do {plataforma} vinculado.",
            ephemeral=True
        )

@client.tree.command(name="status", description="Exibe os canais que você vinculou.")
async def status_command(interaction: discord.Interaction):
    """
    Comando para exibir os canais vinculados pelo usuário.
    """
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    user_platforms = client.data_manager.get_user_platforms(guild_id, user_id)
    
    twitch_channel = user_platforms.get("twitch")
    youtube_channel = user_platforms.get("youtube")
    
    response = "ℹ️ **Seus canais vinculados:**\n"
    if twitch_channel:
        response += f"Twitch: `{twitch_channel}`\n"
    if youtube_channel:
        response += f"YouTube: `{youtube_channel}`\n"
    
    if not twitch_channel and not youtube_channel:
        response = "❌ Você não tem nenhum canal vinculado. Use `/link` para começar."
        
    await interaction.response.send_message(response, ephemeral=True)

# Executar o bot
client.run(DISCORD_TOKEN, log_handler=None)
