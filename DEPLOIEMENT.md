# Déploiement de l'agent REX

## ⚠️ Confidentialité
Les REX contiennent des **données clients sensibles** (noms, missions, montants).
**Ne pas déployer sur un service public** (Streamlit Community Cloud, dépôt GitHub
public, etc.) : les données seraient exposées. Tout déploiement doit rester
**interne à Square** et être validé par la DSI / la conformité.

## Prérequis (une fois par machine)
```
pip install -r requirements.txt
```

## Option A — Accès réseau interne (recommandé, immédiat)
Sur une machine Square (la tienne, ou un poste dédié), double-clique sur
**`lancer_app.bat`** (ou lance la commande) :
```
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Tes collègues sur le même réseau accèdent via :
```
http://<ip-de-la-machine>:8501      (ex. http://192.168.192.202:8501)
```
Trouver l'IP : `ipconfig` → « Adresse IPv4 ». La machine doit rester allumée et
l'app lancée. Le pare-feu Windows peut demander d'autoriser le port 8501.

## Option B — Serveur interne Square (pérenne)
Pour un accès permanent, faire héberger l'app par la DSI sur un serveur interne
(VM / conteneur), avec les mêmes commandes. C'est la solution durable pour un
outil partagé.

## Option C — Local uniquement (chacun sur son poste)
```
streamlit run app.py
```
L'app s'ouvre dans le navigateur (http://localhost:8501). Aucune donnée ne circule.
