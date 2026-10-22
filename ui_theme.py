"""Shared native Tk palette and ttk styles; no rendering engine or extra dependency."""
PALETTES = {
    "dark": dict(window="#18181B", card="#202024", text="#F2F2F7", subtle="#A1A1AA",
                 border="#38383A", button="#303034", pressed="#3A3A40", accent="#58A6FF",
                 on_accent="#0B1524", select="#26486B", red="#FF939B", green="#77D5B0",
                 orange="#F4BF7B", sidebar="#1C1C1E", field="#2C2C2E", bubble="#28384B"),
    "light": dict(window="#F5F5F7", card="#FFFFFF", text="#1D1D1F", subtle="#63636A",
                  border="#DEDEE3", button="#EAEAEE", pressed="#DCDCE2", accent="#0066CC",
                  on_accent="#FFFFFF", select="#E0D9FA", red="#B93649", green="#23745C",
                  orange="#99601E", sidebar="#EEEEF2", field="#F5F5F7", bubble="#EAF3FF"),
}


def configure_styles(style, p):
    style.configure("TFrame", background=p["card"])
    style.configure("TLabel", background=p["card"], foreground=p["text"], font=("Segoe UI", 10))
    style.configure("Muted.TLabel", foreground=p["subtle"], background=p["card"], font=("Segoe UI", 9))
    style.configure("Title.TLabel", foreground=p["text"], background=p["card"], font=("Segoe UI Semibold", 17))
    style.configure('TNotebook',background=p['card'],borderwidth=0)
    style.configure('TNotebook.Tab',padding=(16,8),background=p['button'],foreground=p['text'])
    style.map('TNotebook.Tab',background=[('selected',p['card'])],foreground=[('selected',p['accent'])])
    style.configure("TButton", background=p["button"], foreground=p["text"], borderwidth=0,
                    relief="flat", padding=(10, 8), font=("Segoe UI", 10), anchor="center")
    style.map("TButton", background=[("disabled", p["card"]), ("active", p["pressed"])],
              foreground=[("disabled", p["subtle"])])
    style.configure("Accent.TButton", background=p["accent"], foreground=p["on_accent"], font=("Segoe UI Semibold",10))
    style.map("Accent.TButton", background=[("disabled",p["button"]),("active",p["accent"])],
              foreground=[("disabled",p["subtle"]),("active",p["on_accent"])])
    style.configure("TCombobox", fieldbackground=p["field"], background=p["field"],
                    foreground=p["text"], arrowcolor=p["subtle"], bordercolor=p["border"],
                    lightcolor=p["field"], darkcolor=p["field"], borderwidth=1, padding=6, arrowsize=12)
    style.map("TCombobox", fieldbackground=[("readonly",p["field"])], foreground=[("readonly",p["text"])],
              selectbackground=[("readonly",p["field"])], selectforeground=[("readonly",p["text"])])
    style.configure("Vertical.TScrollbar", background=p["border"], troughcolor=p["card"],
                    bordercolor=p["card"], arrowcolor=p["subtle"], lightcolor=p["card"],darkcolor=p["card"],
                    borderwidth=0, arrowsize=11, width=10)
    style.map("Vertical.TScrollbar",background=[("active",p["pressed"])])
    style.configure("TPanedwindow",background=p["window"])
    style.configure("Sash",sashthickness=10,gripcount=0)

    style.configure("Horizontal.TScrollbar", background=p["border"], troughcolor=p["field"],
                    bordercolor=p["field"], arrowcolor=p["subtle"], lightcolor=p["field"],
                    darkcolor=p["field"], borderwidth=0, arrowsize=10, width=10)
