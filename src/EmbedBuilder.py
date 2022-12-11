import discord


class EmbedBuilder:
    def __init__(
        self, title: str, description: str, color: int = 0x18E299, image: str = None
    ) -> None:
        self.title = title
        self.description = description
        self.color = color
        self.footer = "Powered by Mintlify"
        self.image = image

    def build(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title, description=self.description, color=self.color
        )
        if self.image:
            embed.set_image(url=self.image)
        embed.set_footer(text=self.footer)
        return embed
