"""Generate assets/vaultlog.ico (a padlock on a rounded square). Requires Pillow.

Run once; the generated icon is committed to the repo.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "vaultlog.ico"
S = 1024  # draw large, downscale for crisp edges


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=220, fill=(32, 46, 70))
    # shackle
    d.rounded_rectangle((330, 190, 694, 600), radius=182, outline=(230, 236, 245), width=78)
    # body
    d.rounded_rectangle((250, 460, 774, 860), radius=70, fill=(242, 182, 60))
    # keyhole
    d.ellipse((462, 570, 562, 670), fill=(32, 46, 70))
    d.polygon([(492, 640), (532, 640), (550, 770), (474, 770)], fill=(32, 46, 70))
    return img


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    draw().save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {OUT}")
