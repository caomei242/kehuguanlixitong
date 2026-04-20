from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "icon-options"
SIZE = 1024
SCALE = 3


def s(value: int) -> int:
    return value * SCALE


def make_canvas(bg: str, inner: str = "#ffffff") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((s(72), s(72), s(952), s(952)), radius=s(214), fill=(36, 48, 80, 62))
    shadow = shadow.filter(ImageFilter.GaussianBlur(s(24)))
    canvas.alpha_composite(shadow)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((s(64), s(56), s(960), s(952)), radius=s(220), fill=bg)
    draw.rounded_rectangle((s(146), s(146), s(878), s(878)), radius=s(128), fill=inner)
    return canvas, draw


def save(canvas: Image.Image, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    icon = canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    icon.save(OUT_DIR / f"{name}.png")


def strawberry(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    draw.ellipse((s(cx - r), s(cy - r), s(cx + r), s(cy + r)), fill="#ff456d")
    draw.ellipse((s(cx - r // 2), s(cy - r // 3), s(cx + r // 2), s(cy + r),), fill="#ff5278")
    for dx, dy in [(-25, -30), (24, -36), (48, 10), (-6, 46), (30, 64)]:
        seed = max(5, r // 14)
        draw.ellipse((s(cx + dx - seed), s(cy + dy - seed), s(cx + dx + seed), s(cy + dy + seed)), fill="#ffd5df")
    draw.polygon([(s(cx - 20), s(cy - r)), (s(cx + 38), s(cy - r - 54)), (s(cx + 48), s(cy - r + 12))], fill="#25a957")
    draw.polygon([(s(cx + 24), s(cy - r)), (s(cx + 92), s(cy - r - 38)), (s(cx + 68), s(cy - r + 28))], fill="#188d46")
    draw.polygon([(s(cx - 34), s(cy - r + 4)), (s(cx - 78), s(cy - r - 38)), (s(cx + 8), s(cy - r - 18))], fill="#2dbb62")


def option_a_network() -> None:
    canvas, draw = make_canvas("#e9f6f0", "#f7fffb")
    # Bold relationship network, no document card silhouette.
    center = (512, 458)
    nodes = [(316, 350, 54), (704, 338, 60), (338, 650, 66), (720, 642, 56), center + (82,)]
    for x, y, _ in nodes[:-1]:
        draw.line((s(center[0]), s(center[1]), s(x), s(y)), fill="#8ed0bc", width=s(22))
    draw.line((s(316), s(350), s(704), s(338)), fill="#b5dfd2", width=s(14))
    draw.line((s(338), s(650), s(720), s(642)), fill="#b5dfd2", width=s(14))
    for x, y, r in nodes:
        color = "#1f9f77" if (x, y) == center else "#7fb8ff"
        draw.ellipse((s(x - r), s(y - r), s(x + r), s(y + r)), fill=color)
    strawberry(draw, 686, 710, 88)
    save(canvas, "A-relationship-network")


def option_b_contact_book() -> None:
    canvas, draw = make_canvas("#edf2ff", "#ffffff")
    # Address book / CRM dossier. Very different from order-card layout.
    draw.rounded_rectangle((s(258), s(220), s(720), s(800)), radius=s(74), fill="#315ecf")
    draw.rounded_rectangle((s(322), s(220), s(768), s(800)), radius=s(74), fill="#f5f8ff")
    draw.rounded_rectangle((s(292), s(286), s(360), s(354)), radius=s(18), fill="#ff4b6e")
    draw.rounded_rectangle((s(292), s(448), s(360), s(516)), radius=s(18), fill="#ff4b6e")
    draw.rounded_rectangle((s(410), s(300), s(676), s(348)), radius=s(24), fill="#cbdafa")
    draw.rounded_rectangle((s(410), s(414), s(690), s(456)), radius=s(21), fill="#dce7ff")
    draw.rounded_rectangle((s(410), s(488), s(650), s(530)), radius=s(21), fill="#dce7ff")
    draw.ellipse((s(488), s(584), s(608), s(704)), fill="#4a7cff")
    draw.rounded_rectangle((s(426), s(684), s(670), s(752)), radius=s(34), fill="#8fb0ff")
    strawberry(draw, 720, 704, 72)
    save(canvas, "B-contact-book")


def option_c_pipeline() -> None:
    canvas, draw = make_canvas("#fff1f4", "#ffffff")
    # Sales funnel / customer stages.
    funnel = [(266, 258), (758, 258), (626, 482), (558, 482), (558, 704), (466, 704), (466, 482), (398, 482)]
    draw.polygon([(s(x), s(y)) for x, y in funnel], fill="#ff4b6e")
    draw.line((s(320), s(330), s(704), s(330)), fill="#ffd0dc", width=s(30))
    draw.line((s(382), s(428), s(642), s(428)), fill="#ffd0dc", width=s(24))
    # Stage dots.
    for x, y, c in [(318, 742, "#4a7cff"), (436, 742, "#6bbf9c"), (554, 742, "#f6b748"), (672, 742, "#315ecf")]:
        draw.ellipse((s(x - 38), s(y - 38), s(x + 38), s(y + 38)), fill=c)
    strawberry(draw, 742, 578, 70)
    save(canvas, "C-sales-funnel")


def option_d_shop_grid() -> None:
    canvas, draw = make_canvas("#ecf7ff", "#ffffff")
    # Store-group customers: grid of stores / software seats.
    colors = ["#4a7cff", "#8fb0ff", "#58c9a7", "#ff4b6e"]
    i = 0
    for row in range(3):
        for col in range(3):
            x = 286 + col * 154
            y = 260 + row * 142
            draw.rounded_rectangle((s(x), s(y), s(x + 104), s(y + 94)), radius=s(24), fill="#f4f8ff")
            draw.rectangle((s(x), s(y), s(x + 104), s(y + 26)), fill=colors[i % len(colors)])
            draw.rounded_rectangle((s(x + 32), s(y + 44), s(x + 72), s(y + 94)), radius=s(12), fill="#dce7ff")
            i += 1
    # Bulk discount stack.
    draw.rounded_rectangle((s(320), s(732), s(704), s(790)), radius=s(29), fill="#315ecf")
    draw.rounded_rectangle((s(374), s(664), s(650), s(710)), radius=s(23), fill="#8fb0ff")
    strawberry(draw, 742, 710, 68)
    save(canvas, "D-shop-grid")


def option_e_handshake() -> None:
    canvas, draw = make_canvas("#f4f1ff", "#ffffff")
    # Cooperation / relationship closing.
    draw.rounded_rectangle((s(238), s(320), s(498), s(546)), radius=s(78), fill="#4a7cff")
    draw.rounded_rectangle((s(526), s(320), s(786), s(546)), radius=s(78), fill="#ff4b6e")
    draw.polygon([(s(442), s(496)), (s(520), s(438)), (s(594), s(520)), (s(520), s(594))], fill="#f6c789")
    draw.polygon([(s(510), s(438)), (s(584), s(496)), (s(510), s(594)), (s(436), s(520))], fill="#f3b978")
    for x, y in [(360, 636), (512, 676), (664, 636)]:
        draw.ellipse((s(x - 46), s(y - 46), s(x + 46), s(y + 46)), fill="#8fb0ff")
    draw.line((s(406), s(636), s(466), s(670)), fill="#b8c9f8", width=s(18))
    draw.line((s(558), s(670), s(618), s(636)), fill="#b8c9f8", width=s(18))
    strawberry(draw, 724, 724, 66)
    save(canvas, "E-partnership")


def option_f_command_center() -> None:
    canvas, draw = make_canvas("#eef4ff", "#ffffff")
    # Operational CRM cockpit / radar target.
    for r, color in [(286, "#eef4ff"), (214, "#dce7ff"), (138, "#bfd1ff")]:
        draw.ellipse((s(512 - r), s(512 - r), s(512 + r), s(512 + r)), fill=color)
    draw.ellipse((s(412), s(412), s(612), s(612)), fill="#315ecf")
    draw.line((s(512), s(512), s(744), s(370)), fill="#4a7cff", width=s(18))
    for x, y, c in [(744, 370, "#ff4b6e"), (332, 430, "#58c9a7"), (402, 716, "#8fb0ff"), (706, 676, "#f6b748")]:
        draw.ellipse((s(x - 42), s(y - 42), s(x + 42), s(y + 42)), fill=c)
    draw.rounded_rectangle((s(324), s(748), s(700), s(802)), radius=s(27), fill="#4a7cff")
    strawberry(draw, 720, 720, 62)
    save(canvas, "F-customer-radar")


def contact_sheet() -> None:
    names = [
        ("A", "relationship-network"),
        ("B", "contact-book"),
        ("C", "sales-funnel"),
        ("D", "shop-grid"),
        ("E", "partnership"),
        ("F", "customer-radar"),
    ]
    thumb = 260
    padding = 34
    label_h = 42
    sheet = Image.new("RGBA", (padding * 4 + thumb * 3, padding * 3 + (thumb + label_h) * 2), "#f5f7fb")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
    for idx, (letter, slug) in enumerate(names):
        row = idx // 3
        col = idx % 3
        x = padding + col * (thumb + padding)
        y = padding + row * (thumb + label_h + padding)
        icon = Image.open(OUT_DIR / f"{letter}-{slug}.png").resize((thumb, thumb), Image.Resampling.LANCZOS)
        sheet.alpha_composite(icon, (x, y))
        draw.text((x + 6, y + thumb + 8), f"{letter}  {slug}", fill="#20304a", font=font)
    sheet.convert("RGB").save(OUT_DIR / "contact-sheet.png")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    option_a_network()
    option_b_contact_book()
    option_c_pipeline()
    option_d_shop_grid()
    option_e_handshake()
    option_f_command_center()
    contact_sheet()


if __name__ == "__main__":
    main()
