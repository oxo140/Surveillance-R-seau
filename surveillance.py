import tkinter as tk
import subprocess
import platform
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, time as dt_time
import pandas as pd
import time
import threading
import os

# --- Configuration ---
EMAIL_EXPEDITEUR = "EMAIL_EXPEDITEUR@gmail.com"
EMAIL_MDP_APP = "mots de passe gmail"
EMAIL_DESTINATAIRE = "EMAIL_DESTINATAIRE@gmail.com"

CSV_PATH = "equipements.csv"
LOG_FILE = "log_surveillance.txt"
SCAN_FREQUENCE_MIN = 5
PING_COUNT = 10
MAX_FAILURES = 4
ANTI_SPAM_MIN = 90

HEURE_DEBUT_SILENCE = dt_time(21, 30)
HEURE_FIN_SILENCE = dt_time(7, 30)

# Dictionnaires pour suivre l'état des équipements
equipment_status = {
    # Format: {ip: {'failures': 0, 'was_down': False, 'hostname': "nom", 'last_failure': datetime, 'last_alert': datetime}}
}

surveillance_active = True

# Interface graphique
app = tk.Tk()
app.title("Surveillance Réseau")
app.geometry("800x500")

log_text = tk.Text(app, height=25, wrap="word")
log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
log_text.config(state=tk.DISABLED)

def log(message, couleur="black"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne = f"[{timestamp}] {message}"
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, ligne + "\n", couleur)
    log_text.tag_config(couleur, foreground=couleur)
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")

def envoyer_mail(ip, status):
    now = datetime.now()
    current_time = now.time()

    # Vérification période de silence
    if HEURE_DEBUT_SILENCE < HEURE_FIN_SILENCE:
        if HEURE_DEBUT_SILENCE <= current_time <= HEURE_FIN_SILENCE:
            return False
    else:
        if current_time >= HEURE_DEBUT_SILENCE or current_time <= HEURE_FIN_SILENCE:
            return False

    # Vérification anti-spam
    last_alert = equipment_status[ip]['last_alert']
    if last_alert and (now - last_alert) < timedelta(minutes=ANTI_SPAM_MIN):
        return False

    # Création du mail
    hostname = equipment_status[ip]['hostname']
    equipement_id = f"{hostname} ({ip})" if hostname else ip

    message_email = MIMEMultipart()
    message_email["From"] = EMAIL_EXPEDITEUR
    message_email["To"] = EMAIL_DESTINATAIRE

    if status == "down":
        subject = f"ALERTE: Équipement hors ligne - {equipement_id}"
        body = f"L'équipement {equipement_id} est hors ligne après {MAX_FAILURES} tests consécutifs."
    else:
        subject = f"RÉTABLISSEMENT: Équipement de nouveau en ligne - {equipement_id}"
        body = f"L'équipement {equipement_id} est de nouveau en ligne après avoir été hors service."

    message_email["Subject"] = subject
    message_email.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_EXPEDITEUR, EMAIL_MDP_APP)
            server.sendmail(EMAIL_EXPEDITEUR, EMAIL_DESTINATAIRE, message_email.as_string())
        log(f"Mail envoyé: {equipement_id} - {status}", "green")
        equipment_status[ip]['last_alert'] = now
        return True
    except Exception as e:
        log(f"Erreur envoi mail pour {equipement_id}: {str(e)}", "red")
        return False

def ping_host(ip):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, str(PING_COUNT), ip]

    try:
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return output.returncode == 0
    except subprocess.TimeoutExpired:
        return False

def surveiller():
    global surveillance_active

    while surveillance_active:
        try:
            # Chargement du fichier CSV
            try:
                df = pd.read_csv(CSV_PATH)
                if 'ip' not in df.columns or 'hostname' not in df.columns:
                    log("Erreur: Le fichier CSV doit contenir les colonnes 'hostname' et 'ip'", "red")
                    time.sleep(60)
                    continue
            except Exception as e:
                log(f"Erreur lecture CSV: {str(e)}", "red")
                time.sleep(60)
                continue

            log(f"Début du cycle de surveillance - {len(df)} équipements à vérifier", "blue")

            # Initialisation des équipements
            for _, row in df.iterrows():
                ip = str(row['ip']).strip()
                hostname = str(row['hostname']).strip()

                if ip not in equipment_status:
                    equipment_status[ip] = {
                        'failures': 0,
                        'was_down': False,
                        'hostname': hostname,
                        'last_failure': None,
                        'last_alert': None
                    }

            # Vérification des équipements
            for _, row in df.iterrows():
                ip = str(row['ip']).strip()
                hostname = str(row['hostname']).strip()
                equipement_id = f"{hostname} ({ip})"

                if ping_host(ip):
                    log(f"OK: {equipement_id} répond", "green")

                    if equipment_status[ip]['was_down']:
                        # Équipement redevenu disponible
                        if envoyer_mail(ip, "up"):
                            equipment_status[ip]['was_down'] = False
                        equipment_status[ip]['failures'] = 0
                    else:
                        # Équipement toujours disponible
                        equipment_status[ip]['failures'] = 0
                else:
                    equipment_status[ip]['failures'] += 1
                    equipment_status[ip]['last_failure'] = datetime.now()
                    equipment_status[ip]['was_down'] = True
                    log(f"ERREUR: {equipement_id} ne répond pas (échecs: {equipment_status[ip]['failures']})", "red")

                    if equipment_status[ip]['failures'] >= MAX_FAILURES:
                        envoyer_mail(ip, "down")

        except Exception as e:
            log(f"Erreur dans le cycle de surveillance: {str(e)}", "red")

        # Attente avant le prochain cycle
        for _ in range(SCAN_FREQUENCE_MIN * 60):
            if not surveillance_active:
                return
            time.sleep(1)

def on_close():
    global surveillance_active
    surveillance_active = False
    app.destroy()

if __name__ == "__main__":
    threading.Thread(target=surveiller, daemon=True).start()
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()
