"""
generer_rex.py — Génère UN document REX à partir de l'Excel : TOUTES les
missions IA (tous secteurs), classées par type (Conformité, Front Office,
Opérations, Innovation métier, Stratégie IT, People & Change).

Format : 4 fiches/slide, texte résumé (IA mise en avant), style Square.

Lancer :  python generer_rex.py
"""
from src.extraction import charger_references
from src.matching import Categorie, lister_par_categorie
from src.generation import construire_deck, PERIM_ORDER

SORTIE = "output/REX_IA_Toutes_missions.pptx"


if __name__ == "__main__":
    refs = charger_references()

    selection = lister_par_categorie(refs, Categorie(
        theme="IA", secteur="", perimetres=PERIM_ORDER,
        exiger_theme=False, exiger_secteur=False,
    ))
    construire_deck(selection, SORTIE)
    print(f"{len(selection)} réf -> {SORTIE}")
