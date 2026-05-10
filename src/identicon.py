from typing import Tuple
import hashlib


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h_n = (h % 360) / 360.0
    if s == 0:
        v = int(round(l * 255))
        return f"#{v:02x}{v:02x}{v:02x}"

    def _hue2rgb(p: float, q: float, t: float) -> float:
        t %= 1.0
        if t < 1 / 6: return p + (q - p) * 6 * t
        if t < 1 / 2: return q
        if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = _hue2rgb(p, q, h_n + 1 / 3)
    g = _hue2rgb(p, q, h_n)
    b = _hue2rgb(p, q, h_n - 1 / 3)
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def _build_palette(hashed: str) -> Tuple[str, str, str, str, str]:
    """
    Deriva uma paleta de 5 cores a partir do digest MD5.
    Retorna: (bg, primary, primary_highlight, accent, accent_highlight)
    """
    hue = int(hashed[0:2], 16) / 255.0 * 360
    sv  = int(hashed[2],   16) / 15.0  # variância de saturação [0, 1]
    lv  = int(hashed[3],   16) / 15.0  # variância de luminosidade [0, 1]

    bg         = _hsl_to_hex(hue, 0.20 + sv * 0.25, 0.08 + lv * 0.10)
    primary    = _hsl_to_hex(hue, 0.55 + sv * 0.35, 0.52 + lv * 0.24)
    primary_hi = _hsl_to_hex(hue, 0.40 + sv * 0.25, 0.74 + lv * 0.16)
    
    aoff       = (180, 120, 210, 60)[int(hashed[4], 16) % 4]
    ah         = (hue + aoff) % 360
    accent     = _hsl_to_hex(ah, 0.50 + sv * 0.30, 0.56 + lv * 0.22)
    accent_hi  = _hsl_to_hex(ah, 0.38 + sv * 0.22, 0.75 + lv * 0.14)

    return bg, primary, primary_hi, accent, accent_hi


def generate_identicon(identifier: str, size: int = 120) -> str:
    """
    Gera um identicon SVG simétrico com paleta de cores dinâmica e fills
    em gradiente, derivados do hash MD5 do `identifier`.

    Args:
        identifier: String única (ex: username, UUID, email).
        size:       Largura e altura do SVG de saída em pixels.

    Returns:
        String XML do SVG bruto.
    """
    hashed = hashlib.md5(identifier.encode("utf-8")).hexdigest()
    bg, pri, pri_hi, acc, acc_hi = _build_palette(hashed)

    CENTER = [
        '<rect width="100" height="100" rx="18"/>',
        '<polygon points="50,5 95,27 95,73 50,95 5,73 5,27"/>',
        '<circle cx="50" cy="50" r="47"/>',
        '<polygon points="50,5 61,36 95,36 68,57 79,92 50,71 21,92 32,57 5,36 39,36"/>',
        '<polygon points="50,3 97,50 50,97 3,50"/>',
        f'<circle cx="50" cy="50" r="47"/><circle cx="50" cy="50" r="20" fill="{bg}"/>',
        '<polygon points="20,5 80,5 95,50 80,95 20,95 5,50"/>',
        f'<rect width="100" height="100" rx="18"/><rect x="22" y="22" width="56" height="56" rx="8" fill="{bg}"/>',
        f'<polygon points="50,5 95,27 95,73 50,95 5,73 5,27"/><polygon points="50,28 73,40 73,60 50,72 27,60 27,40" fill="{bg}"/>',
        '<path d="M8,50 Q50,5 92,50 Q50,95 8,50 Z"/>',
        '<path d="M50,5 L90,25 L90,75 L50,95 L10,75 L10,25 Z"/>',
        '<rect x="8" y="8" width="84" height="84" rx="42"/>',
    ]

    EDGE = [
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
        '<polygon points="10,100 40,30 60,30 90,100"/>',
    ]

    CORNER = [
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
        '<polygon points="0,0 100,0 100,18 18,18 18,100 0,100"/>',
    ]

    ic = int(hashed[6], 16) % len(CENTER)
    ie = int(hashed[7], 16) % len(EDGE)
    ik = int(hashed[8], 16) % len(CORNER)

    # Edges e corners recebem primary ou accent de forma independente
    e_fill = "url(#gp)" if int(hashed[9],  16) % 2 == 0 else "url(#ga)"
    k_fill = "url(#gp)" if int(hashed[10], 16) % 2 == 0 else "url(#ga)"

    def _cell(shape: str, fill: str, tx: int, ty: int, rot: int = 0) -> str:
        return (
            f'<g transform="translate({tx},{ty}) rotate({rot},50,50)" fill="{fill}">'
            f"{shape}</g>"
        )

    cells = [
        _cell(CENTER[ic], "url(#gp)", 100, 100),
        _cell(EDGE[ie],   e_fill,     100,   0,   0),
        _cell(EDGE[ie],   e_fill,     200, 100,  90),
        _cell(EDGE[ie],   e_fill,     100, 200, 180),
        _cell(EDGE[ie],   e_fill,       0, 100, 270),
        _cell(CORNER[ik], k_fill,       0,   0,   0),
        _cell(CORNER[ik], k_fill,     200,   0,  90),
        _cell(CORNER[ik], k_fill,     200, 200, 180),
        _cell(CORNER[ik], k_fill,       0, 200, 270),
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
        </svg>
    """