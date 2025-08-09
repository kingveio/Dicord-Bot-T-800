@bot.tree.command(name="youtube_add", description="Adiciona um canal do YouTube para notificar novos vídeos e lives")
@app_commands.describe(
    youtube_url="URL do canal do YouTube (ex: https://www.youtube.com/@nome_do_canal)",
    notification_channel="O canal do Discord para enviar as notificações",
    discord_member="O membro do Discord para dar o cargo 'Ao Vivo' (opcional)"
)
@app_commands.checks.has_permissions(administrator=True)
async def youtube_add_command(
    interaction: discord.Interaction,
    youtube_url: str,
    notification_channel: discord.TextChannel,
    discord_member: Optional[discord.Member] = None
):
    try:
        # Responder imediatamente para evitar timeout
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        logger.info(f"Tentando adicionar canal YouTube: {youtube_url}")
        
        if not youtube_url.startswith(("http://", "https://")):
            youtube_url = f"https://{youtube_url}"

        # Feedback imediato para o usuário
        await interaction.followup.send("🔍 Buscando informações do canal no YouTube...", ephemeral=True)
        
        youtube_id = await bot.youtube_api.get_channel_id_from_url(youtube_url)
        if not youtube_id:
            logger.error(f"Não foi possível encontrar ID para a URL: {youtube_url}")
            return await interaction.followup.send(
                "❌ Não foi possível identificar o canal a partir da URL fornecida. Verifique:"
                "\n- Se a URL está correta"
                "\n- Se o canal existe"
                "\n- Se é uma URL pública",
                ephemeral=True
            )

        logger.info(f"Channel ID encontrado: {youtube_id}")
        
        data = await get_cached_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in data.get("youtube_channels", {}):
            data["youtube_channels"][guild_id] = {}
        
        if youtube_id in data["youtube_channels"][guild_id]:
            return await interaction.followup.send(
                "⚠️ Este canal do YouTube já está registrado!\n"
                f"Notificações sendo enviadas para: <#{data['youtube_channels'][guild_id][youtube_id]['notification_channel_id']}>",
                ephemeral=True
            )

        data["youtube_channels"][guild_id][youtube_id] = {
            "notification_channel_id": str(notification_channel.id),
            "last_video_id": None,
            "discord_user_id": str(discord_member.id) if discord_member else None
        }

        logger.info(f"Configuração salva: {data['youtube_channels'][guild_id][youtube_id]}")
        
        await set_cached_data(data, bot.drive_service)
        
        response_msg = (
            f"✅ **Canal adicionado com sucesso!**\n\n"
            f"🔗 **Canal:** {youtube_url}\n"
            f"🆔 **ID:** `{youtube_id}`\n"
            f"🔔 **Notificações em:** {notification_channel.mention}\n"
        )
        
        if discord_member:
            response_msg += f"👤 **Usuário vinculado:** {discord_member.mention}\n"
            live_role = await get_or_create_live_role(interaction.guild)
            if live_role:
                response_msg += f"🎮 **Cargo 'Ao Vivo':** {live_role.mention}"
        
        await interaction.followup.send(response_msg, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Erro no comando youtube_add: {str(e)}", exc_info=True)
        try:
            await interaction.followup.send(
                "❌ **Erro ao processar solicitação**\n"
                "Ocorreu um erro inesperado. Por favor, tente novamente mais tarde.",
                ephemeral=True
            )
        except Exception as followup_error:
            logger.error(f"Erro ao enviar mensagem de erro: {followup_error}")
