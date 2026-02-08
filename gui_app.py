import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import threading
import requests  # Requires: pip install requests
from PIL import Image, ImageTk

# Import your modules
import totp_engine
import database_manager
import universal_scanner

# --- CONFIGURATION ---
# REPLACE THIS WITH YOUR COMPUTER'S LOCAL IP ADDRESS!
# Example: "http://192.168.1.15:5000"
SERVER_URL = "http://172.25.21.241:5000"


class AuthenticatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Cloud Authenticator")
        self.root.geometry("450x650")
        self.root.configure(bg="#f0f0f0")

        # --- STYLES ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#333")
        style.configure("Code.TLabel", font=("Consolas", 24, "bold"), foreground="#007bff")
        style.configure("TButton", font=("Segoe UI", 10))

        # --- HEADER ---
        header_frame = tk.Frame(root, bg="#333", height=60)
        header_frame.pack(fill=tk.X)
        lbl_title = tk.Label(header_frame, text="My 2FA Tokens", bg="#333", fg="white", font=("Segoe UI", 16, "bold"))
        lbl_title.pack(pady=15)

        # --- CONNECTION STATUS ---
        self.status_var = tk.StringVar()
        self.status_var.set("Checking Server...")
        lbl_status = tk.Label(root, textvariable=self.status_var, bg="#f0f0f0", fg="#555", font=("Segoe UI", 8))
        lbl_status.pack(pady=2)

        # --- ACCOUNT LIST (SCROLLABLE) ---
        self.canvas = tk.Canvas(root, bg="#f0f0f0", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#f0f0f0")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        # --- FOOTER ---
        footer_frame = tk.Frame(root, bg="#e0e0e0", height=50)
        footer_frame.pack(fill=tk.X, side="bottom")
        btn_add = tk.Button(footer_frame, text="+ Add New Account", bg="#28a745", fg="white",
                            font=("Segoe UI", 11, "bold"), relief="flat", padx=20, pady=10,
                            command=self.open_add_dialog)
        btn_add.pack(pady=10)

        # --- INITIALIZATION ---
        self.account_widgets = []
        self.check_server_connection()
        self.refresh_timer()
        self.load_accounts()

    def check_server_connection(self):
        """Checks if the Flask server is reachable."""

        def _check():
            try:
                requests.get(SERVER_URL, timeout=2)
                self.status_var.set(f"● Connected to Cloud ({SERVER_URL})")
                self.root.nametowidget(self.root.winfo_children()[1]).config(fg="green")
            except:
                self.status_var.set(f"○ Server Offline ({SERVER_URL})")
                self.root.nametowidget(self.root.winfo_children()[1]).config(fg="red")

        threading.Thread(target=_check, daemon=True).start()

    def load_accounts(self):
        """Fetches accounts from LOCAL DB and builds UI."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.account_widgets = []

        accounts = database_manager.get_all_accounts()

        if not accounts:
            lbl_empty = tk.Label(self.scrollable_frame, text="No accounts locally.\nAdd one to sync with Cloud.",
                                 bg="#f0f0f0", fg="#777", font=("Segoe UI", 12))
            lbl_empty.pack(pady=50, padx=60)
            return

        for acc in accounts:
            self.create_account_row(acc)

    def create_account_row(self, account):
        card = tk.Frame(self.scrollable_frame, bg="white", bd=0, highlightbackground="#ddd", highlightthickness=1)
        card.pack(fill=tk.X, pady=5, padx=5, ipady=5)

        letter = account['issuer'][0].upper() if account['issuer'] else "?"
        lbl_icon = tk.Label(card, text=letter, bg="#eee", fg="#555", width=3, height=2, font=("Arial", 14, "bold"))
        lbl_icon.pack(side=tk.LEFT, padx=10)

        info_frame = tk.Frame(card, bg="white")
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lbl_issuer = tk.Label(info_frame, text=account['issuer'], bg="white", font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_issuer.pack(fill=tk.X)
        lbl_name = tk.Label(info_frame, text=account['name'], bg="white", fg="#777", font=("Segoe UI", 9), anchor="w")
        lbl_name.pack(fill=tk.X)

        code_frame = tk.Frame(card, bg="white")
        code_frame.pack(side=tk.RIGHT, padx=15)
        lbl_code = tk.Label(code_frame, text="------", bg="white", fg="#007bff", font=("Consolas", 18, "bold"))
        lbl_code.pack(anchor="e")
        progress = ttk.Progressbar(code_frame, orient="horizontal", length=80, mode="determinate")
        progress.pack(pady=2)

        self.account_widgets.append({
            "secret": account['secret'],
            "lbl_code": lbl_code,
            "progress": progress
        })

    def refresh_timer(self):
        current_time = time.time()
        seconds_remaining = 30 - (int(current_time) % 30)

        for widget_set in self.account_widgets:
            new_code = totp_engine.get_totp_token(widget_set['secret'])
            formatted_code = f"{new_code[:3]} {new_code[3:]}"
            widget_set['lbl_code'].config(text=formatted_code)
            widget_set['progress']['value'] = (seconds_remaining / 30) * 100

            if seconds_remaining < 5:
                widget_set['lbl_code'].config(fg="#dc3545")
            else:
                widget_set['lbl_code'].config(fg="#007bff")

        self.root.after(1000, self.refresh_timer)

    def upload_to_cloud_async(self, issuer, name, secret):
        """Sends the secret to the Flask server in a background thread."""

        def _upload():
            try:
                payload = {"issuer": issuer, "name": name, "secret": secret}
                requests.post(f"{SERVER_URL}/upload", json=payload, timeout=3)
                print(f"[CLOUD] Uploaded: {name}")
            except Exception as e:
                print(f"[CLOUD] Upload Failed: {e}")

        threading.Thread(target=_upload, daemon=True).start()

    def open_add_dialog(self):
        popup = tk.Toplevel(self.root)
        popup.title("Add Account")
        popup.geometry("300x200")
        tk.Label(popup, text="How do you want to scan?", font=("Segoe UI", 12)).pack(pady=20)

        tk.Button(popup, text="📷 Use Webcam", width=20, pady=5,
                  command=lambda: self.handle_scan(popup, "webcam")).pack(pady=5)
        tk.Button(popup, text="📂 Upload Screenshot", width=20, pady=5,
                  command=lambda: self.handle_scan(popup, "file")).pack(pady=5)

    def handle_scan(self, popup, mode):
        popup.destroy()
        accounts = []
        if mode == "webcam":
            messagebox.showinfo("Scanner", "Webcam window will open.\nPress 'q' to close it.")
            accounts = universal_scanner.run_webcam_scan()
        else:
            accounts = universal_scanner.select_file_and_scan()

        if accounts:
            saved_count = 0
            for acc in accounts:
                # 1. Save Locally
                if database_manager.add_account(acc['issuer'], acc['name'], acc['secret']):
                    saved_count += 1
                    # 2. Upload to Cloud (Auto-Sync)
                    self.upload_to_cloud_async(acc['issuer'], acc['name'], acc['secret'])

            if saved_count > 0:
                messagebox.showinfo("Success", f"Saved {saved_count} new accounts!\nSyncing to Cloud...")
                self.load_accounts()
            else:
                messagebox.showwarning("Duplicate", "Account(s) already exist.")
        else:
            messagebox.showerror("Error", "No QR code found.")


if __name__ == "__main__":
    database_manager.init_db()
    root = tk.Tk()
    app = AuthenticatorApp(root)
    root.mainloop()