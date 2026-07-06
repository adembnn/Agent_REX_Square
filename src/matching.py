"""
matching.py — Filtrage des références par catégorie.

L'agent ne "note" pas : il FILTRE les références selon des facettes (thème,
secteur, périmètre, type de prestation, IA générative), puis les renvoie
triées par année décroissante (les plus récentes d'abord). Indépendant du
format Excel : il travaille sur des objets Reference normalisés.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
import unicodedata


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------
@dataclass
class Reference:
    """Une référence client normalisée (une ligne de l'Excel)."""
    client: str
    secteur: str = ""
    domaines: list[str] = field(default_factory=list)   # ex. ["conformité", "risques"]
    type_mission: str = ""                               # ex. "pilotage"
    annee: int | None = None                             # année de début
    annee_fin: int | None = None                         # année de fin (colonne 'end')
    resultats: str = ""                                  # texte des résultats chiffrés ("" si aucun)
    description: str = ""                                 # libellé complet de la mission
    perimetre: str = ""                                  # ex. "Front Office", "Conformité", "Opérations"
    titre: str = ""                                      # 'DIRECTION – RÔLE' (fiches références)
    nom: str = ""                                        # nom court de la mission (colonne 'name', timeline)
    genai: bool = False                                  # la mission relève-t-elle de l'IA générative ?
    pertinence_ia: str = ""                              # Indice IA (palier) : Marginal/Contributif/Central/Cœur technique
    score_ia: int | None = None                          # Score /9 de pertinence IA


@dataclass
class Categorie:
    """Filtre à facettes : on ne garde que les références qui y appartiennent."""
    theme: str = ""                                      # ex. "IA"
    secteur: str = ""                                    # match flou : "banque d'entreprise", "banque"…
    perimetres: list[str] = field(default_factory=list)  # ex. ["Front Office", "Conformité"] (logique OU)
    exiger_theme: bool = True                            # le thème est-il obligatoire ?
    exiger_secteur: bool = True                          # le secteur est-il obligatoire ?
    secteurs: list[str] = field(default_factory=list)    # secteurs précis (match exact, logique OU)
    types_prestation: list[str] = field(default_factory=list)  # ex. ["Pilotage", "Data Science"]
    genai_only: bool = False                             # ne garder que les missions IA générative
    paliers_ia: list[str] = field(default_factory=list)  # paliers de pertinence IA retenus (match exact)
    inclure_pertinence_inconnue: bool = True             # garder les réfs sans palier renseigné


# Paliers de pertinence IA, du plus faible au plus fort.
PALIERS_IA = ["Marginal", "Contributif", "Central", "Cœur technique"]


# ---------------------------------------------------------------------------
# 3. Utilitaires de normalisation texte (accents, casse)
# ---------------------------------------------------------------------------
def _norm(texte: str) -> str:
    """minuscule + sans accents, pour comparer 'Conformité' == 'conformite'."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte.lower().strip()


def _tokens(texte: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _norm(texte)))


# ---------------------------------------------------------------------------
# Filtrage par catégorie
# ---------------------------------------------------------------------------
def _dedup(refs: list[Reference]) -> list[Reference]:
    """Évite les quasi-doublons (même client + même description)."""
    vus: set[tuple[str, str]] = set()
    garde = []
    for ref in refs:
        cle = (_norm(ref.client), _norm(ref.description))
        if cle in vus:
            continue
        vus.add(cle)
        garde.append(ref)
    return garde
def _texte_ref(ref: Reference) -> set[str]:
    """Tous les tokens exploitables d'une référence pour la recherche."""
    return _tokens(" ".join(ref.domaines) + " " + ref.description
                   + " " + ref.perimetre + " " + ref.type_mission)


def _match_mots(expression: str, cible: set[str]) -> bool:
    """L'expression (ex. 'Front Office') est trouvée si TOUS ses mots
    significatifs sont présents dans la cible."""
    mots = _tokens(expression)
    return bool(mots) and mots <= cible


# Mots trop génériques pour distinguer un secteur (banque d'entreprise vs de détail).
_SECTEUR_STOP = {"banque", "de", "du", "des", "la", "le", "les", "d", "et", "l", "en"}


def _secteur_appartient(secteur_cat: str, secteur_ref: str) -> bool:
    """Correspondance secteur qui ignore les mots génériques : les mots
    DISTINCTIFS de la catégorie doivent être présents dans le secteur de la réf.
    'banque d'entreprise' -> mot distinctif {entreprise} ; ne matche pas
    'banque de détail'. Si aucun mot distinctif, on retombe sur un chevauchement.
    """
    cible = _tokens(secteur_ref)
    distinctifs = _tokens(secteur_cat) - _SECTEUR_STOP
    if distinctifs:
        return distinctifs <= cible
    return bool(_tokens(secteur_cat) & cible)


def _appartient(ref: Reference, cat: Categorie) -> bool:
    """La référence appartient-elle à la catégorie (filtre dur) ?"""
    texte = _texte_ref(ref)

    if cat.exiger_theme and cat.theme and not _match_mots(cat.theme, texte):
        return False

    if cat.genai_only and not ref.genai:
        return False

    # pertinence IA (palier). Les réfs sans palier ("on ne sait pas") sont
    # gérées à part via inclure_pertinence_inconnue.
    if ref.pertinence_ia:
        if cat.paliers_ia and ref.pertinence_ia not in cat.paliers_ia:
            return False
    elif not cat.inclure_pertinence_inconnue:
        return False

    # type de prestation : on ne filtre que les réfs qui ONT un type (sinon on
    # exclurait tout un fichier dont les clusters AXE 1 sont cassés / vides)
    if cat.types_prestation and ref.type_mission and ref.type_mission not in cat.types_prestation:
        return False

    if cat.secteurs:
        # secteurs précis : match exact (logique OU)
        if ref.secteur not in cat.secteurs:
            return False
    elif cat.exiger_secteur and cat.secteur:
        # sinon : match flou sur un libellé de secteur ("banque", "banque d'entreprise"…)
        if not _secteur_appartient(cat.secteur, ref.secteur):
            return False

    if cat.perimetres and ref.perimetre:
        # logique OU : le PÉRIMÈTRE STRUCTURÉ de la réf (issu du cluster AXE 2)
        # doit correspondre à l'un des périmètres demandés. On ne filtre que les
        # réfs qui ONT un périmètre (sinon un fichier aux clusters cassés = vide).
        cible_perim = _tokens(ref.perimetre)
        if not any(_match_mots(p, cible_perim) for p in cat.perimetres):
            return False

    return True


def lister_par_categorie(
    references: list[Reference],
    cat: Categorie,
    anti_doublon: bool = True,
) -> list[Reference]:
    """Renvoie TOUTES les références de la catégorie (liste exhaustive),
    triées par année décroissante (les plus récentes d'abord)."""
    survivants = [r for r in references if _appartient(r, cat)]
    survivants.sort(key=lambda r: (r.annee or 0, r.client.lower()), reverse=False)
    survivants.sort(key=lambda r: (r.annee or 0), reverse=True)
    if anti_doublon:
        survivants = _dedup(survivants)
    return survivants
