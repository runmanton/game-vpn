"""Design GameVPN icon and installer wizard images.

Generates:
  - assets/icon.ico              (multi-size app icon)
  - installer/wizard_image.bmp   (164x314, welcome/finish pages)
  - installer/wizard_small.bmp   (55x58, top-right of other pages)

Style: dark navy -> cyan gradient with 3-peer network topology graphic.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

# --- Color palette ------------------------------------------------------
DARK_NAVY = (10, 20, 40)
MID_BLUE = (20, 50, 100)
DEEP_PURPLE = (30, 25, 70)
CYAN = (0, 212, 255)
PEER_GREEN = (0, 255, 180)
WHITE = (255, 255, 255)

# --- Helpers ------------------------------------------------------------

def diagonal_gradient(size, top_left, bottom_right):
    """Diagonal gradient from top-left to bottom-right corner."""
    w, h = size
    img = Image.new('RGB', size, top_left)
    px = img.load()
    diag_max = w + h
    for y in range(h):
        for x in range(w):
            t = (x + y) / diag_max
            r = int(top_left[0] + (bottom_right[0] - top_left[0]) * t)
            g = int(top_left[1] + (bottom_right[1] - top_left[1]) * t)
            b = int(top_left[2] + (bottom_right[2] - top_left[2]) * t)
            px[x, y] = (r, g, b)
    return img


def rounded_mask(size, radius):
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return mask


def find_font(size, bold=True):
    """Find a usable system font for the requested point size."""
    candidates = [
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibrib.ttf' if bold else 'C:/Windows/Fonts/calibri.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


# --- Network topology graphic ------------------------------------------

def draw_network_graphic(canvas, center, radius_px):
    """Draw 3 peer nodes connected to a central hub at given center.

    radius_px = orbit radius (distance from center to peer nodes).
    """
    draw = ImageDraw.Draw(canvas, 'RGBA')
    cx, cy = center
    line_w = max(2, radius_px // 20)
    node_r = max(3, radius_px // 6)
    hub_r = max(4, radius_px // 4)

    # Peer node positions (3 nodes, top + bottom-left + bottom-right)
    angles = [-math.pi / 2,
              -math.pi / 2 + 2 * math.pi / 3,
              -math.pi / 2 + 4 * math.pi / 3]
    nodes = [
        (cx + int(radius_px * math.cos(a)),
         cy + int(radius_px * math.sin(a)))
        for a in angles
    ]

    # Connection lines between peers (triangle edges, lighter)
    for i in range(3):
        draw.line(
            [nodes[i], nodes[(i + 1) % 3]],
            fill=(0, 212, 255, 140),
            width=line_w,
        )

    # Lines from hub to each peer (stronger)
    for n in nodes:
        draw.line([(cx, cy), n], fill=CYAN, width=line_w + 1)

    # Central hub glow + solid
    draw.ellipse(
        [cx - int(hub_r * 1.6), cy - int(hub_r * 1.6),
         cx + int(hub_r * 1.6), cy + int(hub_r * 1.6)],
        fill=(0, 212, 255, 60),
    )
    draw.ellipse(
        [cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
        fill=WHITE,
    )

    # Peer nodes glow + solid
    for nx, ny in nodes:
        draw.ellipse(
            [nx - int(node_r * 1.8), ny - int(node_r * 1.8),
             nx + int(node_r * 1.8), ny + int(node_r * 1.8)],
            fill=(0, 255, 180, 70),
        )
        draw.ellipse(
            [nx - node_r, ny - node_r, nx + node_r, ny + node_r],
            fill=PEER_GREEN,
        )


# --- Icon (rounded square) ---------------------------------------------

def render_icon(size):
    """Render a square app icon (rounded) at the given pixel size."""
    scale = 4 if size <= 128 else 2
    big = size * scale

    # Background gradient
    bg = diagonal_gradient((big, big), DARK_NAVY, MID_BLUE).convert('RGBA')

    # Soft purple radial accent (corner highlight)
    accent = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(accent)
    for i in range(8, 0, -1):
        alpha = int(180 / i)
        r = big * (0.3 + i * 0.06)
        adraw.ellipse(
            [big * 0.75 - r, big * 0.15 - r,
             big * 0.75 + r, big * 0.15 + r],
            fill=(120, 80, 200, alpha // 6),
        )
    bg = Image.alpha_composite(bg, accent)

    # Rounded mask
    mask = rounded_mask((big, big), radius=big // 5)
    rounded = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    rounded.paste(bg, (0, 0), mask)

    # Network graphic
    draw_network_graphic(rounded, (big // 2, big // 2),
                         radius_px=int(big * 0.28))

    # Downscale with LANCZOS for smooth edges
    return rounded.resize((size, size), Image.LANCZOS)


def build_icon_ico(path):
    sizes = [256, 128, 64, 48, 32, 16]  # largest first
    images = [render_icon(s) for s in sizes]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    images[0].save(
        path, format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f'  [OK] {path}')


# --- Wizard images (BMP, no alpha) -------------------------------------

def build_wizard_image(path, size=(164, 314)):
    """Large left-side image shown on Welcome/Finish pages."""
    w, h = size
    scale = 3
    bw, bh = w * scale, h * scale

    bg = diagonal_gradient((bw, bh), DARK_NAVY, DEEP_PURPLE).convert('RGBA')

    # Subtle dot pattern (network feel)
    dots = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dots)
    step = bw // 14
    for y in range(step, bh, step):
        for x in range(step, bw, step):
            r = max(1, bw // 240)
            ddraw.ellipse([x - r, y - r, x + r, y + r],
                          fill=(0, 212, 255, 35))
    bg = Image.alpha_composite(bg, dots)

    # Central network graphic (upper area)
    gx, gy = bw // 2, int(bh * 0.28)
    draw_network_graphic(bg, (gx, gy), radius_px=int(bw * 0.30))

    # Title text "GameVPN"
    draw = ImageDraw.Draw(bg)
    title_font = find_font(int(bw * 0.17), bold=True)
    title = 'GameVPN'
    tw_l, th_t, tw_r, th_b = draw.textbbox((0, 0), title, font=title_font)
    tw = tw_r - tw_l
    th = th_b - th_t
    tx = (bw - tw) // 2 - tw_l
    ty = int(bh * 0.58)
    # Drop shadow
    draw.text((tx + 4, ty + 4), title, font=title_font, fill=(0, 0, 0, 200))
    draw.text((tx, ty), title, font=title_font, fill=WHITE)

    # Tagline (bigger, brighter, more spacing)
    sub_font = find_font(int(bw * 0.075), bold=False)
    sub = 'Virtual LAN for Gaming'
    sw_l, sh_t, sw_r, sh_b = draw.textbbox((0, 0), sub, font=sub_font)
    sw = sw_r - sw_l
    sx = (bw - sw) // 2 - sw_l
    sy = ty + th + int(bh * 0.04)
    draw.text((sx, sy), sub, font=sub_font, fill=(120, 230, 255, 255))

    # Bottom accent line
    line_y = int(bh * 0.93)
    draw.line(
        [int(bw * 0.20), line_y, int(bw * 0.80), line_y],
        fill=(0, 212, 255, 220),
        width=max(2, bw // 200),
    )

    # Attribution at very bottom
    attr_font = find_font(int(bw * 0.048), bold=False)
    attr = 'by Luong Manh Tuan'
    aw_l, ah_t, aw_r, ah_b = draw.textbbox((0, 0), attr, font=attr_font)
    aw = aw_r - aw_l
    ax = (bw - aw) // 2 - aw_l
    ay = line_y + int(bh * 0.015)
    draw.text((ax, ay), attr, font=attr_font, fill=(140, 170, 210, 255))

    # Downscale and save as BMP (RGB)
    final = bg.convert('RGB').resize((w, h), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    final.save(path, 'BMP')
    print(f'  [OK] {path}')


def build_wizard_small(path, size=(55, 58)):
    """Small top-right icon shown on inner wizard pages."""
    w, h = size
    scale = 8
    bw, bh = w * scale, h * scale

    bg = diagonal_gradient((bw, bh), DARK_NAVY, MID_BLUE).convert('RGBA')
    draw_network_graphic(bg, (bw // 2, bh // 2),
                         radius_px=int(min(bw, bh) * 0.34))

    final = bg.convert('RGB').resize((w, h), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    final.save(path, 'BMP')
    print(f'  [OK] {path}')


# --- Main ---------------------------------------------------------------

def main():
    print('Generating GameVPN assets...')
    build_icon_ico('assets/icon.ico')
    build_wizard_image('installer/wizard_image.bmp')
    build_wizard_small('installer/wizard_small.bmp')
    print('Done.')


if __name__ == '__main__':
    main()
