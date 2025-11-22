import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional, Tuple

import image_splitter
import ascii_matcher
from PIL import Image, ImageDraw, ImageFont
import tkinter.font as tkfont


class ASCIIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Picture2ASCII — Minimal GUI")
        # Default opening resolution requested
        self.geometry("1920x1080")
        self.minsize(800, 500)

        # apply a minimal light theme / palette
        self._apply_theme()

        # State
        self.image_path = os.path.join(os.path.dirname(__file__), "input.png")
        self.cols = tk.IntVar(value=80)
        self.rows = tk.IntVar(value=0)
        self.lock_aspect = tk.BooleanVar(value=True)
        self.color = tk.BooleanVar(value=False)
        self.export_tiles = tk.BooleanVar(value=False)
        self.tile_w = tk.IntVar(value=8)
        self.tile_h = tk.IntVar(value=16)
        self.chars_index = tk.IntVar(value=0)
        # internal
        self._created_tags = set()

        # Path StringVar so we can trace changes
        self.path_var = tk.StringVar(value=self.image_path)

        self._build_ui()

    def _build_ui(self):
        # Left controls
        ctrl = ttk.Frame(self)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        ttk.Label(ctrl, text="Input Image:").pack(anchor="w")
        path_frame = ttk.Frame(ctrl)
        path_frame.pack(fill=tk.X)
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="Browse", command=self.browse_image).pack(side=tk.LEFT, padx=4)

        # tweak widget backgrounds to match theme where possible
        try:
            style = ttk.Style(self)
            # Frame/Label background
            style.configure('TFrame', background=self._palette['panel'])
            style.configure('TLabel', background=self._palette['panel'], foreground=self._palette['text'])
            style.configure('TButton', background=self._palette['button_bg'], foreground=self._palette['button_fg'])
            style.configure('TEntry', fieldbackground=self._palette['input_bg'], foreground=self._palette['text'])
            style.configure('TSpinbox', fieldbackground=self._palette['input_bg'], foreground=self._palette['text'])
            style.configure('TCombobox', fieldbackground=self._palette['input_bg'], foreground=self._palette['text'])
            style.configure('TCheckbutton', background=self._palette['panel'], foreground=self._palette['text'])
        except Exception:
            pass

        ttk.Separator(ctrl).pack(fill=tk.X, pady=6)

        ttk.Label(ctrl, text="Layout").pack(anchor="w")
        ttk.Label(ctrl, text="Cols:").pack(anchor="w")
        ttk.Spinbox(ctrl, from_=10, to=400, textvariable=self.cols, width=8).pack(anchor="w")
        ttk.Label(ctrl, text="Rows (optional):").pack(anchor="w")
        ttk.Spinbox(ctrl, from_=1, to=400, textvariable=self.rows, width=8).pack(anchor="w")
        ttk.Checkbutton(ctrl, text="Lock aspect ratio", variable=self.lock_aspect).pack(anchor="w", pady=4)

        ttk.Separator(ctrl).pack(fill=tk.X, pady=6)
        ttk.Label(ctrl, text="Tile / Font").pack(anchor="w")
        tile_frame = ttk.Frame(ctrl)
        tile_frame.pack(fill=tk.X)
        ttk.Label(tile_frame, text="W:").grid(row=0, column=0)
        ttk.Entry(tile_frame, textvariable=self.tile_w, width=4).grid(row=0, column=1)
        ttk.Label(tile_frame, text="H:").grid(row=0, column=2)
        ttk.Entry(tile_frame, textvariable=self.tile_h, width=4).grid(row=0, column=3)

        ttk.Separator(ctrl).pack(fill=tk.X, pady=6)
        ttk.Checkbutton(ctrl, text="Color output", variable=self.color).pack(anchor="w")
        ttk.Checkbutton(ctrl, text="Export tiles", variable=self.export_tiles).pack(anchor="w")

        ttk.Label(ctrl, text="Charset: ").pack(anchor="w", pady=(8, 0))
        ttk.Combobox(ctrl, values=["LESS", "DEFAULT", "MORE"], state="readonly", width=10, textvariable=self.chars_index).pack(anchor="w")

        # we'll set up traces after the UI variables (font_size) are created

        ttk.Separator(ctrl).pack(fill=tk.X, pady=6)
        btn_frame = ttk.Frame(ctrl)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Render", command=self.start_render).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="Save TXT", command=self.save_text).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(btn_frame, text="Export as Image", command=self.export_preview_as_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        ttk.Separator(ctrl).pack(fill=tk.X, pady=6)
        ttk.Label(ctrl, text="Preview font size").pack(anchor="w")
        self.font_size = tk.IntVar(value=10)
        ttk.Scale(ctrl, from_=6, to=22, variable=self.font_size, command=lambda e: self._update_font()).pack(fill=tk.X)

        # Font weight slider (0-3) — used to control thickness when exporting image
        ttk.Label(ctrl, text="Font Weight: 0(normal)-3(bold)").pack(anchor="w", pady=(6,0))
        self.font_weight = tk.IntVar(value=1)
        ttk.Scale(ctrl, from_=0, to=3, variable=self.font_weight, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Note: realtime rendering removed — rendering is manual via the Render button.

        # switch to grid layout and make left column fixed width
        # compute a sensible fixed left width based on screen width (but not too small)
        screen_w = self.winfo_screenwidth() or 1200
        default_left = int(max(280, min(800, screen_w * 0.35)))
        self._left_fixed_width = default_left

        # left column fixed (weight=0), right column expands (weight=1)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left controls frame -> grid column 0 (fixed width)
        ctrl.pack_forget()
        ctrl.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        try:
            ctrl.configure(width=self._left_fixed_width)
            ctrl.grid_propagate(False)
        except Exception:
            pass

        # Right: preview
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        # ensure left column minsize is enforced
        try:
            self.grid_columnconfigure(0, minsize=self._left_fixed_width)
        except Exception:
            pass

        # adapt preview font for display scaling
        # use a tkfont.Font so we can change weight dynamically
        self.preview_font = tkfont.Font(family="Courier New", size=int(self._scaled_font_size(self.font_size.get())), weight='normal')
        self.preview = ScrolledText(right, wrap=tk.NONE, font=self.preview_font)
        self.preview.pack(fill=tk.BOTH, expand=True)
        # preview colors (light theme)
        try:
            self.preview.configure(bg=self._palette['preview_bg'], fg=self._palette['preview_fg'], insertbackground=self._palette['preview_fg'], relief='flat', bd=0)
            # configure the internal text widget border visually
            self.preview.config(highlightthickness=1, highlightbackground=self._palette['border'])
        except Exception:
            pass
        self.preview.configure(state=tk.NORMAL)

        # Status bar
        self.status = ttk.Label(self, text="Ready", anchor="w")
        self.status.grid(row=1, column=0, columnspan=2, sticky="we")

    def browse_image(self):
        p = filedialog.askopenfilename(
            parent=self,
            title="Select image",
            filetypes=[("Image files", ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif")), ("All files", "*.*")],
        )
        if p:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, p)

    def _update_font(self):
        # update preview font size and weight according to sliders
        try:
            size = int(self.font_size.get())
        except Exception:
            size = 10
        # map weight slider (0-3) to normal/bold; 0-1 => normal, 2-3 => bold
        try:
            wval = int(self.font_weight.get())
        except Exception:
            wval = 1
        weight = 'bold' if wval >= 2 else 'normal'
        try:
            self.preview_font.configure(size=int(self._scaled_font_size(size)), weight=weight)
        except Exception:
            # fallback: set tuple directly
            try:
                self.preview.configure(font=("Courier New", int(self._scaled_font_size(size))))
            except Exception:
                pass
        # font change does not trigger realtime rendering (manual render)
        return

    def _scaled_font_size(self, base_size: int) -> float:
        """Return font size adjusted for display scaling (DPI) and platform scaling."""
        try:
            # tk scaling typically is pixels per point / 1.0, default 1.0
            scaling = float(self.tk.call('tk', 'scaling'))
        except Exception:
            scaling = 1.0
        # Some platforms set scaling >1 for high-DPI; adjust font accordingly
        return max(6, base_size * scaling)

    def start_render(self):
        # spawn thread to avoid blocking UI
        t = threading.Thread(target=self.render)
        t.daemon = True
        t.start()


    def render(self):
        try:
            self.status.config(text="Rendering...")
            self.preview.configure(state=tk.NORMAL)
            self.preview.delete("1.0", tk.END)

            image_path = self.path_entry.get().strip()
            if not image_path:
                messagebox.showerror("Error", "Please choose an image")
                return

            cols = int(self.cols.get())
            rows_val = int(self.rows.get()) if int(self.rows.get()) > 0 else None
            lock = bool(self.lock_aspect.get())
            color = bool(self.color.get())
            export_tiles = bool(self.export_tiles.get())
            tile_size = (int(self.tile_w.get()), int(self.tile_h.get()))
            try:
                chars_index = int(self.chars_index.get())
            except Exception:
                chars_index = 0

            # compute rows if locked
            if lock:
                with image_splitter.Image.open(image_path) as im:  # type: ignore[attr-defined]
                    w, h = im.size
                tile_w, tile_h = tile_size
                rows = max(1, int(round((h * cols * tile_w) / (w * tile_h))))
            else:
                rows = rows_val or cols

            grid = image_splitter.split_grid_from_path(image_path, columns=cols, rows=rows, save_image=export_tiles)

            # prepare templates for matching
            templates = ascii_matcher.build_char_templates(chars_index=chars_index, tile_size=tile_size)

            # render into Text widget with color tags
            for r, row in enumerate(grid):
                line_chars = []
                for c, cell in enumerate(row):
                    img = cell.get("image")
                    ch, _ = ascii_matcher.match_tile_to_char(img, templates, tile_size)
                    if color:
                        rr, gg, bb = ascii_matcher._avg_tile_color(img)
                        hexc = f"#{rr:02x}{gg:02x}{bb:02x}"
                        tag_name = f"c_{hexc}"
                        if tag_name not in self._created_tags:
                            # configure tag once
                            try:
                                self.preview.tag_configure(tag_name, foreground=hexc)
                            except Exception:
                                pass
                            self._created_tags.add(tag_name)
                        line_chars.append((ch, tag_name))
                    else:
                        line_chars.append((ch, None))

                # insert line
                for ch, tag in line_chars:
                    if tag:
                        self.preview.insert(tk.END, ch, tag)
                    else:
                        self.preview.insert(tk.END, ch)
                self.preview.insert(tk.END, "\n")

            self.preview.configure(state=tk.DISABLED)
            self.status.config(text=f"Rendered {cols}x{rows} (color={color})")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.config(text="Error")

    def save_text(self):
        # save the plain ASCII text (without ANSI) to file
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files","*.txt"), ("All files","*.*")])
        if not path:
            return
        text = self.preview.get("1.0", tk.END)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Saved", f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_preview_as_image(self):
        """Export the current preview text as a PNG image.

        Uses the preview font size and font weight slider to control appearance.
        """

    def _apply_theme(self):
        """Apply a minimal dark color palette to the UI."""
        # color palette (light, minimal)
        self._palette = {
            'bg': '#f6f7fb',         # window background
            'panel': '#ffffff',      # panel / frame background
            'text': '#0f1724',       # primary text (dark)
            'muted': '#516178',      # secondary text
            'accent': '#2563eb',     # accent (buttons / highlights)
            'input_bg': '#f3f4f6',   # entry background
            'button_bg': '#ffffff',  # button background (flat)
            'button_fg': '#0f1724',  # button foreground
            'preview_bg': '#ffffff', # preview background
            'preview_fg': '#0f1724', # preview text
            'border': '#e6e9ef',     # subtle borders
        }
        try:
            self.configure(bg=self._palette['bg'])
        except Exception:
            pass
        try:
            s = ttk.Style(self)
            # Prefer a neutral theme first
            try:
                s.theme_use('clam')
            except Exception:
                pass
            # Frames and labels
            s.configure('TFrame', background=self._palette['panel'])
            s.configure('TLabel', background=self._palette['panel'], foreground=self._palette['text'])
            # Minimal flat button style
            s.configure('TButton', background=self._palette['button_bg'], foreground=self._palette['button_fg'], relief='flat', padding=6)
            s.map('TButton', background=[('active', self._palette['accent'])], relief=[('pressed', 'flat')])
            # Inputs: subtle background and thin border feel
            s.configure('TEntry', fieldbackground=self._palette['input_bg'], foreground=self._palette['text'])
            s.configure('TCombobox', fieldbackground=self._palette['input_bg'], foreground=self._palette['text'])
            s.configure('TCheckbutton', background=self._palette['panel'], foreground=self._palette['text'])
            # Try to reduce focus border emphasis where possible
            try:
                s.configure('Vertical.TScrollbar', troughcolor=self._palette['panel'])
            except Exception:
                pass
        except Exception:
            pass
        # preview (ScrolledText) is a Tk Text widget — configure directly later when built


def main():
    app = ASCIIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
