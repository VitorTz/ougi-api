from src.constants import Constants
from random import Random
import hashlib


_CENTER_SHAPES = (
    '<rect width="100" height="100" rx="18"/>',
    '<polygon points="50,5 95,27 95,73 50,95 5,73 5,27"/>',
    '<circle cx="50" cy="50" r="47"/>',
    '<polygon points="50,5 61,36 95,36 68,57 79,92 50,71 21,92 32,57 5,36 39,36"/>',
    '<polygon points="50,3 97,50 50,97 3,50"/>',
    '<circle cx="50" cy="50" r="47"/><circle cx="50" cy="50" r="20" fill="{bg}"/>',
    '<polygon points="20,5 80,5 95,50 80,95 20,95 5,50"/>',
    '<rect width="100" height="100" rx="18"/><rect x="22" y="22" width="56" height="56" rx="8" fill="{bg}"/>',
    '<polygon points="50,5 95,27 95,73 50,95 5,73 5,27"/><polygon points="50,28 73,40 73,60 50,72 27,60 27,40" fill="{bg}"/>',
    '<path d="M8,50 Q50,5 92,50 Q50,95 8,50 Z"/>',
    '<path d="M50,5 L90,25 L90,75 L50,95 L10,75 L10,25 Z"/>',
    '<rect x="8" y="8" width="84" height="84" rx="42"/>'
)

_EDGE_SHAPES = (
    '<polygon points="50,0 100,100 0,100"/>',
    '<path d="M0,100 A50,50 0 0,1 100,100 Z"/>',
    '<polygon points="50,0 100,50 100,100 50,50 0,100 0,50"/>',
    '<path d="M0,100 Q50,0 100,100 Z"/>',
    '<circle cx="50" cy="72" r="36"/>',
    '<polygon points="0,100 50,0 100,100 50,68"/>',
    '<polygon points="0,100 0,50 50,50 50,0 100,0 100,100"/>',
    '<rect x="15" y="50" width="70" height="50" rx="10"/>',
    '<path d="M18,100 L50,12 L82,100 Z"/>',
    '<ellipse cx="50" cy="78" rx="44" ry="28"/>',
    '<path d="M0,100 L0,55 Q50,0 100,55 L100,100 Z"/>',
    '<polygon points="10,100 40,30 60,30 90,100"/>'
)

_CORNER_SHAPES = (
    '<polygon points="0,0 100,0 0,100"/>',
    '<path d="M0,0 L100,0 A100,100 0 0,0 0,100 Z"/>',
    '<polygon points="0,0 68,0 0,68"/>',
    '<polygon points="0,0 100,0 100,28 28,28 28,100 0,100"/>',
    '<circle cx="2" cy="2" r="72"/>',
    '<rect width="58" height="58" rx="12"/>',
    '<path d="M0,0 Q100,0 100,100 Q0,100 0,0 Z"/>',
    '<polygon points="0,0 50,0 100,50 100,100 50,100 0,50"/>',
    '<path d="M0,0 L65,0 Q100,0 100,35 L100,100 L0,100 Z"/>',
    '<ellipse cx="0" cy="0" rx="88" ry="88"/>',
    '<rect width="42" height="42"/><rect x="58" y="58" width="42" height="42"/>',
    '<polygon points="0,0 100,0 100,18 18,18 18,100 0,100"/>'
)

_BG_ANGLES = ((0, 0, 900, 0), (0, 0, 0, 300), (0, 0, 900, 300), (900, 0, 0, 300))
_PALETTE_IDX = (0.0, 1.0)  # stop offsets for gradients
_ACCENT_OFFSETS = (180, 120, 210, 60)
_SHAPE_TYPES = ('circle', 'ring', 'line', 'triangle')


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Converte HSL para hex RGB. Otimizado para casos especiais."""
    h_n = (h % 360) / 360.0
    
    # Caso especial: grayscale
    if s == 0:
        v = int(round(l * 255))
        return f"#{v:02x}{v:02x}{v:02x}"

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def _hue2rgb(t: float) -> float:
        t = (t + 1.0) % 1.0  # Modulo otimizado
        if t < 0.16666667:
            return p + (q - p) * 6.0 * t
        if t < 0.5:
            return q
        if t < 0.66666667:
            return p + (q - p) * (0.66666667 - t) * 6.0
        return p

    r = int(round(_hue2rgb(h_n) * 255))
    g = int(round(_hue2rgb(h_n - 0.33333333) * 255))
    b = int(round(_hue2rgb(h_n + 0.33333333) * 255))
    
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_palette(hashed: str) -> tuple:
    """
    Derive 5-color palette from MD5 hash.
    Returns: (bg, primary, primary_highlight, accent, accent_highlight)
    """
    h0, h2, h3, h4 = int(hashed[0:2], 16), int(hashed[2], 16), int(hashed[3], 16), int(hashed[4], 16)
    
    hue = h0 / 255.0 * 360
    sv = h2 / 15.0
    lv = h3 / 15.0

    bg = _hsl_to_hex(hue, 0.20 + sv * 0.25, 0.08 + lv * 0.10)
    primary = _hsl_to_hex(hue, 0.55 + sv * 0.35, 0.52 + lv * 0.24)
    primary_hi = _hsl_to_hex(hue, 0.40 + sv * 0.25, 0.74 + lv * 0.16)
    
    aoff = _ACCENT_OFFSETS[h4 % 4]
    ah = (hue + aoff) % 360
    accent = _hsl_to_hex(ah, 0.50 + sv * 0.30, 0.56 + lv * 0.22)
    accent_hi = _hsl_to_hex(ah, 0.38 + sv * 0.22, 0.75 + lv * 0.14)

    return bg, primary, primary_hi, accent, accent_hi


def _cell_svg(shape: str, fill: str, tx: int, ty: int, rot: int = 0) -> str:
    """Gera célula SVG com transform."""
    return f'<g transform="translate({tx},{ty}) rotate({rot},50,50)" fill="{fill}">{shape}</g>'


def generate_avatar_identicon(identifier: str, size: int = 120) -> str:
    """
    Gera identicon SVG simétrico com paleta dinâmica e gradientes.
    """
    hashed = hashlib.md5(identifier.encode()).hexdigest()
    bg, pri, pri_hi, acc, acc_hi = _build_palette(hashed)

    ic = int(hashed[6], 16) % len(_CENTER_SHAPES)
    ie = int(hashed[7], 16) % len(_EDGE_SHAPES)
    ik = int(hashed[8], 16) % len(_CORNER_SHAPES)

    e_fill = "url(#gp)" if int(hashed[9], 16) & 1 else "url(#ga)"
    k_fill = "url(#gp)" if int(hashed[10], 16) & 1 else "url(#ga)"

    center_shape = _CENTER_SHAPES[ic].replace("{bg}", bg)
    edge_shape = _EDGE_SHAPES[ie]
    corner_shape = _CORNER_SHAPES[ik]

    # Cells em ordem: center, 4 edges, 4 corners
    cells = [
        _cell_svg(center_shape, "url(#gp)", 100, 100),
        _cell_svg(edge_shape, e_fill, 100, 0, 0),
        _cell_svg(edge_shape, e_fill, 200, 100, 90),
        _cell_svg(edge_shape, e_fill, 100, 200, 180),
        _cell_svg(edge_shape, e_fill, 0, 100, 270),
        _cell_svg(corner_shape, k_fill, 0, 0, 0),
        _cell_svg(corner_shape, k_fill, 200, 0, 90),
        _cell_svg(corner_shape, k_fill, 200, 200, 180),
        _cell_svg(corner_shape, k_fill, 0, 200, 270)
    ]

    body = "\n    ".join(cells)

    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="{size}" height="{size}">
<defs>
<linearGradient id="gp" x1="0" y1="0" x2="100" y2="100" gradientUnits="userSpaceOnUse">
<stop offset="0%" stop-color="{pri_hi}"/>
<stop offset="100%" stop-color="{pri}"/>
</linearGradient>
<linearGradient id="ga" x1="0" y1="0" x2="100" y2="100" gradientUnits="userSpaceOnUse">
<stop offset="0%" stop-color="{acc_hi}"/>
<stop offset="100%" stop-color="{acc}"/>
</linearGradient>
</defs>
<rect width="300" height="300" fill="{bg}"/>
<g transform="translate(21,21) scale(0.86)">
{body}
</g>
</svg>"""


def generate_banner_identicon(identifier: str, width: int = 1500, height: int = 500) -> str:
    """Gera banner SVG geométrico procedural."""
    hashed = hashlib.md5(identifier.encode()).hexdigest()
    bg, pri, pri_hi, acc, acc_hi = _build_palette(hashed)
    rng = Random(hashed)

    VW, VH = 900, 300

    # Background gradient
    gx1, gy1, gx2, gy2 = rng.choice(_BG_ANGLES)
    
    h0 = int(hashed[0:2], 16) / 255.0 * 360
    sv = int(hashed[2], 16) / 15.0
    lv = int(hashed[3], 16) / 15.0
    hue_shift = rng.randint(15, 30) * rng.choice([-1, 1])
    bg2 = _hsl_to_hex((h0 + hue_shift) % 360, 0.22 + sv * 0.20, 0.12 + lv * 0.10)

    # Gerar shapes com list comprehension
    num_shapes = rng.randint(12, 24)
    palette = [pri, pri_hi, acc, acc_hi, bg, bg2]
    
    shapes_svg = []
    for _ in range(num_shapes):
        shape_type = rng.choice(_SHAPE_TYPES)
        color = rng.choice(palette)
        opacity = round(rng.uniform(0.3, 0.95), 2)
        
        if shape_type == "circle":
            cx, cy, r = rng.randint(-50, VW + 50), rng.randint(-50, VH + 50), rng.randint(20, 160)
            shapes_svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{opacity}"/>')
            
        elif shape_type == "ring":
            cx, cy, r, sw = rng.randint(-50, VW + 50), rng.randint(-50, VH + 50), rng.randint(30, 130), rng.randint(4, 25)
            shapes_svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" opacity="{opacity}"/>')
            
        elif shape_type == "line":
            x_start, y_start = rng.randint(-100, VW + 50), rng.randint(-100, VH + 50)
            x_end, y_end = x_start + rng.randint(-400, 400), y_start + rng.randint(-300, 300)
            sw = rng.randint(8, 45)
            shapes_svg.append(
                f'<line x1="{x_start}" y1="{y_start}" x2="{x_end}" y2="{y_end}" '
                f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" opacity="{opacity}"/>'
            )
            
        elif shape_type == "triangle":
            cx, cy, size = rng.randint(0, VW), rng.randint(0, VH), rng.randint(40, 180)
            x1, y1 = cx, cy - size
            x2, y2 = cx - size * 0.866, cy + size * 0.5
            x3, y3 = cx + size * 0.866, cy + size * 0.5
            rot = rng.randint(0, 360)
            shapes_svg.append(
                f'<polygon points="{x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x3:.1f},{y3:.1f}" '
                f'fill="{color}" opacity="{opacity}" transform="rotate({rot} {cx} {cy})"/>'
            )

    body_svg = "\n    ".join(shapes_svg)

    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW} {VH}" width="{width}" height="{height}">
<defs>
<linearGradient id="bg_grad" x1="{gx1}" y1="{gy1}" x2="{gx2}" y2="{gy2}" gradientUnits="userSpaceOnUse">
<stop offset="0%" stop-color="{bg}"/>
<stop offset="100%" stop-color="{bg2}"/>
</linearGradient>
</defs>
<rect width="{VW}" height="{VH}" fill="url(#bg_grad)"/>
<g>
{body_svg}
</g>
</svg>"""


def generate_etag(v: str) -> str:
    """Gera ETag MD5."""
    return f'"{hashlib.md5(v.strip().encode()).hexdigest()}"'