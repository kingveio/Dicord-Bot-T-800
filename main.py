class T800Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # Inicializa o DataManager
        self.data_manager = DataManager()
        self.data_manager.bot = self  # Permite acesso ao bot
        
        # Inicializa APIs
        self.twitch_api = TwitchAPI()
        self.youtube_api = YouTubeAPI()

    async def setup_hook(self):
        await self.data_manager.load()  # Carrega os dados
        await self.load_extension("cogs.live_monitor")
        await self.load_extension("cogs.live_monitor")
        await self.load_extension("cogs.youtube")
        await self.load_extension("cogs.twitch")
        await self.load_extension("cogs.settings")
        try:
        # Carrega dados primeiro
        await self.data_manager.load()
        
        # Depois carrega os cogs
        cogs = [
            "cogs.live_monitor",
            "cogs.youtube",
            "cogs.twitch",
            "cogs.settings"
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog carregado: {cog}")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar {cog}: {e}")
                
    except Exception as e:
        logger.critical(f"Falha no setup: {e}", exc_info=True)
        raise
bot = T800Bot()

if __name__ == "__main__":
    Config.validate()
    bot.run(Config.DISCORD_TOKEN)
