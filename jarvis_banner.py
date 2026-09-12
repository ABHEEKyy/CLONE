import os
import sys
import time

def enable_windows_ansi():
    """Enables ANSI escape sequence processing and UTF-8 encoding in Windows Command Prompt/PowerShell."""
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            os.system("")

def animate_jarvis_banner():
    """Renders an Iron Man Arc Reactor core initialization & stencil banner for J.A.R.V.I.S."""
    enable_windows_ansi()

    RESET        = "\033[0m"
    BOLD         = "\033[1m"
    BRIGHT_WHITE = "\033[1;97m"
    WHITE        = "\033[97m"
    GRAY         = "\033[37m"
    DARK_GRAY    = "\033[90m"

    # Perfected Stencil Font spelling J A R V I S
    stencil_art = [
        "   ___   _   ___  _   _ ___ ___ ",
        "  |_  | /_\\ | _ \\| | | |_ _/ __|",
        "   _| |/ _ \\|   /| |_| || |\\__ \\",
        "  |___/_/ \\_\\_|_| \\___/|___|___/",
    ]

    arc_symbols = [" ( ◯ ) ", " ( ⊙ ) ", " ( ◉ ) ", " ( ◈ ) ", " ( ✦ ) "]

    print()
    # Step 1: Arc Reactor Spin + Stencil Reveal
    for i, line in enumerate(stencil_art):
        symbol = arc_symbols[i % len(arc_symbols)]
        print(f"  {BRIGHT_WHITE}{symbol}{RESET}  {WHITE}{BOLD}{line}{RESET}")
        time.sleep(0.03)

    print(f"  {DARK_GRAY}─────────────────────────────────────────────────────{RESET}")

    # Step 2: Animated Arc-Reactor Progress Bar
    bar_width = 32
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    if is_tty:
        for b in range(0, bar_width + 1, 4):
            filled = "▓" * b
            unfilled = "░" * (bar_width - b)
            pct = int((b / bar_width) * 100)
            sys.stdout.write(f"\r  {WHITE}{BOLD}[ CORE ]{RESET} {BRIGHT_WHITE}[{filled}{DARK_GRAY}{unfilled}{BRIGHT_WHITE}]{RESET} {WHITE}{pct}%{RESET}")
            sys.stdout.flush()
            time.sleep(0.03)
        print()
    else:
        filled = "▓" * bar_width
        print(f"  {WHITE}{BOLD}[ CORE ]{RESET} {BRIGHT_WHITE}[{filled}]{RESET} {WHITE}100%{RESET}")

    print(f"  {DARK_GRAY}─────────────────────────────────────────────────────{RESET}")
    print(f"  {BRIGHT_WHITE}SYSTEM:{RESET} {WHITE}ONLINE{RESET}   {DARK_GRAY}│{RESET}   {BRIGHT_WHITE}VOICE:{RESET} {WHITE}ACTIVE{RESET}   {DARK_GRAY}│{RESET}   {BRIGHT_WHITE}HUD:{RESET} {WHITE}READY{RESET}\n")

def print_jarvis_banner():
    animate_jarvis_banner()

if __name__ == "__main__":
    animate_jarvis_banner()
