"""
resume.py — Raccourcit un texte REX en METTANT EN AVANT LE RÔLE DE L'IA,
sans IA/API (pur découpage de phrases).

Heuristique :
  1. on garde toujours la 1re phrase (rôle Square + client + programme) ;
  2. on ajoute EN PRIORITÉ les phrases qui décrivent l'apport de l'IA
     (mots-clés : IA, algorithme, modèle, LLM, automatisation, chatbot…) ;
  3. on complète avec les phrases restantes si la place le permet.
Le rendu final respecte l'ordre d'origine des phrases pour rester lisible.
"""

from __future__ import annotations
import re

# mots-clés signalant l'apport concret de l'IA dans la mission
IA_KW = re.compile(
    r"(intelligence artificielle|\bi\.?a\.?\b|g[ée]n[ée]rative|\bllm\b|\bgpt\b|"
    r"machine learning|deep learning|\bml\b|\bnlp\b|algorithm|mod[èe]l|"
    r"chatbot|callbot|automatis|computer vision|\brag\b|data ?science|"
    r"pr[ée]dicti|embedding|palantir|scoring)",
    re.IGNORECASE,
)


def resumer(texte: str, max_car: int = 400) -> str:
    texte = re.sub(r"\s+", " ", texte or "").strip()
    if len(texte) <= max_car:
        return texte

    phrases = re.split(r"(?<=[.!?…])\s+", texte)

    def _couper(txt):
        """Coupe proprement au dernier mot sous le plafond, sans '[...]'."""
        txt = txt[:max_car].rsplit(" ", 1)[0].rstrip(" .,;:–-")
        return txt + "."

    if len(phrases) == 1:
        return _couper(phrases[0])

    ia = [i for i in range(len(phrases)) if IA_KW.search(phrases[i])]
    keep = {0}
    total = len(phrases[0])
    # ordre de priorité : d'abord les phrases 'IA', puis les autres
    reste = range(1, len(phrases))
    priorite = [i for i in reste if i in ia] + [i for i in reste if i not in ia]
    for i in priorite:
        if total + 1 + len(phrases[i]) <= max_car:
            keep.add(i)
            total += 1 + len(phrases[i])

    # GARANTIE : si des phrases parlent d'IA mais qu'aucune n'a été retenue
    # (ouverture trop longue), on tronque l'ouverture pour en faire entrer une.
    if ia and not (keep & set(ia)):
        j = min(ia, key=lambda i: len(phrases[i]))     # la plus courte phrase IA
        s0 = phrases[0]
        budget = max_car - len(phrases[j]) - 2
        if len(s0) > budget:
            s0 = s0[:budget].rsplit(" ", 1)[0].rstrip(" .,;:–-") + "."
        resume = f"{s0} {phrases[j]}"
        return resume if len(resume) <= max_car else _couper(resume)

    resume = " ".join(phrases[i] for i in sorted(keep))
    return resume if len(resume) <= max_car else _couper(resume)
