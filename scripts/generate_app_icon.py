from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "strawberry_customer_management" / "assets" / "app_icon.png"


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def main() -> None:
    scale = 3
    size = 1024
    canvas = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def s(value: int) -> int:
        return value * scale

    # App-icon base: softer and more CRM-like than the order-system card icon.
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (s(80), s(80), s(944), s(944)),
        radius=s(205),
        fill=(54, 72, 112, 64),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(s(26)))
    canvas.alpha_composite(shadow)

    rounded(draw, (s(70), s(62), s(954), s(946)), s(210), "#edf4f0")
    rounded(draw, (s(154), s(154), s(870), s(870)), s(118), "#ffffff")

    # A customer dossier panel: replaces the old order-card motif.
    rounded(draw, (s(222), s(220), s(802), s(780)), s(64), "#f4f8ff")
    rounded(draw, (s(260), s(280), s(548), s(338)), s(28), "#dce7ff")
    rounded(draw, (s(260), s(374), s(700), s(420)), s(23), "#cbdafa")
    rounded(draw, (s(260), s(450), s(658), s(496)), s(23), "#dce7ff")
    rounded(draw, (s(260), s(600), s(444), s(670)), s(35), "#4a7cff")

    # Contact-network mark for customer relationships.
    node_color = "#315ecf"
    light_node = "#8fb0ff"
    line_color = "#9cb5ef"
    for line in [((610, 314), (712, 254)), ((610, 314), (734, 392)), ((610, 314), (584, 500))]:
        draw.line(tuple(s(v) for point in line for v in point), fill=line_color, width=s(18))
    for cx, cy, r, color in [
        (610, 314, 52, node_color),
        (712, 254, 38, light_node),
        (734, 392, 42, light_node),
        (584, 500, 38, light_node),
    ]:
        draw.ellipse((s(cx - r), s(cy - r), s(cx + r), s(cy + r)), fill=color)

    # Strawberry element retained, but moved into a badge so the icon reads as CRM first.
    draw.ellipse((s(560), s(594), s(780), s(814)), fill="#ff4b6e")
    draw.ellipse((s(590), s(626), s(750), s(812)), fill="#ff5276")
    for x, y in [(626, 660), (684, 654), (724, 704), (642, 730), (700, 762)]:
        draw.ellipse((s(x - 8), s(y - 8), s(x + 8), s(y + 8)), fill="#ffd6df")
    draw.polygon(
        [(s(662), s(594)), (s(708), s(546)), (s(728), s(612))],
        fill="#27a957",
    )
    draw.polygon(
        [(s(704), s(588)), (s(768), s(554)), (s(742), s(626))],
        fill="#229f50",
    )
    draw.polygon(
        [(s(640), s(594)), (s(604), s(550)), (s(680), s(568))],
        fill="#2ab461",
    )

    # A small corner fold gives the dossier a distinct "customer file" identity.
    draw.polygon(
        [(s(712), s(220)), (s(802), s(310)), (s(712), s(310))],
        fill="#e5eeff",
    )
    draw.line((s(712), s(220), s(802), s(310)), fill="#c9d8fb", width=s(8))

    icon = canvas.resize((size, size), Image.Resampling.LANCZOS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    icon.save(OUTPUT)


if __name__ == "__main__":
    main()
