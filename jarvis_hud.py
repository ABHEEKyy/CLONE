import math
import sys
import threading
import time
import tkinter as tk

class JarvisSiriHUD:
    """Floating Siri-style glowing orb HUD overlay for J.A.R.V.I.S."""
    def __init__(self, start_hidden=True):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S. HUD")
        
        # Configure window: Frameless, Always-on-top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Set transparent background if supported on Windows
        try:
            self.root.config(bg="#0B0E14")
            self.root.attributes("-transparentcolor", "#0B0E14")
        except Exception:
            self.root.config(bg="#0B0E14")

        width, height = 220, 110
        screen_width = self.root.winfo_screenwidth()
        x_pos = screen_width - width - 30
        y_pos = 30
        self.root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        # Make window draggable
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # Canvas for animated glowing Siri orb
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg="#0B0E14", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.state = "STANDBY"
        self.status_text = "STANDBY"
        self.anim_step = 0
        self.running = True

        if start_hidden:
            self.root.withdraw()

        self.update_animation()

    def show_hud(self):
        """Pops up the Siri HUD window on screen."""
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def hide_hud(self):
        """Hides the Siri HUD window when standby."""
        self.root.withdraw()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def set_state(self, new_state: str, text: str = None):
        self.state = new_state
        if text:
            self.status_text = text.upper()
        else:
            state_text_map = {
                "STANDBY": "STANDBY",
                "LISTENING_WAKE": "LISTENING...",
                "LISTENING_CMD": "SPEAK NOW...",
                "PROCESSING": "PROCESSING...",
                "SPEAKING": "SPEAKING..."
            }
            self.status_text = state_text_map.get(new_state, new_state)

    def update_animation(self):
        if not self.running:
            return

        self.canvas.delete("all")
        width, height = 220, 110
        cx, cy = 50, 55
        self.anim_step += 0.1

        # Color schemes based on state
        if self.state == "LISTENING_CMD":
            pulse = math.sin(self.anim_step * 2) * 8
            r1, r2, r3 = 28 + pulse, 22 + pulse * 0.7, 15 + pulse * 0.4
            c1, c2, c3 = "#FF007F", "#00F0FF", "#7000FF"
            ring_color = "#00FFFF"
        elif self.state == "LISTENING_WAKE":
            pulse = math.sin(self.anim_step * 1.5) * 5
            r1, r2, r3 = 25 + pulse, 18 + pulse * 0.5, 12
            c1, c2, c3 = "#00E5FF", "#0088FF", "#0022AA"
            ring_color = "#00E5FF"
        elif self.state == "PROCESSING":
            pulse = math.sin(self.anim_step * 3) * 4
            r1, r2, r3 = 24 + pulse, 18, 12
            c1, c2, c3 = "#FFD700", "#00F0FF", "#FF8C00"
            ring_color = "#FFD700"
        elif self.state == "SPEAKING":
            pulse = math.sin(self.anim_step * 2.5) * 7
            r1, r2, r3 = 26 + pulse, 20 + pulse * 0.6, 13
            c1, c2, c3 = "#00FF66", "#00D4FF", "#0088FF"
            ring_color = "#00FF66"
        else:
            pulse = math.sin(self.anim_step) * 3
            r1, r2, r3 = 20 + pulse, 15, 10
            c1, c2, c3 = "#0088FF", "#0044AA", "#001155"
            ring_color = "#0055AA"

        # Draw multi-ring glowing orb
        self.canvas.create_oval(cx - r1, cy - r1, cx + r1, cy + r1, fill=c3, outline="")
        self.canvas.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=c2, outline="")
        self.canvas.create_oval(cx - r3, cy - r3, cx + r3, cy + r3, fill=c1, outline="")
        self.canvas.create_oval(cx - r1 - 3, cy - r1 - 3, cx + r1 + 3, cy + r1 + 3, outline=ring_color, width=2)

        # Draw Glowing J.A.R.V.I.S. Label Text
        self.canvas.create_text(131, 44, text="J.A.R.V.I.S.", fill="#003366", font=("Segoe UI", 11, "bold"))
        self.canvas.create_text(130, 43, text="J.A.R.V.I.S.", fill="#00F0FF", font=("Segoe UI", 11, "bold"))
        self.canvas.create_text(130, 63, text=self.status_text, fill=ring_color, font=("Segoe UI", 9, "bold"))


        self.root.after(33, self.update_animation)

    def run(self):
        self.root.mainloop()

    def close(self):
        self.running = False
        self.root.destroy()
