import os
from typing import Optional, Tuple, List
import argparse

import image_splitter
import ascii_matcher


# Default input filename in project root (same folder as this script)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_NAME = "input.png"
DEFAULT_INPUT_PATH = os.path.join(ROOT_DIR, DEFAULT_INPUT_NAME)


def image_to_ascii(
    image_path: str,                        # path to source image
    lock_aspect: bool = True,               # if True, compute `rows` from `cols` to keep original aspect ratio
    cols: int = 80,                         # number of character columns
    rows: Optional[int] = None,             # number of character rows
    color: bool = False,                    # if True, produce ANSI-colored output
    export_tiles: bool = False,             
    out_txt_path: Optional[str] = None, 
    tile_size: Tuple[int, int] = (8, 16),   
    chars_index: int = 0,
) -> str:
    """Convert an image to ASCII art and return the text result.

    Parameters:
      - image_path: path to source image
      - lock_aspect: if True, compute `rows` from `cols` to keep original aspect ratio
      - cols: number of character columns (width in characters)
      - rows: number of character rows (height in characters). If None and lock_aspect=True it will be computed.
      - color: if True, produce ANSI-colored output (requires terminal support)
      - export_tiles: if True, the split tiles will be saved to ./output_tiles
      - out_txt_path: if provided, write the ascii output to this file
      - tile_size: pixel size used to render character templates (width, height)
      - chars_index: 0 (default compact), 1 = MORE (richer charset), -1 = LESS (smaller set)

    Returns the final ASCII text (multi-line string).
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Compute rows based on aspect ratio and tile_size if requested
    if lock_aspect:
        with image_splitter.Image.open(image_path) as im:  # type: ignore[attr-defined]
            w, h = im.size
        tile_w, tile_h = tile_size
        # rows = (h * cols * tile_w) / (w * tile_h)
        rows = max(1, int(round((h * cols * tile_w) / (w * tile_h))))
    else:
        if rows is None:
            rows = cols

    # split image into grid
    grid = image_splitter.split_grid_from_path(image_path, columns=cols, rows=rows, save_image=export_tiles)

    # build templates
    templates = ascii_matcher.build_char_templates(chars_index=chars_index, tile_size=tile_size)

    # convert to ascii lines
    if color:
        ascii_lines = ascii_matcher.grid_to_ascii_color(grid, templates, tile_size)
    else:
        ascii_lines = ascii_matcher.grid_to_ascii_monochrome(grid, templates, tile_size)

    text = "\n".join(ascii_lines)

    if out_txt_path:
        with open(out_txt_path, "w", encoding="utf-8") as f:
            f.write(text)

    return text


def _parse_args_and_run():
    p = argparse.ArgumentParser(description="Convert image to ASCII art")
    p.add_argument("image", nargs="?", default=DEFAULT_INPUT_PATH, help="Path to image (default: ./input.png)")
    p.add_argument("--lock-aspect", dest="lock_aspect", action="store_true", help="Lock aspect ratio (compute rows from cols)")
    p.add_argument("--no-lock-aspect", dest="lock_aspect", action="store_false", help="Do not lock aspect ratio")
    p.set_defaults(lock_aspect=True)
    p.add_argument("--cols", type=int, default=80, help="Number of character columns")
    p.add_argument("--rows", type=int, default=None, help="Number of character rows (if not locking aspect)")
    p.add_argument("--color", action="store_true", help="Enable ANSI color output")
    p.add_argument("--export-tiles", action="store_true", help="Export split tiles to ./output_tiles")
    p.add_argument("--out-txt", default=None, help="Write ASCII output to this text file")
    p.add_argument("--tile-w", type=int, default=8, help="Template tile width in pixels")
    p.add_argument("--tile-h", type=int, default=16, help="Template tile height in pixels")
    p.add_argument("--chars", type=int, default=0, choices=[-1, 0, 1], help="Charset index: -1=LESS,0=DEFAULT,1=MORE")
    args = p.parse_args()

    tile_size = (args.tile_w, args.tile_h)
    text = image_to_ascii(
        image_path=args.image,
        lock_aspect=args.lock_aspect,
        cols=args.cols,
        rows=args.rows,
        color=args.color,
        export_tiles=args.export_tiles,
        out_txt_path=args.out_txt,
        tile_size=tile_size,
        chars_index=args.chars,
    )
    print(text)

# * TEST BASH 1 : python main.py ./input.png --lock-aspect --cols 80 --export-tiles --out-txt "./output.txt"
# * TEST BASH 2 : python main.py ./input.png --lock-aspect --color --cols 80 --export-tiles --out-txt "./output.txt"
if __name__ == "__main__":
    _parse_args_and_run()
