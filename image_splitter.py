from PIL import Image
import os
from typing import List, Dict, Tuple


def split_grid_from_path(
    image_path: str,
    columns: int = 128,
    rows: int = 64,
    save_image: bool = False,
) -> List[List[Dict[str, object]]]:
    """Load image and split into grid (columns x rows).

    Returns a 2D list (rows x columns) where each element is a dict:
      {
        'image': PIL.Image.Image,
        'box': (x, y, width, height),
        'row': row_index,  # 0-based
        'col': col_index,  # 0-based
      }

    If `save_image` is True the tiles will be saved under `./output_tiles` with
    filenames like `tile_r{row+1}c{col+1}.png`.
    """
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be >= 1")
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    im = Image.open(image_path)
    w, h = im.size

    col_base = w // columns
    col_rem = w % columns
    row_base = h // rows
    row_rem = h % rows

    grid: List[List[Dict[str, object]]] = []

    y = 0
    for r in range(rows):
        h_r = row_base + (1 if r < row_rem else 0)
        row_list: List[Dict[str, object]] = []
        x = 0
        for c in range(columns):
            w_c = col_base + (1 if c < col_rem else 0)
            box = (x, y, w_c, h_r)
            tile = im.crop((x, y, x + w_c, y + h_r))
            cell = {"image": tile, "box": box, "row": r, "col": c}
            row_list.append(cell)
            x += w_c
        y += h_r
        grid.append(row_list)

    if save_image:
        out_dir = "./output_tiles"
        save_image_grid(grid, out_dir)

    return grid


def save_image_grid(grid: List[List[Dict[str, object]]], out_dir: str, base_name: str = "tile") -> List[str]:
    """Save a grid produced by `split_grid_from_path` to disk and return saved paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths: List[str] = []
    for row in grid:
        for cell in row:
            r = cell.get("row", 0)
            c = cell.get("col", 0)
            img: Image.Image = cell["image"]
            filename = f"{base_name}_r{r+1}c{c+1}.png"
            path = os.path.join(out_dir, filename)
            img.save(path)
            paths.append(path)
    return paths

def save_image_list(images: List[Image.Image], out_dir: str, base_name: str = "tile") -> List[str]:
    """Backward-compatible: save a flat list of PIL images to `out_dir`."""
    os.makedirs(out_dir, exist_ok=True)
    paths: List[str] = []
    for i, img in enumerate(images, start=1):
        path = os.path.join(out_dir, f"{base_name}_{i}.png")
        img.save(path)
        paths.append(path)
    return paths