from PIL import Image, ImageDraw, ImageFont, ImageOps
import numpy as np
from typing import Dict, List, Tuple, Optional
import os

LESS = 1
MORE = 0

# A compact set of printable ASCII characters ordered roughly by "density" (dark->light)
DEFAULT_CHARSET_LESS = list("@%#*+=-:. ")
DEFAULT_CHARSET_MORE = "@#WMB8&%$?*oahkbdpqwmZO0QCLJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


def _get_font(font_path: Optional[str], font_size: int):
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            pass
    # fallback to default font
    return ImageFont.load_default()

def render_char_template(ch: str, size: Tuple[int, int], font_path: Optional[str] = None) -> np.ndarray:
    """Render a single character into a grayscale numpy array of shape (h, w), values 0..1."""
    w, h = size
    # Create an image with white background
    img = Image.new("L", (w, h), color=255)
    draw = ImageDraw.Draw(img)

    # Choose a font size that fits the tile; try a few heuristics
    # Use a font size roughly equal to min(w,h)
    font = _get_font(font_path, max(10, min(w, h)))

    # Center the character
    bbox = font.getbbox(ch)
    text_w = bbox[2] - bbox[0]  # right - left
    text_h = bbox[3] - bbox[1]  # bottom - top
    x = (w - text_w) // 2
    y = (h - text_h) // 2
    draw.text((x, y), ch, fill=0, font=font)

    arr = np.asarray(img, dtype=np.float32) / 255.0
    # invert so that 1.0 = dark/ink, 0.0 = background (makes density intuitive)
    arr = 1.0 - arr
    return arr


def build_char_templates(
    chars_index: int = 0,
    tile_size: Tuple[int, int] = (8, 24),
    font_path: Optional[str] = None,
) -> Dict[str, np.ndarray]:
    """Pre-render templates for each character.

    Returns dict char -> numpy array (h, w) float32 in [0,1], 1=ink.
    """
    if chars_index is MORE:
        chars = DEFAULT_CHARSET_MORE
    elif chars_index is LESS:
        chars = DEFAULT_CHARSET_LESS
    templates: Dict[str, np.ndarray] = {}
    for ch in chars:
        templates[ch] = render_char_template(ch, tile_size, font_path)
    return templates


def _image_to_array(img: Image.Image, size: Tuple[int, int]) -> np.ndarray:
    """Convert PIL image to normalized grayscale array matching template size."""
    im = img.convert("L")
    # Resize using ANTIALIAS (Lanczos)
    im = ImageOps.fit(im, size, Image.LANCZOS)
    arr = np.asarray(im, dtype=np.float32) / 255.0
    arr = 1.0 - arr
    return arr


def match_tile_to_char(
    tile: Image.Image,
    templates: Dict[str, np.ndarray],
    size: Tuple[int, int],
    replace_dot_with_block: bool = False,
) -> Tuple[str, float]:
    """Return best matching character and its score (lower is better).

    Score is mean squared error between tile and template.
    """
    tile_arr = _image_to_array(tile, size)
    best_char = None
    best_score = float("inf")
    for ch, temp in templates.items():
        # ensure same shape
        if temp.shape != tile_arr.shape:
            continue
        diff = tile_arr - temp
        score = float((diff * diff).mean())
        if score < best_score:
            best_score = score
            best_char = ch
    ch = best_char if best_char is not None else " "
    if replace_dot_with_block and ch == '.':
        ch = '█'
    return ch, best_score


def grid_to_ascii_monochrome(
    grid: List[List[Dict[str, object]]],
    templates: Dict[str, np.ndarray],
    tile_size: Tuple[int, int],
) -> List[str]:
    """Convert the 2D grid (rows x cols) of cells into list of ASCII strings (one per row).

    Each cell is expected to be a dict with key 'image' -> PIL.Image.
    """
    ascii_rows: List[str] = []
    for row in grid:
        chars = []
        for cell in row:
            img = cell.get("image")
            ch, score = match_tile_to_char(img, templates, tile_size)
            chars.append(ch)
        ascii_rows.append("".join(chars))
    return ascii_rows

def _avg_tile_color(tile: Image.Image) -> Tuple[int, int, int]:
    """Return average RGB color of tile as ints 0..255."""
    im = tile.convert("RGB")
    # fast downscale to 1x1 to get average color
    tiny = ImageOps.fit(im, (1, 1), Image.LANCZOS)
    r, g, b = tiny.getpixel((0, 0))
    return int(r), int(g), int(b)


def _ansi_fg_truecolor(r: int, g: int, b: int) -> str:
    """ANSI escape sequence for truecolor foreground."""
    return f"\x1b[38;2;{r};{g};{b}m"


def _ansi_bg_truecolor(r: int, g: int, b: int) -> str:
    """ANSI escape sequence for truecolor background."""
    return f"\x1b[48;2;{r};{g};{b}m"


def grid_to_ascii_color(
    grid: List[List[Dict[str, object]]],
    templates: Dict[str, np.ndarray],
    tile_size: Tuple[int, int],
    use_background: bool = False,
    use_block: bool = False,
    reset: str = "\x1b[0m",
) -> List[str]:
    """
    Convert grid to colored ASCII lines (ANSI).

    Options:
    - use_background: paint tile color as background and emit a space (or block if use_block=True).
    - use_block: use '█' (full block) as character with foreground color (better color coverage in some terminals).
      If False, the character chosen by brightness matching is used with foreground color.
    Returns list of strings where each string contains ANSI sequences.
    """
    lines: List[str] = []
    for row in grid:
        parts: List[str] = []
        for cell in row:
            img = cell.get("image")
            # pick char by matching (monochrome templates)
            # replace '.' with block for better color blocks in color mode
            ch, _ = match_tile_to_char(img, templates, tile_size)
            r, g, b = _avg_tile_color(img)
            if use_background:
                # draw a space or block on colored background
                bg = _ansi_bg_truecolor(r, g, b)
                char = "█" if use_block else " "
                parts.append(f"{bg}{char}{reset}")
            else:
                # draw chosen char in foreground color; fallback to space for None
                fg = _ansi_fg_truecolor(r, g, b)
                char = "█" if use_block else (ch if ch is not None else " ")
                parts.append(f"{fg}{char}{reset}")
        lines.append("".join(parts))
    return lines

if __name__ == "__main__":
    # Quick demo using ./input.png and the image_splitter grid
    try:
        from image_splitter import split_grid_from_path
    except Exception as e:
        print("Demo requires image_splitter.split_grid_from_path available in project.")
        raise

    INPUT = os.path.join(os.path.dirname(__file__), "input.png")
    if not os.path.exists(INPUT):
        print("Place an input.png in the project root to run demo.")
    else:
        # choose a small tile size for visible ASCII art
        tile_size = (8, 20)
        cols = 100
        # 读取原图尺寸，用于计算需要的行数以保留长宽比（并考虑 tile 纵横比）
        with Image.open(INPUT) as im:
            w, h = im.size

        tile_w, tile_h = tile_size
        # 公式：rows = h / tile_height ； tile_height = (w / cols) * (tile_h / tile_w)
        # 化简得到 rows = (h * cols * tile_w) / (w * tile_h)
        rows = max(1, int(round((h * cols * tile_w) / (w * tile_h))))
        grid = split_grid_from_path(INPUT, columns=cols, rows=rows, save_image=False)
        templates = build_char_templates(tile_size=tile_size)
        ascii_lines = grid_to_ascii_color(grid, templates, tile_size)
        for line in ascii_lines:
            print(line)
