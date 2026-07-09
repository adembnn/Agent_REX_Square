"""
extraction.py — Transforme le fichier Excel réel (REX IA SQM) en objets
Reference exploitables par le moteur de matching.

Le fichier n'a pas de colonnes "secteur" / "périmètre" explicites : on les
DÉDUIT des deux axes de clusters et du nom du client.
  - AXE 2 (domaine)  -> périmètre  (Cluster A/B/C = Front Office / Conformité / Opérations ...)
  - AXE 1 (type)     -> type de mission
  - client           -> secteur (banque ou non) via un classifieur de noms
  - Reformulation REX-> texte affiché
"""

from __future__ import annotations
import re
import pandas as pd

from src.matching import Reference

import unicodedata


def _feuille_principale(chemin: str) -> str:
    """Détecte automatiquement la feuille de données (celle qui contient les
    colonnes attendues), pour ne plus dépendre d'un nom de feuille figé."""
    xl = pd.ExcelFile(chemin)
    for sh in xl.sheet_names:
        cols = {str(c).strip().lower()
                for c in pd.read_excel(chemin, sheet_name=sh, nrows=0).columns}
        if "client" in cols and "reformulation rex" in cols:
            return sh
    return xl.sheet_names[0]


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


# --- Périmètre & type de prestation : DÉDUITS PAR MOTS-CLÉS ------------------
# On IGNORE les colonnes AXE 1 / AXE 2 (formules cassées / inutiles). Le
# périmètre est déduit du texte des colonnes direction/community/name/description,
# le type de prestation du rôle + texte.
_PERIM_KW = {
    "Conformité":        [r"conformit", r"compliance", r"reglementaire", r"risque", r"lcb",
                          r"kyc", r"blanchiment", r"juridique", r"bale", r"regulatory",
                          r"controle", r"securite financiere", r"fraude", r"sanction", r"audit"],
    "Front Office":      [r"relation client", r"marketing", r"vente", r"\bcrm\b", r"front office",
                          r"commercial", r"chatbot", r"callbot", r"paiement", r"payment",
                          r"\bcard", r"distribution", r"recommandation", r"sobot", r"assistant"],
    "Opérations":        [r"operation", r"back office", r"back-office", r"middle office",
                          r"processus", r"efficacite", r"organisation", r"\brpa\b", r"automatis",
                          r"facturation", r"supply", r"indemnisation", r"back/middle"],
    "Innovation métier": [r"innovation", r"r&d", r"\br&i\b", r"recherche", r"coeur de metier",
                          r"cosmetique", r"vision", r"industrie", r"augmented", r"viticult", r"agricult"],
    "People & Change":   [r"people", r"conduite du changement", r"\bchange\b", r"\brh\b", r"formation",
                          r"acculturation", r"competence", r"sustainability", r"transformation", r"hackathon"],
    "Stratégie IT":      [r"\bdsi\b", r"architecture", r"\bdata\b", r"\bmdm\b", r"master data",
                          r"systeme d", r"\bit\b", r"infrastructure", r"plateforme", r"data warehouse",
                          r"donnee", r"\bllm", r"\bnlp\b", r"modele"],
}
# ordre = priorité en cas d'égalité ; défaut = "Stratégie IT"
_PERIM_ORDRE = ["Conformité", "Front Office", "Opérations",
                "Innovation métier", "People & Change", "Stratégie IT"]

_TYPE_KW = {
    "Pilotage":                  [r"chef de projet", r"\bpmo\b", r"product owner", r"\bpo\b",
                                  r"pilotage", r"coordination", r"gestion de projet", r"deploiement", r"suivi"],
    "Stratégie & Cadrage":       [r"strateg", r"cadrage", r"advisor", r"conseil", r"diagnostic",
                                  r"\btom\b", r"gouvernance", r"roadmap", r"feuille de route", r"target operating"],
    "Data Science":              [r"data scientist", r"modele", r"machine learning", r"algorithm",
                                  r"\bllm\b", r"\bnlp\b", r"developpement", r"fine-tuning", r"\brag\b",
                                  r"computer vision", r"backtest"],
    "Conduite du changement":    [r"conduite du changement", r"\bchange\b", r"formation",
                                  r"acculturation", r"accompagnement", r"adoption"],
    "Éthique & Conformité data": [r"ethique", r"data steward", r"qualite des donnees",
                                  r"explicabilite", r"\brgpd\b", r"biais"],
}
_TYPE_ORDRE = list(_TYPE_KW)
# Ordre canonique des types de prestation (pour l'interface).
TYPES_PRESTATION = list(_TYPE_KW.keys())


def _classer_motscles(txt: str, table: dict, ordre: list, defaut: str) -> str:
    txt = _norm(txt)
    best, best_n = defaut, 0
    for cle in ordre:
        n = sum(len(re.findall(kw, txt)) for kw in table[cle])
        if n > best_n:
            best, best_n = cle, n
    return best


def _perimetre(row) -> str:
    txt = " ".join(str(row.get(c, "")) for c in
                   ("direction", "community", "name", "description", "context"))
    return _classer_motscles(txt, _PERIM_KW, _PERIM_ORDRE, "Stratégie IT")


def _type_prestation(row) -> str:
    txt = " ".join(str(row.get(c, "")) for c in ("role", "name", "description"))
    return _classer_motscles(txt, _TYPE_KW, _TYPE_ORDRE, "Pilotage")


# Détection "IA générative" (GenAI) dans le texte de la mission.
_GENAI_KW = re.compile(r"g[ée]n[ée]rativ|genai|\bgpt\b|\bllm\b|\biagen\b", re.IGNORECASE)


# --- Classifieur secteur (tous secteurs) -------------------------------------
# Banques : "Banque d'entreprise (CIB)" = CIB + financement spécialisé
# (leasing/factoring) ; sinon "Banque de détail". Hors banques : mapping par
# nom de client. L'ordre du mapping compte (du plus spécifique au plus général).
_MOTS_BANQUE = [
    "societe generale", "sg bddf", "bnp", "bnpp", "bpce", "credit agricole",
    "cal&f", "la banque postale", "natixis",
]
_CIB_KW = [
    "cib", "global banking", "global markets", "banque de financement",
    "leasing", "factoring", "cal&f", "affacturage",
]
# Secteurs hors-banque (vérifiés AVANT la détection banque pour gérer les
# filiales : "natixis im" = gestion d'actifs et non banque, etc.).
_SECTEURS_MAP = [
    (("carmignac", "natixis im", "groupama am", "amundi"),          "Gestion d'actifs"),
    (("axa", "allianz", "baloise", "groupama", "mncap", "coface"),  "Assurance"),
    (("lvmh", "moet", "hennessy", "dior", "oreal", "luxe"),         "Luxe & Cosmétique"),
    (("engie",),                                                    "Énergie"),
    (("valeo", "arquus", "chicago pneumatic", "bloomfield", "ferrero"), "Industrie"),
    (("sncf", "la poste", "insep", "bonn", "akto", "fdj"),          "Transport & Public"),
    (("scale ai", "gleamer", "abilicor", "ailancy", "capgemini", "bca", "tdf"),
                                                                    "Tech & Conseil"),
]

# Ordre canonique des secteurs (pour l'interface).
SECTEURS = [
    "Banque d'entreprise (CIB)", "Banque de détail", "Gestion d'actifs",
    "Assurance", "Luxe & Cosmétique", "Industrie", "Énergie",
    "Transport & Public", "Tech & Conseil", "Autre",
]


def _secteur_du_client(client: str, direction: str = "") -> str:
    c = (client or "").lower()
    for cles, sec in _SECTEURS_MAP:           # hors-banque d'abord (filiales)
        if any(x in c for x in cles):
            return sec
    if any(x in c for x in _MOTS_BANQUE):      # banques
        txt = f"{c} {(direction or '').lower()}"
        return "Banque d'entreprise (CIB)" if any(k in txt for k in _CIB_KW) else "Banque de détail"
    return "Autre"


# --- Utilitaires -------------------------------------------------------------
_PLACEHOLDERS = {"", "nan", "-", "–", "—", "n/a", "na", "."}


def _propre(v) -> str:
    v = str(v or "").strip()
    return "" if v.lower() in _PLACEHOLDERS else v


def _titre_carte(row) -> str:
    """Reconstitue le titre de fiche façon template : 'DIRECTION – RÔLE'.
    Ignore les valeurs vides/placeholder ('-', 'nan'…)."""
    parts = [p for p in (_propre(row.get("direction")), _propre(row.get("role"))) if p]
    return " – ".join(parts)


# Textes REX cassés (l'outil de reformulation de l'Excel a parfois échoué)
_REX_CASSE = ("un problème est survenu", "réessayez", "une erreur", "try again")


def _texte_reference(row) -> str:
    """Texte de la fiche = 'Reformulation REX' si valide, sinon repli sur les
    colonnes brutes (description / contexte / name)."""
    rex = str(row.get("Reformulation REX") or "").strip()
    if len(rex) >= 40 and not any(m in rex.lower() for m in _REX_CASSE):
        return rex
    for col in ("description", "context", "name"):
        v = str(row.get(col) or "").strip()
        if len(v) >= 40:
            return v
    return rex or str(row.get("name", "")).strip()


def _annee(valeur) -> int | None:
    try:
        return pd.to_datetime(valeur).year
    except Exception:
        return None


def _score_ia(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def charger_references(chemin: str = "data/references.xlsx") -> list[Reference]:
    df = pd.read_excel(chemin, sheet_name=_feuille_principale(chemin), header=0)
    refs: list[Reference] = []

    for _, row in df.iterrows():
        client = str(row.get("client", "")).strip()
        # "nan"/"nat" = cellule vide lue par pandas (ligne blanche/parasite) -> ignorée.
        if not client or client.lower() in ("nan", "nat", "interne", "square management"):
            continue

        # périmètre & type DÉDUITS par mots-clés (on n'utilise plus AXE 1/2)
        perimetre = _perimetre(row)
        type_mission = _type_prestation(row)

        texte = _texte_reference(row)
        titre = _titre_carte(row)
        refs.append(Reference(
            client=client,
            secteur=_secteur_du_client(client, str(row.get("direction", ""))),
            domaines=["ia", perimetre] if perimetre else ["ia"],
            type_mission=type_mission,
            annee=_annee(row.get("start")),
            annee_fin=_annee(row.get("end")),
            resultats="",                       # pas de colonne résultats chiffrés dédiée
            description=texte,
            perimetre=perimetre,
            titre=titre,
            nom=_propre(row.get("name")),
            genai=bool(_GENAI_KW.search(f"{texte} {titre}")),
            pertinence_ia=_propre(row.get("Indice IA (palier)")),
            score_ia=_score_ia(row.get("Score /9")),
        ))
    return refs


if __name__ == "__main__":
    refs = charger_references()
    print(f"{len(refs)} références chargées.")
    from collections import Counter
    print("Secteurs :", dict(Counter(r.secteur for r in refs)))
    print("GenAI    :", sum(r.genai for r in refs), "missions IA générative")
