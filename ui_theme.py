"""Shared native Tk palette and ttk styles; no rendering engine or extra dependency."""
PALETTES = {
    "dark": dict(window="#0B1019", card="#121A27", text="#E8EDF5", subtle="#8D9BB0",
                 border="#263245", button="#1B2637", pressed="#29374C", accent="#A89BFF",
                 on_accent="#151125", select="#3E365F", red="#FF939B", green="#77D5B0",
                 orange="#F4BF7B", sidebar="#0E1521", field="#172233", bubble="#1C2940"),
    "light": dict(window="#EDF0F5", card="#FFFFFF", text="#1F2B40", subtle="#63728A",
                  border="#DDE3EE", button="#EAEFF7", pressed="#DBE3F0", accent="#6654C8",
                  on_accent="#FFFFFF", select="#E0D9FA", red="#B93649", green="#23745C",
                  orange="#99601E", sidebar="#F7F9FD", field="#F3F6FB", bubble="#EFF0FC"),
}


def configure_styles(style, p):
    style.configure("TFrame", background=p["card"])
    style.configure("TLabel", background=p["card"], foreground=p["text"], font=("Segoe UI", 10))
    style.configure("Muted.TLabel", foreground=p["subtle"], background=p["card"], font=("Segoe UI", 9))
    style.configure("Title.TLabel", foreground=p["text"], background=p["card"], font=("Segoe UI Semibold", 19))
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
