"""
Floating reference-image overlay with an assistive ball (pure Python).
Install:  pip install pillow
Run:      python overlay_ball.py
Ball: drag = move | click = open/close panel | right-click = show/hide overlay
"""
import sys
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from PIL import Image, ImageTk

EXTS = {".png", ".jpg", ".jpeg", ".webp"}
FOLDER = ""          # optional: set a folder path here, or pick one in the panel

root = tk.Tk()
root.withdraw()

files, idx = [], 0
overlay_on, tk_img = True, None
SW, SH = root.winfo_screenwidth(), root.winfo_screenheight()

# ---------------- overlay window ----------------
ov = tk.Toplevel(root)
ov.overrideredirect(True)
ov.attributes("-topmost", True)
ov.attributes("-alpha", 0.5)
lbl = tk.Label(ov, bd=0, bg="black")
lbl.pack()


def click_through(win):
    if sys.platform != "win32":
        return
    import ctypes
    win.update_idletasks()
    u = ctypes.windll.user32
    hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
    style = u.GetWindowLongW(hwnd, -20)
    u.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)  # layered + transparent


def show_image():
    global tk_img
    if not files:
        return
    img = Image.open(files[idx]).convert("RGB")
    img.thumbnail((SW, SH))
    tk_img = ImageTk.PhotoImage(img)
    lbl.config(image=tk_img)
    x, y = (SW - img.width) // 2, (SH - img.height) // 2
    ov.geometry(f"{img.width}x{img.height}+{x}+{y}")
    counter.set(f"{idx + 1}/{len(files)}  {files[idx].name}")
    click_through(ov)
    ball.lift()
    panel.lift()


def load_folder(path):
    global files, idx
    files = sorted((p for p in Path(path).iterdir() if p.suffix.lower() in EXTS),
                   key=lambda p: p.name.lower())
    idx = 0
    show_image()


def step(d):
    global idx
    if files:
        idx = (idx + d) % len(files)
        show_image()


def toggle_overlay(_=None):
    global overlay_on
    overlay_on = not overlay_on
    ov.deiconify() if overlay_on else ov.withdraw()
    ball_canvas.itemconfig(circle, fill="#2e7d32" if overlay_on else "#b71c1c")
    if overlay_on:
        show_image()


# ---------------- control panel ----------------
panel = tk.Toplevel(root)
panel.overrideredirect(True)
panel.attributes("-topmost", True)
panel.configure(bg="#222")
panel.withdraw()
counter = tk.StringVar(value="No images")

tk.Label(panel, textvariable=counter, fg="white", bg="#222", wraplength=240).pack(padx=10, pady=(10, 4))
tk.Scale(panel, from_=0, to=100, orient="horizontal", label="Opacity %", length=220,
         fg="white", bg="#222", highlightthickness=0,
         command=lambda v: ov.attributes("-alpha", int(v) / 100)).pack(padx=10)
panel.winfo_children()[-1].set(50)

row = tk.Frame(panel, bg="#222")
row.pack(pady=6)
tk.Button(row, text="◀", width=4, command=lambda: step(-1)).pack(side="left", padx=4)
tk.Button(row, text="▶", width=4, command=lambda: step(1)).pack(side="left", padx=4)
tk.Button(panel, text="Choose folder",
          command=lambda: (lambda d: d and load_folder(d))(filedialog.askdirectory())).pack(pady=2)
tk.Button(panel, text="Quit", command=root.destroy).pack(pady=(2, 10))


def toggle_panel():
    if panel.winfo_viewable():
        panel.withdraw()
    else:
        panel.update_idletasks()
        x = min(ball.winfo_x(), SW - panel.winfo_reqwidth() - 10)
        y = ball.winfo_y() + 70
        if y + panel.winfo_reqheight() > SH:
            y = ball.winfo_y() - panel.winfo_reqheight() - 10
        panel.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        panel.deiconify()
        panel.lift()


# ---------------- floating ball ----------------
ball = tk.Toplevel(root)
ball.overrideredirect(True)
ball.attributes("-topmost", True)
ball.geometry(f"60x60+{SW - 90}+{SH // 3}")
ball_canvas = tk.Canvas(ball, width=60, height=60, highlightthickness=0, bg="white")
ball_canvas.pack()
circle = ball_canvas.create_oval(4, 4, 56, 56, fill="#2e7d32", outline="white", width=2)
ball_canvas.create_text(30, 30, text="◐", fill="white", font=("Arial", 22))
try:
    ball.attributes("-transparentcolor", "white")   # round shape on Windows
except tk.TclError:
    pass

drag = {"x": 0, "y": 0, "moved": False}


def on_press(e):
    drag.update(x=e.x, y=e.y, moved=False)


def on_move(e):
    drag["moved"] = True
    ball.geometry(f"+{ball.winfo_x() + e.x - drag['x']}+{ball.winfo_y() + e.y - drag['y']}")
    if panel.winfo_viewable():
        panel.withdraw()


def on_release(e):
    if not drag["moved"]:
        toggle_panel()


ball_canvas.bind("<ButtonPress-1>", on_press)
ball_canvas.bind("<B1-Motion>", on_move)
ball_canvas.bind("<ButtonRelease-1>", on_release)
ball_canvas.bind("<Button-3>", toggle_overlay)

if FOLDER:
    load_folder(FOLDER)
root.mainloop()
