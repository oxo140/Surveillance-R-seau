import tkinter as tk
import subprocess
import platform
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import pandas as pd
import time
import threading
import os

# --- Configuration e-mail ---
EMAIL_EXPEDITEUR = "expediteur@exemple.com"
EMAIL_MDP_APP = "mdpappsansespace"
EMAIL_DESTINATAIRE = "destinataire@exemple.com"

CSV_PATH = "equipements.csv"
LOG_FILE = "log_surveillance.txt"
SCAN_FREQUENCE_MIN = 1
ANTI_SPAM_MIN = 60

derniers_alertes = {}  # {ip: datetime}
surveillance_active = True

# --- Application Tkinter ---
app = tk.Tk()
app.title("Surveillance Automatique Réseau")
app.geometry("800x500")

log_text = tk.Text(app, height=25, wrap="word")
log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
log_text.config(state=tk.DISABLED)

# --- Fonctions ---
def log(message, couleur="black"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    ligne = f"[{timestamp}] {message}"
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, ligne + "\n", couleur)
    log_text.tag_config(couleur, foreground=couleur)
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")

def envoyer_mail(nom, ip):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_EXPEDITEUR
        msg["To"] = EMAIL_DESTINATAIRE
        msg["Subject"] = f"Alerte : {nom} ({ip}) injoignable"
        corps = f"L'hôte {nom} ({ip}) ne répond pas après 4 tentatives de ping.\nVoir log joint pour détails."
        msg.attach(MIMEText(corps, "plain"))

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={LOG_FILE}")
                msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as serveur:
            serveur.starttls()
            serveur.login(EMAIL_EXPEDITEUR, EMAIL_MDP_APP)
            serveur.send_message(msg)

        log(f"Mail envoyé pour {nom} ({ip}) avec le journal", "red")
    except Exception as e:
        log(f"Erreur envoi mail : {e}", "red")

def ping_host(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    for _ in range(4):
        result = subprocess.run(["ping", param, "1", ip],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        if "TTL=" in result.stdout or "ttl=" in result.stdout:
            return True
        time.sleep(1)
    return False

def surveiller():
    global surveillance_active
    while surveillance_active:
        if not os.path.exists(CSV_PATH):
            log("Fichier equipements.csv non trouvé", "red")
            time.sleep(SCAN_FREQUENCE_MIN * 60)
            continue

        try:
            df = pd.read_csv(CSV_PATH)
            if "hostname" not in df.columns or "ip" not in df.columns:
                log("CSV invalide : colonnes manquantes", "red")
                time.sleep(SCAN_FREQUENCE_MIN * 60)
                continue

            log(f"--- Scan à {datetime.now().strftime('%H:%M:%S')} ---", "blue")
            for _, row in df.iterrows():
                nom = str(row["hostname"])
                ip = str(row["ip"])
                log(f"Ping {nom} ({ip})...", "blue")

                if ping_host(ip):
                    log(f"{nom} ({ip}) répond.", "green")
                else:
                    now = datetime.now()
                    derniere = derniers_alertes.get(ip)
                    if not derniere or (now - derniere) >= timedelta(minutes=ANTI_SPAM_MIN):
                        envoyer_mail(nom, ip)
                        derniers_alertes[ip] = now
                    else:
                        log(f"{nom} ({ip}) ne répond pas, mais anti-spam actif (moins de {ANTI_SPAM_MIN} min)", "orange")

        except Exception as e:
            log(f"Erreur de traitement : {e}", "red")

        for _ in range(SCAN_FREQUENCE_MIN * 60):
            if not surveillance_active:
                return
            time.sleep(1)

def on_close():
    global surveillance_active
    surveillance_active = False
    app.destroy()

# --- Lancement automatique ---
threading.Thread(target=surveiller, daemon=True).start()
app.protocol("WM_DELETE_WINDOW", on_close)
app.mainloop()
