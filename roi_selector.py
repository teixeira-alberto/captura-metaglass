import sys
import tkinter as tk
from ctypes import windll, Structure, byref, c_long, wintypes

ALPHA = 0.35         
INIT_W, INIT_H = 320, 320

user32 = windll.user32
try:
    user32.SetProcessDPIAware()  
except Exception:
    pass

class RECT(Structure):
    _fields_ = [("left", c_long), ("top", c_long), ("right", c_long), ("bottom", c_long)]

def get_client_rect_screen(hwnd):
    """Retorna (left, top, width, height) do CLIENTE em coordenadas de tela (pixels físicos)."""
    rc = RECT()
    user32.GetClientRect(hwnd, byref(rc))       
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, byref(pt))         
    left, top = int(pt.x), int(pt.y)
    width, height = int(rc.right - rc.left), int(rc.bottom - rc.top)
    return left, top, width, height

_last_key = None
_last_len = 0

def _status_write(text: str):
    global _last_len
    pad = max(0, _last_len - len(text))
    sys.stdout.write("\r" + text + (" " * pad))
    sys.stdout.flush()
    _last_len = len(text)

def _status_newline():
    global _last_len
    sys.stdout.write("\n")
    sys.stdout.flush()
    _last_len = 0

# --- TK window ---
root = tk.Tk()
root.title("Selecionar tamanho da janela")
root.attributes("-topmost", True)
try:
    root.attributes("-alpha", ALPHA)
except tk.TclError:
    pass

# centraliza
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{INIT_W}x{INIT_H}+{(sw-INIT_W)//2}+{(sh-INIT_H)//2}")

# canvas só para desenhar uma borda-guia (área de cliente)
canvas = tk.Canvas(root, highlightthickness=0, bg="black")
canvas.pack(fill="both", expand=True)

def draw_client_guide():
    canvas.delete("all")
    w, h = root.winfo_width(), root.winfo_height()
    if w > 2 and h > 2:
        canvas.create_rectangle(1, 1, w-2, h-2, outline="white", width=1)

def print_region(force=False):
    global _last_key
    hwnd = root.winfo_id()
    left, top, width, height = get_client_rect_screen(hwnd)
    if width <= 0 or height <= 0:
        return
    key = (left, top, width, height)
    if force or key != _last_key:
        _last_key = key
        text = f"Use no mss: {{'left': {left}, 'top': {top}, 'width': {width}, 'height': {height}}}"
        _status_write(text)

def on_configure(event=None):
    draw_client_guide()
    print_region()

def on_key(event):
    if event.keysym in ("Escape", "q", "Q"):
        _status_newline()
        print("Saindo.")
        root.destroy()
    elif event.keysym in ("Return", "KP_Enter"):
        # imprime a medida final numa nova linha e sai
        print_region(force=True)
        _status_newline()
        print("Medida final confirmada. Saindo.")
        root.destroy()

print("Mova/redimensione o pop-up por cima da área a ser capturada (sem incluir bordas da janela de seleção)")
print("Com a janela selecionada, pressione: ENTER = confirmar e sair  |  Q/ESC = sair")
print("(A linha abaixo será atualizada em tempo real)\n")

root.bind("<Configure>", on_configure)
root.bind("<Key>", on_key)

root.mainloop()