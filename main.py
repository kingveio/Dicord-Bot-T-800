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

bot = T800Bot()

if __name__ == "__main__":
    Config.validate()
    bot.run(Config.DISCORD_TOKEN)
