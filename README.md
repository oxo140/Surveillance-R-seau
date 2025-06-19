# 🛰️ Supervision Réseau Automatisée (Ping + Alerte Email)

Ce projet est une application Python avec interface graphique (Tkinter) qui :

- Lit automatiquement un fichier `equipements.csv`
- Ping chaque IP 4 fois
- Envoie un email d'alerte avec pièce jointe (`log_surveillance.txt`) si l'hôte est injoignable
- Évite le spam en respectant un délai anti-alerte (anti-spam)
- Affiche et journalise tous les événements en temps réel

---

## 🖥️ Fonctionnement

- Le programme démarre automatiquement dès l'ouverture
- Il lit `equipements.csv` toutes les **1 minute**
- Si une IP ne répond pas après 4 pings :
  - Un mail est envoyé
  - Le fichier `log_surveillance.txt` est joint à l'email
- Un délai d'**1 heure** est appliqué avant d'autoriser un nouveau mail pour une IP déjà signalée


---
## 🖥️ Variables
🔁 SCAN_FREQUENCE_MIN = 1

    Fréquence de balayage réseau : une vérification est effectuée toutes les 1 minute.

🚫 ANTI_SPAM_MIN = 60

    Délai minimum entre deux alertes e-mail pour une même adresse IP : 60 minutes.

    Cela évite l'envoi répété d'e-mails pour un même problème persistant.

🌙 HEURE_DEBUT_SILENCE = 22h00
🌅 HEURE_FIN_SILENCE = 07h00

    Durant cette plage horaire (22h00 à 07h00), aucun e-mail ne sera envoyé, même si un hôte ne répond pas.

    La surveillance reste active, mais les notifications par e-mail sont suspendues pour éviter les dérangements nocturnes.

---

## 🗃️ Exemple de fichier `equipements.csv`

```csv
hostname,ip
Routeur,192.168.1.1
Caméra1,192.168.1.50
Serveur1,172.16.100.100
````

📝 Ce fichier doit être placé **dans le même dossier que le script Python**.

---

## ⚙️ Prérequis

* Python 3.8+
* Les bibliothèques suivantes (installables via pip) :

```bash
pip install pandas
```

Et facultativement :

```bash
pip install python-dotenv
```

---

## 🔐 Configuration de l’envoi de mail

### Étapes avec Gmail :

1. Activer l’**authentification à deux facteurs** sur ton compte Gmail
2. Créer un **mot de passe d'application** ici : [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Copier ce mot de passe dans le script Python :

   ```python
   EMAIL_EXPEDITEUR = "tonadresse@gmail.com"
   EMAIL_MDP_APP = "motdepasseapplication"
   EMAIL_DESTINATAIRE = "adresse@destinataire.com"
   ```

⚠️ **Ne jamais utiliser ton vrai mot de passe Gmail !**

---

## 🚀 Lancer l’application

```bash
python ton_script.py
```

Ou double-clique sur le fichier `.py` si Python est bien associé.

---

## 📁 Fichier généré

* `log_surveillance.txt` : toutes les actions sont enregistrées ici.

  * Exemple :

    ```
    [11:22:50] Mail envoyé pour Caméra1 (192.168.1.50)
    [11:23:08] Ping Serveur1 (172.16.100.100)...
    [11:23:09] Serveur1 (172.16.100.100) répond.
    ```

---

## 🛑 Arrêter proprement

Ferme simplement la fenêtre de l'application. Le thread de surveillance se termine automatiquement.

---
