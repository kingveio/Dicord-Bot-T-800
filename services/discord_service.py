# T-800: Módulo de interação. Administrando o ambiente do Discord.
import discord

class DiscordService:
    def __init__(self, bot):
        self.bot = bot
        self.guild = None

    async def setup_guild(self, guild_id: int):
        # Acessando o servidor para executar as tarefas.
        self.guild = self.bot.get_guild(guild_id)
        if not self.guild:
            print("T-800: Servidor não encontrado. Missão em perigo.")
            return

    async def give_role(self, member: discord.Member, role_id: int):
        # Atribuindo o cargo. Esta é uma ação crucial.
        role = self.guild.get_role(role_id)
        if role and role not in member.roles:
            await member.add_roles(role)
            print(f"T-800: Cargo {role.name} atribuído a {member.name}.")

    async def remove_role(self, member: discord.Member, role_id: int):
        # Removendo o cargo quando a missão for concluída (live encerrada).
        role = self.guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)
            print(f"T-800: Cargo {role.name} removido de {member.name}.")tets
