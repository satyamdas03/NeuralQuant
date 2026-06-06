"""
Generate NeuralQuant PWA icons from the master SVG.

Requires: pip install Pillow cairosvg
Usage:   python generate_icons.py

Creates:
  - icon-16x16.png
  - icon-32x32.png
  - icon-180x180.png   (apple-touch-icon)
  - icon-192x192.png
  - icon-512x512.png
  - favicon.ico          (32x32, multi-size)
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

# Brand colors
BG_DARK = (13, 20, 37)       # #0D1425
BG_DARK_END = (10, 15, 30)   # #0A0F1E
ACCENT = (0, 255, 178)        # #00FFB2
ACCENT_END = (0, 201, 167)    # #00C9A7
WHITE = (255, 255, 255)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB colors."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def create_icon(size):
    """Create a NeuralQuant icon at the given size."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background rounded rect
    radius = int(size * 96 / 512)
    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius,
        fill=BG_DARK,
        outline=(*ACCENT, 77),  # 30% opacity
        width=max(1, int(size * 3 / 512))
    )

    # Decorative neural network nodes
    node_r = max(1, int(size * 4 / 512))
    node_opacity = 38  # ~15% of 255
    node_positions = [
        (0.234, 0.273),  # top-left
        (0.766, 0.273),  # top-right
        (0.234, 0.727),  # bottom-left
        (0.766, 0.727),  # bottom-right
    ]
    for nx, ny in node_positions:
        px, py = int(nx * size), int(ny * size)
        draw.ellipse(
            [px - node_r, py - node_r, px + node_r, py + node_r],
            fill=(*ACCENT, node_opacity)
        )

    # Neural connections
    line_w = max(1, int(size * 1 / 512))
    line_opacity = 20  # ~8% of 255
    center_x, center_y = size // 2, size // 2
    for nx, ny in node_positions:
        px, py = int(nx * size), int(ny * size)
        draw.line(
            [(px, py), (center_x, center_y)],
            fill=(*ACCENT, line_opacity),
            width=line_w
        )

    # Draw NQ monogram
    # For small sizes, use simpler rendering
    font_size = int(size * 240 / 512)

    # Try to find a suitable font
    font = None
    font_paths = [
        # Windows
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        # macOS
        "/System/Library/Fonts/SFNSText-Bold.otf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except (IOError, OSError):
                continue

    if font is None:
        # Fallback to default
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Draw "NQ" text with glow effect
    text = "NQ"

    # Calculate text position for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (size - text_w) // 2 - bbox[0]
    text_y = (size - text_h) // 2 - bbox[1]

    # Glow layer (draw text larger/offset for glow)
    glow_size = max(2, int(size * 3 / 512))
    glow_alpha = int(255 * 0.3)  # 30% opacity

    # Create glow overlay
    glow_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    # Draw glow text slightly larger/offset
    for dx in range(-glow_size, glow_size + 1):
        for dy in range(-glow_size, glow_size + 1):
            if dx * dx + dy * dy <= glow_size * glow_size:
                glow_draw.text(
                    (text_x + dx, text_y + dy),
                    text,
                    font=font,
                    fill=(*ACCENT, glow_alpha)
                )
    img = Image.alpha_composite(img, glow_img)
    draw = ImageDraw.Draw(img)

    # Main text - gradient approximation: draw in accent color
    draw.text((text_x, text_y), text, font=font, fill=ACCENT)

    return img


def create_favicon(sizes=None):
    """Create a multi-size favicon.ico."""
    if sizes is None:
        sizes = [(16, 16), (32, 32), (48, 48)]
    images = []
    for w, h in sizes:
        icon = create_icon(w)
        # Convert RGBA to RGB for ICO (ICO doesn't always handle alpha well)
        rgb_icon = Image.new('RGB', icon.size, BG_DARK)
        rgb_icon.paste(icon, mask=icon.split()[3])
        images.append(rgb_icon)
    return images


def main():
    print("Generating NeuralQuant PWA icons...")

    # Generate PNG icons
    png_sizes = [
        (16, 16, "icon-16x16.png"),
        (32, 32, "icon-32x32.png"),
        (180, 180, "apple-touch-icon.png"),
        (192, 192, "icon-192.png"),
        (512, 512, "icon-512.png"),
    ]

    for w, h, filename in png_sizes:
        print(f"  Creating {filename} ({w}x{h})...")
        icon = create_icon(w)
        filepath = os.path.join(SCRIPT_DIR, filename)
        icon.save(filepath, 'PNG')
        print(f"    Saved: {filepath}")

    # Generate favicon.ico
    print("  Creating favicon.ico (multi-size: 16x16, 32x32, 48x48)...")
    favicon_images = create_favicon()
    # Find the web app root — icons/ is inside public/, which is inside apps/web/
    # SCRIPT_DIR = .../apps/web/public/icons
    # Going up 2 levels: icons -> public -> apps/web
    web_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
    favicon_path = os.path.join(web_dir, "src", "app", "favicon.ico")
    # Also save to public/icons for reference
    favicon_images[1].save(
        favicon_path,
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=favicon_images
    )
    print(f"    Saved: {favicon_path}")

    # Also save a copy to public root for browsers that look for /favicon.ico
    public_favicon = os.path.join(web_dir, "public", "favicon.ico")
    favicon_images[1].save(
        public_favicon,
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=favicon_images
    )
    print(f"    Saved: {public_favicon}")

    print("\nAll icons generated successfully!")
    print("\nGenerated files:")
    for w, h, filename in png_sizes:
        filepath = os.path.join(SCRIPT_DIR, filename)
        size_kb = os.path.getsize(filepath) / 1024
        print(f"  {filename}: {w}x{h} ({size_kb:.1f} KB)")
    print(f"  favicon.ico: multi-size (16, 32, 48)")


if __name__ == "__main__":
    main()