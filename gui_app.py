import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import requests  # Requires: pip install requests
from PIL import Image, ImageTk

# Import your modules
import totp_engine
import universal_scanner

# --- CONFIGURATION ---
# Your Vercel URL
SERVER_URL = "https://esp32-cloud-backend-ien0egkwm-rohan-patels-projects-f8b9837d.vercel.app/api"


class AuthenticatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 Cloud Authenticator (Global)")
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
        lbl_title = tk.Label(header_frame, text="My Cloud 2FA Tokens", bg="#333", fg="white",
                             font=("Segoe UI", 16, "bold"))
        lbl_title.pack(pady=15)

        # --- CONNECTION STATUS ---
        self.status_var = tk.StringVar()
        self.status_var.set("Connecting to Cloud...")
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
        self.accounts_data = []  # Store accounts in memory

        # Start the refresh timer immediately
        self.refresh_timer()

        # Fetch accounts from cloud immediately
        self.fetch_accounts_from_cloud()

    def fetch_accounts_from_cloud(self):
        """Downloads the list of accounts from Vercel/Supabase."""

        def _fetch():
            try:
                self.status_var.set("Syncing with Cloud...")
                # Fetch from /fetch endpoint
                response = requests.get(f"{SERVER_URL}/fetch", timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    self.accounts_data = data  # Update local memory

                    # Update UI in main thread
                    self.root.after(0, self.refresh_ui_list)
                    self.status_var.set(f"● Synced with Cloud ({len(data)} accounts)")
                    self.root.nametowidget(self.root.winfo_children()[1]).config(fg="green")
                else:
                    self.status_var.set(f"○ Cloud Error: {response.status_code}")
                    self.root.nametowidget(self.root.winfo_children()[1]).config(fg="red")
            except Exception as e:
                print(e)
                self.status_var.set("○ Cloud Unreachable")
                self.root.nametowidget(self.root.winfo_children()[1]).config(fg="red")

        threading.Thread(target=_fetch, daemon=True).start()

    def refresh_ui_list(self):
        """Rebuilds the UI based on self.accounts_data."""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.account_widgets = []

        if not self.accounts_data:
            lbl_empty = tk.Label(self.scrollable_frame, text="No accounts in Cloud.\nAdd one to start!",
                                 bg="#f0f0f0", fg="#777", font=("Segoe UI", 12))
            lbl_empty.pack(pady=50, padx=60)
            return

        for acc in self.accounts_data:
            self.create_account_row(acc)

    def create_account_row(self, account):
        card = tk.Frame(self.scrollable_frame, bg="white", bd=0, highlightbackground="#ddd", highlightthickness=1)
        card.pack(fill=tk.X, pady=5, padx=5, ipady=5)

        letter = account['issuer'][0].upper() if account.get('issuer') else "?"
        lbl_icon = tk.Label(card, text=letter, bg="#eee", fg="#555", width=3, height=2, font=("Arial", 14, "bold"))
        lbl_icon.pack(side=tk.LEFT, padx=10)

        info_frame = tk.Frame(card, bg="white")
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lbl_issuer = tk.Label(info_frame, text=account.get('issuer', 'Unknown'), bg="white",
                              font=("Segoe UI", 10, "bold"), anchor="w")
        lbl_issuer.pack(fill=tk.X)
        lbl_name = tk.Label(info_frame, text=account.get('name', 'Unknown'), bg="white", fg="#777",
                            font=("Segoe UI", 9), anchor="w")
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
            try:
                new_code = totp_engine.get_totp_token(widget_set['secret'])
                formatted_code = f"{new_code[:3]} {new_code[3:]}"
                widget_set['lbl_code'].config(text=formatted_code)
                widget_set['progress']['value'] = (seconds_remaining / 30) * 100

                if seconds_remaining < 5:
                    widget_set['lbl_code'].config(fg="#dc3545")
                else:
                    widget_set['lbl_code'].config(fg="#007bff")
            except:
                pass  # Ignore invalid secrets temporarily

        self.root.after(1000, self.refresh_timer)

    def upload_to_cloud_async(self, issuer, name, secret):
        """Sends the secret to the Cloud and then refreshes the list."""

        def _upload():
            try:
                full_url = f"{SERVER_URL}/upload"
                print(f"[DEBUG] Posting to: {full_url}")

                payload = {"issuer": issuer, "name": name, "secret": secret}
                response = requests.post(full_url, json=payload, timeout=10)

                if response.status_code == 201 or response.status_code == 200:
                    print(f"[CLOUD] Upload SUCCESS: {name}")
                    messagebox.showinfo("Success", "Account saved to Cloud!")
                    # Refresh the list to show the new account
                    self.fetch_accounts_from_cloud()
                else:
                    print(f"[CLOUD] Upload FAILED!")
                    messagebox.showerror("Cloud Error", f"Server replied:\n{response.text}")

            except Exception as e:
                print(f"[CLOUD] Connection Failed: {e}")
                messagebox.showerror("Connection Error", str(e))

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
            for acc in accounts:
                # Direct Upload to Cloud (No local save)
                self.upload_to_cloud_async(acc['issuer'], acc['name'], acc['secret'])
        else:
            messagebox.showerror("Error", "No QR code found.")


if __name__ == "__main__":
    root = tk.Tk()
    app = AuthenticatorApp(root)
    root.mainloop()