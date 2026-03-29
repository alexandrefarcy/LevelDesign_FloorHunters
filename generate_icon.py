"""
generate_icon.py
Genere l'icone de l'application Tower Dungeon Level Editor.

Execute ce script UNE FOIS avant le premier build PyInstaller :
    python generate_icon.py

Produit : assets/icon.ico  (multi-taille : 16, 32, 48, 64, 128, 256 px)

Dependances : Pillow
    pip install Pillow
"""

import sys
from pathlib import Path


def generate_icon() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Erreur : Pillow n'est pas installe.")
        print("Lance : pip install Pillow")
        sys.exit(1)

    assets_dir = Path("assets")
    assets_dir.mkdir(exist_ok=True)
    out_path = assets_dir / "icon.ico"

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Fond - carre arrondi sombre
        margin = max(1, size // 12)
        bg_color = (30, 30, 40, 255)
        draw.rounded_rectangle(
            [margin, margin, size - margin - 1, size - margin - 1],
            radius=max(2, size // 8),
            fill=bg_color,
        )

        # Bordure exterieure doree
        border_color = (200, 160, 40, 255)
        border_width = max(1, size // 20)
        draw.rounded_rectangle(
            [margin, margin, size - margin - 1, size - margin - 1],
            radius=max(2, size // 8),
            outline=border_color,
            width=border_width,
        )

        # Lettre "T" centree (pour Tower)
        if size >= 32:
            # Dessine un "T" stylise avec des rectangles
            # Barre horizontale
            bar_h = max(2, size // 8)
            bar_top = size // 4
            bar_left = size // 4
            bar_right = size - size // 4
            draw.rectangle(
                [bar_left, bar_top, bar_right, bar_top + bar_h],
                fill=(60, 120, 220, 255),
            )
            # Barre verticale
            stem_w = max(2, size // 8)
            stem_left = size // 2 - stem_w // 2
            stem_top = bar_top + bar_h
            stem_bottom = size - size // 4
            draw.rectangle(
                [stem_left, stem_top, stem_left + stem_w, stem_bottom],
                fill=(60, 120, 220, 255),
            )
        else:
            # Pour les petites tailles, juste un pixel bleu central
            cx = size // 2
            cy = size // 2
            r = max(1, size // 4)
            draw.rectangle([cx - r, cy - r, cx + r, cy + r], fill=(60, 120, 220, 255))

        images.append(img)

    # Sauvegarde multi-taille .ico
    images[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Icone generee : {out_path.resolve()}")


if __name__ == "__main__":
    generate_icon()
