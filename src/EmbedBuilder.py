import discord


class EmbedBuilder:
    def __init__(self, title, description, color=0x18E299, image=None) -> None:
        self.title: str | None = title
        self.description: str | None = description
        self.color = color
        self.footer = "Powered by Mintlify"
        self.image: str | None = image

    def build(self):
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=self.color,
        )
        if self.image:
            embed.set_image(url=self.image)
        embed.set_footer(text=self.footer)
        return embed
