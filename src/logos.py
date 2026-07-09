"""
logos.py — Résolution centralisée client -> fichier logo.

- `_MAP` : variantes de nom (sous-chaînes) -> clé de logo. Du plus spécifique
  au plus général (l'ordre compte).
- `SEARCH` : clé -> terme de recherche Wikidata (utilisé par fetch_logos.py).
- `chemin_logo(client)` : renvoie le chemin du PNG s'il existe, sinon None
  (dans ce cas la génération affiche le nom du client à la place).
"""
from __future__ import annotations
import os
import re
import unicodedata


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def _slug(client: str) -> str:
    """Nom de fichier canonique déduit du nom du client : sans accents,
    minuscule, séparateurs -> '_'. Ex. 'ABEILLE ASSURANCES' -> 'abeille_assurances'."""
    c = _sans_accents((client or "").lower().strip())
    return re.sub(r"[^a-z0-9]+", "_", c).strip("_")

LOGO_DIR = "data/logos"

_MAP = [
    (("la banque postale",),                  "la_banque_postale"),
    (("societe generale", "sg bddf"),         "societe_generale"),
    (("bnp",),                                "bnp_paribas"),
    (("credit agricole", "cal&f", "cacib", "ca cib"), "credit_agricole"),
    (("bpce",),                               "bpce"),
    (("natixis",),                            "natixis"),
    (("axa",),                                "axa"),
    (("allianz",),                            "allianz"),
    (("baloise",),                            "baloise"),
    (("groupama",),                           "groupama"),
    (("carmignac",),                          "carmignac"),
    (("amundi",),                             "amundi"),
    (("covea", "gmf"),                        "covea"),
    (("coface",),                             "coface"),
    (("l'oreal", "l’oreal", "loreal"),        "loreal"),
    (("moet hennessy",),                      "moet_hennessy"),
    (("christian dior", "dior"),              "dior"),
    (("lvmh",),                               "lvmh"),
    (("engie",),                              "engie"),
    (("fdj", "francaise des jeux"),           "fdj"),
    (("ferrero",),                            "ferrero"),
    (("la poste",),                           "la_poste"),
    (("sncf",),                               "sncf"),
    (("valeo",),                              "valeo"),
    (("tdf",),                                "tdf"),
    (("capgemini",),                          "capgemini"),
    (("arquus",),                             "arquus"),
    (("insep",),                              "insep"),
    (("scale ai",),                           "scale_ai"),
    (("chicago pneumatic",),                  "chicago_pneumatic"),
    (("bonn",),                               "bonn"),
    (("engie",),                              "engie"),
    (("fdj",),                                "fdj"),
    (("ailancy",),                             "ailancy"),
    (("bca expertise",),                       "bca_expertise"),
    (("rexel",),                               "rexel"),
    (("worldline",),                           "worldline"),
    (("abilicor",),                            "abilicor"),
    (("akto",),                                "akto"),
    (("mncap",),                               "mncap"),
    (("bloomfield",),                          "bloomfield_robotic"),
    (("gleamer",),                             "gleamer"),
    (("mediametrie",),                         "mediametrie"),
    (("virtualexpo",),                         "virtualexpo"),
    (("investance",),                          "investance_partners"),
    (("ariane group",),                        "ariane_group"),
    (("macif",),                               "macif"),
    (("prescience",),                          "prescience"),
    (("cma cgm",),                             "cma_cgm"),
    (("homeexchange",),                        "homeexchange"),
    (("idemia",),                              "idemia"),
    (("attijari",),                            "attijariwafa"),
    (("oney",),                                "oney_bank"),
    (("office national des forets",),          "onf"),
    (("generali",),                            "generali"),
    (("sofinco", "cacf"),                      "sofinco"),
    (("behit",),                               "behit"),
    (("ministere de l'economie", "ministere de l economie"), "ministere_economie"),
    (("ca indosuez",),                         "ca_indosuez"),
    (("yves rocher",),                         "yves_rocher"),
    (("avril",),                               "avril"),
]

# Terme de recherche Wikidata pour récupérer le logo (P154) de chaque marque.
SEARCH = {
    "societe_generale":  "Société Générale",
    "bnp_paribas":       "BNP Paribas",
    "credit_agricole":   "Crédit Agricole",
    "la_banque_postale": "La Banque postale",
    "natixis":           "Natixis",
    "axa":               "AXA",
    "allianz":           "Allianz",
    "baloise":           "Baloise",
    "groupama":          "Groupama",
    "carmignac":         "Carmignac",
    "amundi":            "Amundi",
    "covea":             "Covéa",
    "coface":            "Coface",
    "loreal":            "L'Oréal",
    # moet_hennessy : pas sur Wikidata/Commons -> logo fourni manuellement
    #                 par l'utilisateur dans data/logos/moet_hennessy.png (non fetché).
    "dior":              "Christian Dior (entreprise)",
    "lvmh":              "LVMH",
    "engie":             "Engie",
    "fdj":               "Française des jeux",
    "ferrero":           "Ferrero",
    "la_poste":          "La Poste (entreprise)",
    "sncf":              "SNCF Voyageurs",
    "valeo":             "Valeo",
    "tdf":               "TDF (entreprise)",
    "capgemini":         "Capgemini",
    "arquus":            "Arquus",
    "insep":             "Institut national du sport de l'expertise et de la performance",
    "scale_ai":          "Scale AI",
    "chicago_pneumatic": "Chicago Pneumatic",
    "bonn":              "université rhénane Frédéric-Guillaume de Bonn",
    "ailancy":           "Ailancy",
    "bca_expertise":     "BCA Expertise",
    "rexel":             "Rexel",
    "worldline":         "Worldline",
    "abilicor":          "Abilicor",
    "akto":              "Akto",
    "mncap":             "MNCAP",
    "bloomfield_robotic":"Bloomfield Robotics",
    "gleamer":           "Gleamer",
    "mediametrie":       "Médiamétrie",
    "virtualexpo":       "Virtual Expo Group",
    "investance_partners":"Investance",
    "ariane_group":      "ArianeGroup",
    "macif":             "Macif",
    "prescience":        "Prescience",
    "cma_cgm":           "CMA CGM",
    "homeexchange":      "HomeExchange",
    "idemia":            "Idemia",
    "attijariwafa":      "Attijariwafa Bank",
    "oney_bank":         "Oney",
    "onf":               "Office national des forêts",
    "generali":          "Generali",
    "sofinco":           "Sofinco",
    "behit":             "Behit",
    "ministere_economie":"Ministère de l'Économie et des Finances (France)",
    "ca_indosuez":       "Indosuez Wealth Management",
    "yves_rocher":       "Yves Rocher",
    "avril":             "Groupe Avril",
}
# Domaines web des marques (pour les sources de type favicon / logo par domaine).
DOMAINS = {
    "societe_generale": "societegenerale.com", "bnp_paribas": "bnpparibas.com",
    "credit_agricole": "credit-agricole.com", "la_banque_postale": "labanquepostale.fr",
    "bpce": "groupebpce.com", "natixis": "natixis.com", "axa": "axa.com",
    "allianz": "allianz.com", "baloise": "baloise.com", "groupama": "groupama.com",
    "carmignac": "carmignac.com", "coface": "coface.com", "loreal": "loreal.com",
    "moet_hennessy": "moethennessy.com", "dior": "dior.com", "lvmh": "lvmh.com",
    "engie": "engie.com", "fdj": "groupefdj.com", "ferrero": "ferrero.com",
    "la_poste": "laposte.fr", "sncf": "sncf.com", "valeo": "valeo.com",
    "tdf": "tdf.fr", "capgemini": "capgemini.com", "arquus": "arquusdefense.com",
    "insep": "insep.fr", "scale_ai": "scale.com", "chicago_pneumatic": "cp.com",
    "bonn": "uni-bonn.de",
    "ailancy": "ailancy.com", "bca_expertise": "bca-expertise.fr", "rexel": "rexel.com",
    "worldline": "worldline.com", "akto": "akto.fr", "gleamer": "gleamer.ai",
    "mediametrie": "mediametrie.fr", "virtualexpo": "virtual-expo.com",
    "investance_partners": "investance.com", "ariane_group": "ariane.group",
    "macif": "macif.fr", "cma_cgm": "cmacgm-group.com", "homeexchange": "homeexchange.com",
    "idemia": "idemia.com", "attijariwafa": "attijariwafabank.com", "oney_bank": "oney.com",
    "onf": "onf.fr", "generali": "generali.fr", "sofinco": "sofinco.fr",
    "ministere_economie": "economie.gouv.fr", "ca_indosuez": "ca-indosuez.com",
    "yves_rocher": "yves-rocher.com", "avril": "avril.com",
}
# QID Wikidata fiables (par clé) : évite de dépendre d'une recherche floue.
KNOWN_QID = {
    "societe_generale": "Q270363", "bnp_paribas": "Q499707", "credit_agricole": "Q590952",
    "la_banque_postale": "Q3206431", "natixis": "Q571156", "axa": "Q160054",
    "allianz": "Q487292", "baloise": "Q457912", "groupama": "Q3083531",
    "coface": "Q658635", "loreal": "Q156077", "lvmh": "Q504998", "engie": "Q13416787",
    "amundi": "Q2844522", "covea": "Q3001845",
    "fdj": "Q1450805", "capgemini": "Q1034621", "arquus": "Q3425100",
    "scale_ai": "Q112629176", "chicago_pneumatic": "Q4036103", "bonn": "Q152171",
    "sncf": "Q93090957", "ferrero": "Q21493848",
}
# Marques sans P154 Wikidata : fichier Commons explicite. (bpce = fourni
# manuellement par l'utilisateur, non refetché.)
COMMONS_FILE = {"dior": "Dior Logo.svg", "tdf": "TDF (Unternehmen) logo.svg",
                "la_poste": "La Poste Logo.svg", "lvmh": "LVMH logo.svg",
                "valeo": "Valeo Logo.svg", "sncf": "200914 LOGO SNCF GC RGB.png"}


# Libellés "clients" qui ne désignent aucune marque : missions anonymisées,
# regroupements ("Partenaires multiples") ou artefacts de données ("NaT").
# On ne les compte pas comme "logo manquant" (aucun logo n'est attendu).
_ANON_MARKERS = ("confidentiel", "anonym", "partenaires multiples",
                 "multiples", "divers", "plusieurs", "pluralisme")


def est_anonymise(client: str) -> bool:
    """True si le libellé n'est pas une vraie marque (mission anonymisée,
    regroupement ou cellule vide/parasite) — donc jamais de logo attendu."""
    c = _sans_accents((client or "").lower().strip())
    if c in ("", "nat", "nan", "n/a", "na", "-", "–", "—"):
        return True
    return any(m in c for m in _ANON_MARKERS)


def resoudre(client: str) -> str | None:
    """Client -> clé de logo (= nom de fichier sans extension). `_MAP` fusionne
    les variantes d'une même marque (toutes les 'BNP …' -> 'bnp_paribas') ;
    sinon on retombe sur le slug du nom. Cette clé est partagée par le
    téléchargeur (fetch_logos) ET le générateur de slides — un seul système."""
    if est_anonymise(client):
        return None
    c = _sans_accents((client or "").lower().strip())
    if c in ("sg", "sg bddf"):
        return "societe_generale"
    for subs, key in _MAP:
        if any(s in c for s in subs):
            return key
    return _slug(client)                      # fallback : slug du nom complet


def _index_fichiers() -> dict[str, str]:
    """Index {nom_fichier_minuscule: nom_fichier_reel} de LOGO_DIR.

    Nécessaire car `resoudre()` produit toujours une clé en minuscule, mais
    Windows (insensible à la casse) laisse passer un fichier réel mal nommé
    (ex. 'Abilicor.png') alors que Streamlit Cloud tourne sur Linux
    (sensible à la casse) et ne le trouverait pas. On matche donc ici
    manuellement en minuscule plutôt que de compter sur l'OS."""
    try:
        return {f.lower(): f for f in os.listdir(LOGO_DIR)}
    except FileNotFoundError:
        return {}


def chemin_logo(client: str) -> str | None:
    key = resoudre(client)
    if not key:
        return None
    nom_reel = _index_fichiers().get(key.lower() + ".png")
    return os.path.join(LOGO_DIR, nom_reel) if nom_reel else None
