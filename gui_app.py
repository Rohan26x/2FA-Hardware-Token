import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import requests
import serial
import serial.tools.list_ports

import totp_engine
import universal_scanner

# --- CONFIGURATION ---
SERVER_URL = "https://esp32-cloud-backend-9mic9lvwo-rohan-patels-projects-f8b9837d.vercel.app/api"

# --- SESSION STORAGE ---
session = {
    "token":      None,
    "username":   None,
    "user_id":    None,
    "device_key": None
}

def get_headers():
    return {"Authorization": f"Bearer {session['token']}"}


# ============================================================
#  LOGIN SCREEN
# ============================================================
class LoginScreen:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success

        self.root.title("2FA Hardware Token — Login")
        self.root.geometry("380x480")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)

        tk.Label(root, text="🔐", font=("Segoe UI", 40),
                 bg="#1a1a2e").pack(pady=(40, 5))
        tk.Label(root, text="2FA Hardware Token",
                 font=("Segoe UI", 16, "bold"),
                 bg="#1a1a2e", fg="white").pack()
        tk.Label(root, text="Cloud Authenticator",
                 font=("Segoe UI", 10),
                 bg="#1a1a2e", fg="#888").pack(pady=(2, 30))

        card = tk.Frame(root, bg="#16213e", padx=30, pady=30)
        card.pack(fill=tk.X, padx=30)

        self.mode = tk.StringVar(value="login")
        self.lbl_mode = tk.Label(card, text="Sign In",
                                  font=("Segoe UI", 13, "bold"),
                                  bg="#16213e", fg="white")
        self.lbl_mode.pack(anchor="w", pady=(0, 20))

        tk.Label(card, text="Username", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.entry_user = tk.Entry(card, font=("Segoe UI", 11),
                                    bg="#0f3460", fg="white",
                                    insertbackground="white",
                                    relief="flat", bd=5)
        self.entry_user.pack(fill=tk.X, pady=(2, 12))

        tk.Label(card, text="Password", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.entry_pass = tk.Entry(card, font=("Segoe UI", 11),
                                    bg="#0f3460", fg="white",
                                    insertbackground="white",
                                    relief="flat", bd=5, show="•")
        self.entry_pass.pack(fill=tk.X, pady=(2, 20))
        self.entry_pass.bind("<Return>", lambda e: self.submit())

        self.btn_submit = tk.Button(card, text="Sign In",
                                     bg="#e94560", fg="white",
                                     font=("Segoe UI", 11, "bold"),
                                     relief="flat", padx=10, pady=8,
                                     cursor="hand2", command=self.submit)
        self.btn_submit.pack(fill=tk.X)

        self.lbl_status = tk.Label(card, text="", bg="#16213e",
                                    fg="#e94560", font=("Segoe UI", 9),
                                    wraplength=280)
        self.lbl_status.pack(pady=(10, 0))

        toggle_frame = tk.Frame(root, bg="#1a1a2e")
        toggle_frame.pack(pady=15)
        self.lbl_toggle_text = tk.Label(toggle_frame,
                                         text="Don't have an account?",
                                         bg="#1a1a2e", fg="#888",
                                         font=("Segoe UI", 9))
        self.lbl_toggle_text.pack(side=tk.LEFT)
        self.btn_toggle = tk.Button(toggle_frame, text=" Register",
                                     bg="#1a1a2e", fg="#e94560",
                                     font=("Segoe UI", 9, "bold"),
                                     relief="flat", cursor="hand2",
                                     command=self.toggle_mode)
        self.btn_toggle.pack(side=tk.LEFT)

    def toggle_mode(self):
        if self.mode.get() == "login":
            self.mode.set("register")
            self.lbl_mode.config(text="Create Account")
            self.btn_submit.config(text="Register")
            self.btn_toggle.config(text=" Sign In")
            self.lbl_toggle_text.config(text="Already have an account?")
        else:
            self.mode.set("login")
            self.lbl_mode.config(text="Sign In")
            self.btn_submit.config(text="Sign In")
            self.btn_toggle.config(text=" Register")
            self.lbl_toggle_text.config(text="Don't have an account?")

    def submit(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()

        if not username or not password:
            self.lbl_status.config(text="Please fill in all fields.")
            return
        if len(password) < 6:
            self.lbl_status.config(
                text="Password must be at least 6 characters.")
            return

        self.btn_submit.config(state="disabled", text="Please wait...")
        self.lbl_status.config(text="")

        endpoint = "login" if self.mode.get() == "login" else "register"
        threading.Thread(target=self._do_request,
                         args=(endpoint, username, password),
                         daemon=True).start()

    def _do_request(self, endpoint, username, password):
        try:
            response = requests.post(
                f"{SERVER_URL}/{endpoint}",
                json={"username": username, "password": password},
                timeout=10
            )
            data = response.json()

            if response.status_code in (200, 201):
                if endpoint == "login":
                    session["token"]    = data["token"]
                    session["username"] = data["username"]
                    # Silently fetch device credentials in background
                    self._fetch_device_config()
                    self.root.after(0, self.on_success)
                else:
                    self.root.after(0, lambda: self.lbl_status.config(
                        text="Account created! Please sign in.",
                        fg="#28a745"))
                    self.root.after(0, self.toggle_mode)
            else:
                msg = data.get("message", "An error occurred.")
                self.root.after(0, lambda: self.lbl_status.config(
                    text=msg, fg="#e94560"))
        except Exception:
            self.root.after(0, lambda: self.lbl_status.config(
                text="Cannot reach server. Check connection.",
                fg="#e94560"))
        finally:
            def safe_reset():
                try:
                    self.btn_submit.config(
                        state="normal",
                        text="Sign In" if self.mode.get() == "login"
                        else "Register")
                except tk.TclError:
                    pass
            self.root.after(0, safe_reset)

    def _fetch_device_config(self):
        """Silently fetch user_id and device_key after login."""
        try:
            r = requests.get(f"{SERVER_URL}/device/token",
                             headers=get_headers(), timeout=5)
            if r.status_code == 200:
                data = r.json()
                session["user_id"]    = data["user_id"]
                session["device_key"] = data["device_key"]
        except Exception:
            pass  # Non-fatal — WiFi dialog will show error if missing


# ============================================================
#  MAIN DASHBOARD
# ============================================================
class AuthenticatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"2FA Tokens — {session['username']}")
        self.root.geometry("460x660")
        self.root.configure(bg="#f0f0f0")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar",
                         troughcolor="#eee", background="#007bff")

        # ── Header ──────────────────────────────────────────
        header = tk.Frame(root, bg="#1a1a2e", height=65)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🔐  My 2FA Tokens",
                 bg="#1a1a2e", fg="white",
                 font=("Segoe UI", 15, "bold")).pack(
                     side=tk.LEFT, padx=20, pady=18)
        tk.Label(header, text=f"👤 {session['username']}",
                 bg="#1a1a2e", fg="#888",
                 font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=20)

        # ── Status bar ──────────────────────────────────────
        self.status_var = tk.StringVar(value="Syncing...")
        tk.Label(root, textvariable=self.status_var,
                 bg="#f0f0f0", fg="#555",
                 font=("Segoe UI", 8)).pack(pady=2)

        # ── Footer (packed BEFORE canvas) ───────────────────
        footer = tk.Frame(root, bg="#e0e0e0")
        footer.pack(fill=tk.X, side="bottom")

        tk.Button(footer, text="+ Add Account",
                  bg="#28a745", fg="white",
                  font=("Segoe UI", 11, "bold"), relief="flat",
                  padx=20, pady=10, cursor="hand2",
                  command=self.open_add_dialog).pack(
                      side=tk.LEFT, padx=10, pady=10)

        tk.Button(footer, text="⟳ Sync",
                  bg="#0d6efd", fg="white",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=12, pady=10, cursor="hand2",
                  command=self.fetch_accounts).pack(
                      side=tk.LEFT, pady=10)

        tk.Button(footer, text="📶 Setup Device",
                  bg="#6f42c1", fg="white",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=12, pady=10, cursor="hand2",
                  command=self.open_wifi_dialog).pack(
                      side=tk.LEFT, padx=8, pady=10)

        # ── Scrollable list ──────────────────────────────────
        list_frame = tk.Frame(root, bg="#f0f0f0")
        list_frame.pack(fill="both", expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(list_frame, bg="#f0f0f0",
                                highlightthickness=0,
                                yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both",
                         expand=True, padx=(10, 0))

        scrollbar.config(command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas, bg="#f0f0f0")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(
                self.canvas_window, width=e.width))

        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))

        self.account_widgets = []
        self.accounts_data   = []
        self.refresh_timer()
        self.fetch_accounts()

    # ── Fetch accounts ───────────────────────────────────────
    def fetch_accounts(self):
        def _fetch():
            try:
                self.status_var.set("Syncing with Cloud...")
                r = requests.get(f"{SERVER_URL}/fetch",
                                 headers=get_headers(), timeout=5)
                if r.status_code == 200:
                    self.accounts_data = r.json()
                    self.root.after(0, self.rebuild_ui)
                    self.status_var.set(
                        f"● Synced  —  {len(self.accounts_data)} accounts")
                elif r.status_code == 401:
                    self.status_var.set("○ Session expired. Please restart.")
                else:
                    self.status_var.set(f"○ Server error {r.status_code}")
            except Exception:
                self.status_var.set("○ Could not reach cloud")
        threading.Thread(target=_fetch, daemon=True).start()

    # ── Rebuild UI ───────────────────────────────────────────
    def rebuild_ui(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.account_widgets = []

        if not self.accounts_data:
            tk.Label(self.scrollable_frame,
                     text="No accounts yet.\nClick '+ Add Account' to start!",
                     bg="#f0f0f0", fg="#777",
                     font=("Segoe UI", 12)).pack(pady=50)
            return

        for acc in self.accounts_data:
            self.create_account_row(acc)

    # ── Account card ─────────────────────────────────────────
    def create_account_row(self, account):
        card = tk.Frame(self.scrollable_frame, bg="white",
                        highlightbackground="#ddd", highlightthickness=1)
        card.pack(fill=tk.X, pady=4, padx=(0, 5), ipady=6)

        letter = (account.get('issuer') or "?")[0].upper()
        tk.Label(card, text=letter, bg="#e8f0fe", fg="#1a73e8",
                 width=3, height=2,
                 font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)

        info = tk.Frame(card, bg="white")
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(info, text=account.get('issuer', 'Unknown'),
                 bg="white", font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill=tk.X)
        tk.Label(info, text=account.get('name', ''),
                 bg="white", fg="#777",
                 font=("Segoe UI", 9), anchor="w").pack(fill=tk.X)

        right = tk.Frame(card, bg="white")
        right.pack(side=tk.RIGHT, padx=10)

        lbl_code = tk.Label(right, text="------", bg="white",
                             fg="#007bff",
                             font=("Consolas", 18, "bold"))
        lbl_code.pack(anchor="e")

        progress = ttk.Progressbar(right, orient="horizontal",
                                    length=80, mode="determinate")
        progress.pack(pady=2)

        acc_id = account.get('id')
        tk.Button(right, text="🗑", bg="white", fg="#dc3545",
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=lambda i=acc_id: self.delete_account(i)).pack()

        lbl_code.bind("<Button-1>",
                      lambda e, l=lbl_code: self.copy_code(l))

        self.account_widgets.append({
            "secret":   account['secret'],
            "lbl_code": lbl_code,
            "progress": progress
        })

    def copy_code(self, label):
        code = label.cget("text").replace(" ", "")
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        label.config(bg="#d4edda")
        self.root.after(300, lambda: label.config(bg="white"))

    # ── Delete account ───────────────────────────────────────
    def delete_account(self, acc_id):
        if not messagebox.askyesno(
                "Delete Account",
                "Remove this account from the cloud?\nThis cannot be undone."):
            return

        def _delete():
            try:
                r = requests.delete(f"{SERVER_URL}/delete",
                                    headers=get_headers(),
                                    json={"id": acc_id}, timeout=5)
                if r.status_code == 200:
                    self.root.after(0, self.fetch_accounts)
                    messagebox.showinfo("Deleted", "Account removed successfully.")
                else:
                    messagebox.showerror("Error", f"Could not delete:\n{r.text}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        threading.Thread(target=_delete, daemon=True).start()

    # ── Live TOTP refresh ────────────────────────────────────
    def refresh_timer(self):
        seconds_remaining = 30 - (int(time.time()) % 30)
        for w in self.account_widgets:
            try:
                code = totp_engine.get_totp_token(w['secret'])
                w['lbl_code'].config(
                    text=f"{code[:3]} {code[3:]}",
                    fg="#dc3545" if seconds_remaining <= 5 else "#007bff")
                w['progress']['value'] = (seconds_remaining / 30) * 100
            except Exception:
                pass
        self.root.after(1000, self.refresh_timer)

    # ── Setup Device dialog ──────────────────────────────────
    # Sends WiFi credentials AND cloud auth config to ESP32 in one step.
    # The user only needs to enter their WiFi name and password.
    def open_wifi_dialog(self):
        popup = tk.Toplevel(self.root)
        popup.title("Setup Hardware Token")
        popup.geometry("400x500")
        popup.configure(bg="#1a1a2e")
        popup.resizable(False, False)

        tk.Label(popup, text="📶  Setup Hardware Token",
                 font=("Segoe UI", 14, "bold"),
                 bg="#1a1a2e", fg="white").pack(pady=(25, 4))
        tk.Label(popup,
                 text="Connect your ESP32 via USB,\nthen fill in your WiFi details below.",
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#888",
                 justify=tk.CENTER).pack(pady=(0, 18))

        card = tk.Frame(popup, bg="#16213e", padx=25, pady=22)
        card.pack(fill=tk.X, padx=25)

        # ── Step indicator ───────────────────────────────────
        steps = tk.Frame(card, bg="#16213e")
        steps.pack(fill=tk.X, pady=(0, 18))
        for i, label in enumerate(["① USB", "② WiFi", "③ Done"], 1):
            tk.Label(steps, text=label, bg="#16213e",
                     fg="#28a745" if i == 1 else "#555",
                     font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, expand=True)

        # ── COM port ─────────────────────────────────────────
        tk.Label(card, text="COM Port", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w")
        port_frame = tk.Frame(card, bg="#16213e")
        port_frame.pack(fill=tk.X, pady=(2, 14))

        ports    = [p.device for p in serial.tools.list_ports.comports()]
        port_var = tk.StringVar(
            value=ports[0] if ports else "No ports found")
        port_menu = ttk.Combobox(port_frame, textvariable=port_var,
                                  values=ports, state="readonly",
                                  font=("Segoe UI", 10))
        port_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def refresh_ports():
            new_ports = [p.device
                         for p in serial.tools.list_ports.comports()]
            port_menu['values'] = new_ports
            port_var.set(new_ports[0] if new_ports else "No ports found")

        tk.Button(port_frame, text="⟳", bg="#0f3460", fg="white",
                  relief="flat", font=("Segoe UI", 10), cursor="hand2",
                  command=refresh_ports).pack(side=tk.LEFT, padx=(5, 0))

        # ── SSID ─────────────────────────────────────────────
        tk.Label(card, text="WiFi Name (SSID)", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w")
        entry_ssid = tk.Entry(card, font=("Segoe UI", 11), bg="#0f3460",
                               fg="white", insertbackground="white",
                               relief="flat", bd=5)
        entry_ssid.pack(fill=tk.X, pady=(2, 14))

        # ── Password ─────────────────────────────────────────
        tk.Label(card, text="WiFi Password", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(anchor="w")
        pass_frame = tk.Frame(card, bg="#16213e")
        pass_frame.pack(fill=tk.X, pady=(2, 6))

        entry_pass = tk.Entry(pass_frame, font=("Segoe UI", 11),
                               bg="#0f3460", fg="white",
                               insertbackground="white",
                               relief="flat", bd=5, show="•")
        entry_pass.pack(side=tk.LEFT, fill=tk.X, expand=True)

        show_var = tk.BooleanVar(value=False)
        def toggle_pass():
            entry_pass.config(show="" if show_var.get() else "•")
        tk.Checkbutton(pass_frame, text="Show", variable=show_var,
                       bg="#16213e", fg="#aaa", selectcolor="#0f3460",
                       activebackground="#16213e", font=("Segoe UI", 9),
                       command=toggle_pass).pack(side=tk.LEFT, padx=(8, 0))

        # ── Info note ────────────────────────────────────────
        tk.Label(card,
                 text="Your account credentials are sent automatically.",
                 bg="#16213e", fg="#555",
                 font=("Segoe UI", 8),
                 wraplength=300).pack(pady=(10, 0))

        # ── Status ───────────────────────────────────────────
        lbl_status = tk.Label(popup, text="", bg="#1a1a2e",
                               fg="#28a745", font=("Segoe UI", 9),
                               wraplength=340, justify=tk.CENTER)
        lbl_status.pack(pady=(12, 0), padx=25)

        # ── Progress bar ─────────────────────────────────────
        progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(popup, variable=progress_var,
                                        maximum=100, mode="determinate",
                                        length=340)
        progress_bar.pack(pady=(8, 0), padx=25)

        # ── Send button ──────────────────────────────────────
        def send_all():
            port     = port_var.get()
            ssid     = entry_ssid.get().strip()
            password = entry_pass.get().strip()

            if port == "No ports found":
                lbl_status.config(
                    text="❌ No COM port found.\nConnect your ESP32 via USB.",
                    fg="#e94560")
                return
            if not ssid:
                lbl_status.config(text="❌ Please enter your WiFi name.",
                                   fg="#e94560")
                return
            if not session.get("user_id") or not session.get("device_key"):
                lbl_status.config(
                    text="❌ Could not load account config.\nPlease restart the app.",
                    fg="#e94560")
                return

            btn_send.config(state="disabled", text="Configuring...")
            lbl_status.config(text="Connecting to ESP32...", fg="#aaa")
            progress_var.set(0)

            def _send():
                try:
                    with serial.Serial(port, 115200, timeout=3) as ser:

                        def update(msg, pct, color="#aaa"):
                            popup.after(0, lambda: lbl_status.config(
                                text=msg, fg=color))
                            popup.after(0, lambda: progress_var.set(pct))

                        # Wait for ESP32 to be ready
                        update("Waiting for ESP32...", 10)
                        time.sleep(2)

                        # Send WiFi SSID
                        update("Sending WiFi name...", 25)
                        ser.write(f"SSID:{ssid}\n".encode())
                        time.sleep(0.4)

                        # Send WiFi Password
                        update("Sending WiFi password...", 40)
                        ser.write(f"PASS:{password}\n".encode())
                        time.sleep(0.4)

                        # Send User ID
                        update("Sending account ID...", 60)
                        ser.write(f"UID:{session['user_id']}\n".encode())
                        time.sleep(0.4)

                        # Send Device API Key
                        update("Sending security key...", 75)
                        ser.write(f"DKEY:{session['device_key']}\n".encode())
                        time.sleep(0.4)

                        # Send done signal
                        ser.write(b"CONFIG_DONE\n")
                        time.sleep(0.5)

                        # Wait for confirmation
                        update("Waiting for confirmation...", 88)
                        response = ""
                        deadline = time.time() + 8
                        while time.time() < deadline:
                            if ser.in_waiting:
                                response += ser.read(
                                    ser.in_waiting).decode(errors='ignore')
                                if "CONFIG_SAVED" in response:
                                    break
                            time.sleep(0.1)

                    if "CONFIG_SAVED" in response:
                        update("✓ Device configured successfully!\n"
                               "Your ESP32 will now connect and sync automatically.",
                               100, "#28a745")
                    else:
                        update("⚠ No confirmation received.\n"
                               "Reset your ESP32 and try again.",
                               0, "#e94560")

                except serial.SerialException as e:
                    err = str(e)
                    popup.after(0, lambda: lbl_status.config(
                        text=f"❌ Serial error: {err}", fg="#e94560"))
                    popup.after(0, lambda: progress_var.set(0))
                except Exception as e:
                    err = str(e)
                    popup.after(0, lambda: lbl_status.config(
                        text=f"❌ Error: {err}", fg="#e94560"))
                    popup.after(0, lambda: progress_var.set(0))
                finally:
                    popup.after(0, lambda: btn_send.config(
                        state="normal", text="Configure Device"))

            threading.Thread(target=_send, daemon=True).start()

        btn_send = tk.Button(popup, text="Configure Device",
                              bg="#e94560", fg="white",
                              font=("Segoe UI", 11, "bold"),
                              relief="flat", padx=10, pady=10,
                              cursor="hand2", command=send_all)
        btn_send.pack(pady=14, padx=25, fill=tk.X)

        tk.Label(popup,
                 text="Tip: Press the RST button on your ESP32 just before clicking Configure.",
                 font=("Segoe UI", 8), bg="#1a1a2e", fg="#555",
                 wraplength=340).pack()

    # ── Add account ──────────────────────────────────────────
    def open_add_dialog(self):
        popup = tk.Toplevel(self.root)
        popup.title("Add Account")
        popup.geometry("300x180")
        popup.configure(bg="#f0f0f0")
        popup.resizable(False, False)
        tk.Label(popup, text="How do you want to scan?",
                 font=("Segoe UI", 12), bg="#f0f0f0").pack(pady=20)
        tk.Button(popup, text="📷  Use Webcam", width=22,
                  pady=6, cursor="hand2",
                  command=lambda: self.handle_scan(popup, "webcam")).pack(pady=5)
        tk.Button(popup, text="📂  Upload Screenshot", width=22,
                  pady=6, cursor="hand2",
                  command=lambda: self.handle_scan(popup, "file")).pack(pady=5)

    def handle_scan(self, popup, mode):
        popup.destroy()
        accounts = []
        if mode == "webcam":
            messagebox.showinfo("Scanner",
                                "Webcam window will open.\nPress 'q' to quit.")
            accounts = universal_scanner.run_webcam_scan()
        else:
            accounts = universal_scanner.select_file_and_scan()

        if not accounts:
            messagebox.showerror("Error", "No QR code found.")
            return

        def _upload():
            saved = 0
            for acc in accounts:
                try:
                    r = requests.post(f"{SERVER_URL}/upload",
                                      headers=get_headers(),
                                      json=acc, timeout=10)
                    if r.status_code == 201:
                        saved += 1
                except Exception:
                    pass
            if saved:
                messagebox.showinfo("Success",
                                    f"Saved {saved} account(s) to Cloud!")
                self.root.after(0, self.fetch_accounts)
            else:
                messagebox.showerror(
                    "Error", "Upload failed. Account may already exist.")

        threading.Thread(target=_upload, daemon=True).start()


# ============================================================
#  ENTRY POINT
# ============================================================
def launch_dashboard():
    for widget in root.winfo_children():
        widget.destroy()
    root.geometry("460x660")
    AuthenticatorApp(root)


root = tk.Tk()
LoginScreen(root, on_success=launch_dashboard)
root.mainloop()