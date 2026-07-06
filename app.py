"""
app.py — Interface Streamlit du générateur de REX Square Management.

Lancer :  streamlit run app.py

Permet de : choisir le périmètre (banques CIB/corporate ou tous secteurs) et
les types de mission, prévisualiser les références sélectionnées, puis générer
et télécharger le PowerPoint au style Square.
"""
import os
import tempfile
import pandas as pd
import streamlit as st

from fetch_logos import telecharger_logos_manquants
from src.extraction import charger_references, SECTEURS, TYPES_PRESTATION
from src.matching import Categorie, lister_par_categorie, PALIERS_IA
from src.generation import construire_deck, PERIM_ORDER

OR = "#BD8E42"
EXCEL_DEFAUT = "data/references.xlsx"

st.set_page_config(page_title="REX IA — Square Management", page_icon="📑", layout="wide")

st.markdown(
    f"<h1 style='margin-bottom:0'>Générateur de REX "
    f"<span style='color:{OR}'>·</span> Square Management</h1>"
    "<p style='color:#807F7E;margin-top:4px'>Sélectionne les références IA les plus "
    "pertinentes et génère un PowerPoint prêt à présenter.</p>",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _charger(chemin: str, _sig: float):
    return charger_references(chemin)


def _cases(titre: str, options, prefix: str, defaut: bool = True):
    """Groupe de cases à cocher ; renvoie la liste des options cochées."""
    with st.expander(titre, expanded=True):
        return [o for o in options if st.checkbox(str(o), value=defaut, key=f"{prefix}_{o}")]


# ── Barre latérale 1 : source (avant chargement) ──
with st.sidebar:
    st.header("1 · Source de données")
    fichier = st.file_uploader("Fichier Excel de références (.xlsx)", type=["xlsx"])
    if fichier:
        chemin = os.path.join(tempfile.gettempdir(), fichier.name)
        with open(chemin, "wb") as f:
            f.write(fichier.getbuffer())
    else:
        chemin = EXCEL_DEFAUT
        st.caption(f"Par défaut : `{EXCEL_DEFAUT}`")

st.markdown("---")
st.subheader("🖼️ Gestion des logos")
if st.button("Chercher les logos manquants", use_container_width=True): 
    status_text = st.empty()
    progress_bar = st.progress(0)
    try:
        # On passe les éléments visuels à la fonction pour qu'elle les anime
        nb = telecharger_logos_manquants(chemin, progress_bar, status_text)
            
        # Une fois terminé, on efface le texte de chargement et on remplit la barre
        status_text.empty()
        progress_bar.empty()
            
        if nb > 0:
            st.success(f"✅ {nb} nouveau(x) logo(s) téléchargé(s) !")
        else:
            st.info("👍 Tous les logos sont déjà à jour.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération : {e}")


# ── Chargement des références ──
if not os.path.exists(chemin):
    st.error(f"Fichier introuvable : {chemin}")
    st.stop()
try:
    refs = _charger(chemin, os.path.getmtime(chemin))
except Exception as e:
    st.error(f"Lecture de l'Excel impossible : {e}")
    st.stop()

# ── Barre latérale 2 : filtres (après chargement) ──
with st.sidebar:
    st.header("2 · Périmètre")
    scope = st.radio(
        "Secteur",
        ["Toutes les missions (tous secteurs)",
         "Toutes les banques",
         "Banques d'entreprise (CIB / corporate)",
         "Secteurs au choix…"],
    )
    secteurs_choisis = []
    if scope.startswith("Secteurs au choix"):
        secteurs_choisis = st.multiselect("Secteurs précis", SECTEURS, default=SECTEURS)

    types = _cases("Périmètre (domaine)", PERIM_ORDER, "perim")
    types_prest = _cases("Type de prestation", TYPES_PRESTATION, "type")
    genai_only = st.toggle("Uniquement IA générative")

    # pertinence IA (si le fichier contient la colonne Indice IA)
    paliers_dispo = [p for p in PALIERS_IA if any(r.pertinence_ia == p for r in refs)]
    sans_palier = any(not r.pertinence_ia for r in refs)
    paliers_choisis, inclure_inconnue = paliers_dispo, True
    if paliers_dispo:
        st.header("3 · Pertinence IA")
        with st.expander("Niveaux retenus", expanded=True):
            paliers_choisis = [p for p in paliers_dispo
                               if st.checkbox(p, value=True, key=f"pal_{p}")]
            if sans_palier:
                inclure_inconnue = st.checkbox("Non renseigné (on ne sait pas)",
                                               value=True, key="pal_inconnu")

# ── Filtrage ──
secteur = {
    "Banques d'entreprise (CIB / corporate)": "banque d'entreprise",
    "Toutes les banques": "banque",
}.get(scope, "")                            # sinon : tous secteurs / au choix
tp = types_prest if 0 < len(types_prest) < len(TYPES_PRESTATION) else []
cat = Categorie(
    theme="IA", secteur=secteur, secteurs=secteurs_choisis, perimetres=types,
    types_prestation=tp, genai_only=genai_only, paliers_ia=paliers_choisis,
    inclure_pertinence_inconnue=inclure_inconnue,
    exiger_theme=False, exiger_secteur=bool(secteur),
)
selection = lister_par_categorie(refs, cat)
if not selection:
    st.warning("Aucune référence pour ces critères. Élargis les filtres.")
    st.stop()

# ── Tableau + DÉSÉLECTION (décoche pour exclure) ──
a_pertinence = any(r.pertinence_ia for r in selection)
st.subheader(f"Références retenues — {len(selection)}  ·  décoche une ligne pour l'exclure")
lignes = []
for r in selection:
    ligne = {"Inclure": True, "Client": r.client, "Secteur": r.secteur,
             "Périmètre": r.perimetre or "—", "Prestation": r.type_mission or "—"}
    if a_pertinence:
        ligne["Pertinence IA"] = r.pertinence_ia or "—"
        ligne["Score"] = r.score_ia
    ligne["GenAI"] = "✓" if r.genai else ""
    ligne["Année"] = r.annee
    lignes.append(ligne)

edited = st.data_editor(
    pd.DataFrame(lignes), hide_index=True, width="stretch", key="editeur",
    disabled=[c for c in lignes[0] if c != "Inclure"],
    column_config={"Inclure": st.column_config.CheckboxColumn("Inclure", default=True)},
)
selection_finale = [r for r, inc in zip(selection, edited["Inclure"]) if inc]

c1, c2, c3 = st.columns(3)
c1.metric("Incluses dans le deck", len(selection_finale))
c2.metric("Secteurs", len({r.secteur for r in selection_finale}))
c3.metric("IA générative", sum(1 for r in selection_finale if r.genai))

# ── Génération ──
st.subheader("Génération")
if st.button("🎬 Générer le PowerPoint", type="primary"):
    if not selection_finale:
        st.error("Aucune référence cochée.")
    else:
        with st.spinner("Construction du deck au style Square…"):
            sortie = os.path.join(tempfile.gettempdir(), "REX_IA_Square.pptx")
            construire_deck(selection_finale, sortie)
            with open(sortie, "rb") as f:
                st.session_state["pptx"] = f.read()
        st.success(f"Deck généré ✅ ({len(selection_finale)} références)")

if "pptx" in st.session_state:
    st.download_button(
        "⬇️ Télécharger le .pptx",
        st.session_state["pptx"],
        file_name="REX_IA_Square.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
