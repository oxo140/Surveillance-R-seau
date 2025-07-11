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
SCAN_FREQUENCE_MIN = 2
ANTI_SPAM_MIN = 90
PING_SERIES = 4  # Nombre de séries de pings à effectuer
PING_PER_SERIE = 10  # Nombre de pings par série
DELAI_ENTRE_SERIES = 5  # Délai en secondes entre les séries

HEURE_DEBUT_SILENCE = dt_time(21, 30)
HEURE_FIN_SILENCE = dt_time(7, 30)

derniers_alertes = {}
anti_spam_reset = {}
surveillance_active = True

# --- Interface graphique ---
app = tk.Tk()
app.title("Surveillance Réseau Automatisée")
app.geometry("800x500")

log_text = tk.Text(app, height=25, wrap="word")
log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
log_text.config(state=tk.DISABLED)

def log(message, couleur="black"):
    """Enregistre un message dans l'interface et le fichier de log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne = f"[{timestamp}] {message}"
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, ligne + "\n", couleur)
    log_text.tag_config(couleur, foreground=couleur)
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")

    nettoyer_anciens_logs()

def nettoyer_anciens_logs():
    """Nettoie les logs plus vieux que 7 jours"""
    if not os.path.exists(LOG_FILE):
        return

    lignes_valides = []
    now = datetime.now()
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for ligne in f:
                if ligne.startswith("["):
                    try:
                        date_str = ligne.split("]")[0].strip("[")
                        date_log = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if now - date_log <= timedelta(days=7):
                            lignes_valides.append(ligne)
                    except ValueError:
                        pass
    except Exception as e:
        log(f"Erreur lecture log pour nettoyage : {e}", "red")
        return

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.writelines(lignes_valides)
    except Exception as e:
        log(f"Erreur écriture log nettoyé : {e}", "red")

def mail_autorise():
    """Vérifie si l'envoi de mail est autorisé selon les heures de silence"""
    now = datetime.now().time()
    if HEURE_DEBUT_SILENCE < HEURE_FIN_SILENCE:
        return not (HEURE_DEBUT_SILENCE <= now < HEURE_FIN_SILENCE)
    else:
        return not (now >= HEURE_DEBUT_SILENCE or now < HEURE_FIN_SILENCE)

def envoyer_mail(nom, ip, message):
    """Envoie un email d'alerte si autorisé"""
    if not mail_autorise():
        log(f"Mail non envoyé pour {nom} ({ip}) - en dehors des heures autorisées", "orange")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_EXPEDITEUR
        msg["To"] = EMAIL_DESTINATAIRE
        msg["Subject"] = f"Alerte : {nom} ({ip})"
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as serveur:
            serveur.starttls()
            serveur.login(EMAIL_EXPEDITEUR, EMAIL_MDP_APP)
            serveur.send_message(msg)

        log(f"Mail envoyé pour {nom} ({ip})", "red")
    except Exception as e:
        log(f"Erreur envoi mail : {e}", "red")

def ping_host(ip):
    """Effectue plusieurs séries de pings pour vérifier la disponibilité"""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    successes = 0

    for serie in range(PING_SERIES):
        log(f"Série de ping {serie+1}/{PING_SERIES} pour {ip}...", "blue")
        for _ in range(PING_PER_SERIE):
            result = subprocess.run(["ping", param, "1", ip],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True)
            if "TTL=" in result.stdout or "ttl=" in result.stdout:
                successes += 1
                break  # Si un ping réussit, on passe à la série suivante
            time.sleep(1)

        if successes > 0:
            return True  # Si au moins une série a réussi

        if serie < PING_SERIES - 1:  # Pas besoin d'attendre après la dernière série
            time.sleep(DELAI_ENTRE_SERIES)

    return False

def surveiller():
    """Boucle principale de surveillance des équipements"""
    global surveillance_active
    while surveillance_active:
        if not os.path.exists(CSV_PATH):
            log("Fichier equipements.csv non trouvé", "red")
            time.sleep(SCAN_FREQUENCE_MIN * 60)
            continue

        try:
            df = pd.read_csv(CSV_PATH)
            if "hostname" not in df.columns or "ip" not in df.columns:
                log("Erreur : colonnes 'hostname' et 'ip' manquantes", "red")
                time.sleep(SCAN_FREQUENCE_MIN * 60)
                continue

            log(f"--- Scan à {datetime.now().strftime('%H:%M:%S')} ---", "blue")
            for _, row in df.iterrows():
                nom = str(row["hostname"]).strip()
                ip = str(row["ip"]).strip()

                if not nom or not ip:
                    log("Ligne incomplète dans le CSV (ignorée)", "orange")
                    continue

                log(f"Test de connexion pour {nom} ({ip})...", "blue")
                if ping_host(ip):
                    log(f"{nom} ({ip}) répond.", "green")
                    if ip in derniers_alertes:
                        envoyer_mail(nom, ip, f"L'hôte {nom} ({ip}) répond à nouveau après une indisponibilité.")
                        del derniers_alertes[ip]
                else:
                    now = datetime.now()
                    derniere = derniers_alertes.get(ip)
                    if not derniere or (now - derniere) >= timedelta(minutes=ANTI_SPAM_MIN):
                        message = (f"L'hôte {nom} ({ip}) ne répond pas après "
                                  f"{PING_SERIES} séries de {PING_PER_SERIE} pings chacune.")
                        envoyer_mail(nom, ip, message)
                        derniers_alertes[ip] = now
                    else:
                        log(f"{nom} ({ip}) ne répond pas, mais anti-spam actif (moins de {ANTI_SPAM_MIN} min)", "orange")

        except Exception as e:
            log(f"Erreur de traitement : {e}", "red")

        # Attente avant le prochain scan
        for _ in range(SCAN_FREQUENCE_MIN * 60):
            if not surveillance_active:
                return
            time.sleep(1)

def on_close():
    """Fermeture propre de l'application"""
    global surveillance_active
    surveillance_active = False
    app.destroy()

if __name__ == "__main__":
    # Lancement automatique de la surveillance
    threading.Thread(target=surveiller, daemon=True).start()
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()
