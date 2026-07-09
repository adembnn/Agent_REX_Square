"""
fetch_logos.py — Récupère le MEILLEUR logo de chaque marque en comparant
plusieurs sources, puis l'enregistre (recadré) dans data/logos/.

L'agent télécharge les candidats, les NOTE (résolution, transparence, pas un
favicon minuscule, ratio raisonnable) et conserve le mieux noté.

Lancer :  python fetch_logos.py         (saute les logos déjà présents)
          python fetch_logos.py force   (re-télécharge tout)
"""
import urllib.parse, urllib.request, json, os, re, sys, time
from src.extraction import charger_references
from io import BytesIO
from PIL import Image, ImageChops

from src.logos import (SEARCH, KNOWN_QID, COMMONS_FILE, DOMAINS, LOGO_DIR,
                       resoudre, est_anonymise, chemin_logo)

UA = {"User-Agent": "SquareREXAgent/1.0 (stage; contact intern)"}
FORCE = "force" in sys.argv


def _get(url: str, retries: int = 3):
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                time.sleep(2 * (i + 1)); continue
            return None
        except Exception:
            return None


def _json(url: str):
    data = _get(url)
    return json.loads(data) if data else {}


# ── Helpers Wikidata ────────────────────────────────────────────────────────
def qid(name):
    d = _json("https://www.wikidata.org/w/api.php?action=wbsearchentities"
              f"&search={urllib.parse.quote(name)}&language=fr&format=json&limit=1")
    return d["search"][0]["id"] if d.get("search") else None


def logo_file(q):
    claims = _json("https://www.wikidata.org/w/api.php?action=wbgetclaims"
                   f"&entity={q}&property=P154&format=json").get("claims", {}).get("P154")
    return claims[0]["mainsnak"]["datavalue"]["value"] if claims else None


def thumb_png(filename, width=512):
    d = _json("https://commons.wikimedia.org/w/api.php?action=query"
              f"&titles=File:{urllib.parse.quote(filename)}"
              f"&prop=imageinfo&iiprop=url&iiurlwidth={width}&format=json")
    pages = d.get("query", {}).get("pages", {})
    ii = list(pages.values())[0].get("imageinfo") if pages else None
    return (ii[0].get("thumburl") or ii[0].get("url")) if ii else None


def _domaines(name, key=None):
    """Domaines web candidats de la marque, TOUS découverts automatiquement :
    override manuel (DOMAINS) -> site officiel déclaré sur Wikidata (P856) ->
    devinette `marque.fr`/`.com`/`.eu` à partir du nom. Aucune saisie au cas
    par cas : c'est le générateur de slides qui décide via la notation."""
    if key and DOMAINS.get(key):
        return [DOMAINS[key]]
    q = (KNOWN_QID.get(key) if key else None) or qid(name)
    if q:
        claims = _json("https://www.wikidata.org/w/api.php?action=wbgetclaims"
                       f"&entity={q}&property=P856&format=json").get("claims", {}).get("P856")
        if claims:
            try:
                host = urllib.parse.urlparse(claims[0]["mainsnak"]["datavalue"]["value"]).netloc.lower()
                return [host[4:] if host.startswith("www.") else host]
            except Exception:
                pass
    # Aucun site officiel connu -> devinette sur le mot de marque le plus long.
    mots = sorted(_toks(name) - _STOP, key=len, reverse=True)
    return [f"{mots[0]}.fr", f"{mots[0]}.com", f"{mots[0]}.eu"] if mots else []


# ── Normalisation pour le matching de pertinence (seeklogo) ─────────────────
def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _toks(t, minlen=3):
    return {w for w in re.findall(r"[a-z0-9]+", _norm(t)) if len(w) >= minlen}


# Mots trop génériques pour identifier une marque (évite les faux positifs).
_STOP = {"groupe", "group", "france", "assurance", "assurances", "banque",
         "bank", "holding", "compagnie", "societe", "international", "the",
         "sa", "sas", "gie"}


# ── Sources de logos (les meilleures : logos officiels, pas des favicons) ────
def src_wikidata(key, name, domaines):
    """Logo officiel de la fiche Wikidata (P154) — vectoriel/transparent, HD."""
    q = KNOWN_QID.get(key) or qid(name)
    fn = logo_file(q) if q else None
    return _get(thumb_png(fn)) if fn else None


def _icones_du_site(domain):
    """URLs de logo déclarées sur la page d'accueil : apple-touch-icon (souvent
    le logo de marque transparent) puis og:image, en absolu."""
    for base in (f"https://www.{domain}", f"https://{domain}"):
        html = _get(base)
        if not html:
            continue
        html = html.decode("utf-8", "ignore")
        urls = []
        for balise in re.findall(r"<link[^>]+apple-touch-icon[^>]*>", html, re.I):
            h = re.search(r'href=["\']([^"\']+)', balise)
            if h:
                urls.append(h.group(1))
        for balise in re.findall(r'<meta[^>]+og:image[^>]*>', html, re.I):
            h = re.search(r'content=["\']([^"\']+)', balise)
            if h:
                urls.append(h.group(1))
        return [urllib.parse.urljoin(base + "/", u) for u in urls]
    return []


def src_site(key, name, domaines):
    """Meilleure icône déclarée par le site officiel (PNG transparent 180-300px).
    Les domaines candidats sont fournis automatiquement par `_domaines`."""
    best, best_sc = None, 0.0
    for domain in (domaines or [])[:3]:
        for u in _icones_du_site(domain)[:6]:
            data = _get(u)
            if not data:
                continue
            sc, _ = _qualite(data)
            if sc > best_sc:
                best, best_sc = data, sc
        if best is not None:                       # 1er domaine qui répond suffit
            break
    return best


def src_seeklogo(key, name, domaines):
    """seeklogo.com : bibliothèque de logos d'entreprise (PNG transparents).
    Pas d'API -> on lit la page de recherche et on FILTRE par pertinence sur le
    nom de marque (sinon on récupère un homonyme / une déclinaison régionale)."""
    html = _get("https://seeklogo.com/search?q=" + urllib.parse.quote(name))
    if not html:
        return None
    html = html.decode("utf-8", "ignore")
    qd = _toks(name) - _STOP                       # tokens distinctifs (>= 3 lettres)
    qfull = _toks(name, 2)                          # tous les tokens (pour départager)
    if not qd:
        return None
    best, seen = None, set()
    for u in re.findall(r'https://images\.seeklogo\.com/logo-png/[^\s"\'<>]+\.png', html):
        if u in seen:
            continue
        seen.add(u)
        m = re.search(r'/([a-z0-9\-]+)-logo-png_seeklogo', u)
        stoks = _toks(m.group(1), 2) if m else set()
        rel = len(qd & stoks)                      # nb de tokens de marque retrouvés
        if rel == 0:                               # pas le bon logo -> on écarte
            continue
        data = _get(u)
        if not data:
            continue
        sc, im = _qualite(data)
        if im is None:
            continue
        foreign = len(stoks - qfull)               # mots parasites (ex. axa-'sigorta')
        rank = (rel, -foreign, sc)                 # + pertinent, - parasites, + net
        if best is None or rank > best[0]:
            best = (rank, data)
    return best[1] if best else None


# Sources par ORDRE DE FIABILITÉ (autorité de la marque) :
#   1. Wikidata P154  : logo officiel vectoriel/transparent
#   2. Site officiel  : apple-touch-icon = logo courant, garanti = la bonne société
#   3. seeklogo       : grande bibliothèque, mais AMBIGUË sur les noms courts
#                       (homonymes, versions périmées) -> uniquement en dernier recours
# On prend la 1re source qui renvoie un logo « assez bon » (cf. SEUIL_OK).
SOURCES = [("wikidata", src_wikidata), ("site", src_site), ("seeklogo", src_seeklogo)]
SEUIL_OK = 60_000        # score mini pour valider une source sans essayer les suivantes


# ── Notation qualité d'un candidat ──────────────────────────────────────────
def _qualite(data):
    try:
        im = Image.open(BytesIO(data)); im.load()
    except Exception:
        return -1.0, None
    w, h = im.size
    if w < 16 or h < 16:
        return -1.0, None
    if im.mode == "CMYK":
        im = im.convert("RGB")
    area = float(w * h)
    transparent = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 255
    if transparent:
        score = area * 3.0                        # vrai logo (fond transparent) : priorité
    elif area > 250_000:
        score = area * 0.02                       # gros opaque = probablement une photo
    else:
        score = area
    if max(w, h) < 80:                            # favicon minuscule
        score *= 0.04
    if max(w, h) / min(w, h) > 12:               # ratio extrême
        score *= 0.3
    return score, im


def _recadrer(im):
    if im.mode == "P":
        im = im.convert("RGBA")
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] < 255:
        bbox = im.getbbox()
    else:
        rgb = im.convert("RGB")
        bbox = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).getbbox()
    if bbox:
        p = 8
        l, t, r, b = bbox
        im = im.crop((max(0, l - p), max(0, t - p), min(im.width, r + p), min(im.height, b + p)))
    return im


def meilleur_logo(key, name, existant=None):
    """Parcourt les sources par ordre de fiabilité et renvoie le logo de la 1re
    source qui dépasse SEUIL_OK ; sinon la meilleure image trouvée ; sinon le
    logo actuel. Domaines (pour `site`) découverts automatiquement via Wikidata."""
    domaines = _domaines(name, key)
    fallback = (0.0, None, None)      # meilleure image si aucune source n'atteint le seuil
    detail = []
    for nom, fn in SOURCES:
        try:
            data = fn(key, name, domaines)
        except Exception:
            data = None
        if not data:
            detail.append(f"{nom}=∅"); continue
        sc, im = _qualite(data)
        detail.append(f"{nom}={int(sc) if sc > 0 else '✗'}")
        if im is not None and sc > fallback[0]:
            fallback = (sc, im, nom)
        if im is not None and sc >= SEUIL_OK:        # source fiable suffisante -> stop
            return im, nom, detail
        time.sleep(0.3)
    if fallback[1] is None and existant:             # aucune source -> garder l'actuel
        sc, im = _qualite(existant)
        if sc > 0:
            return im, "actuel", detail
    return fallback[1], fallback[2], detail


def telecharger_logos_manquants(chemin_excel, progress_bar=None, status_text=None):
    """Télécharge UNIQUEMENT les logos qui manquent sur les slides.

    On cible exactement les clients affichés dans « sans logo sur les slides »
    (vraie marque + aucun fichier logo), et on enregistre chaque logo sous la
    clé canonique `resoudre(client)` — la même que lit le générateur de slides.
    En mode `force`, on re-télécharge aussi les logos déjà présents.
    """
    os.makedirs(LOGO_DIR, exist_ok=True)

    # 1. Lecture dynamique du fichier Excel
    try:
        references = charger_references(chemin_excel)
    except Exception as e:
        raise Exception(f"Impossible de lire l'Excel pour les logos : {e}")

    # 2. Cibler les clients concernés (on ignore les libellés anonymisés).
    cibles = sorted({ref.client for ref in references
                     if ref.client and not est_anonymise(ref.client)})
    if not FORCE:                                    # par défaut : les manquants seuls
        cibles = [c for c in cibles if chemin_logo(c) is None]

    nb_telecharges = 0
    total = len(cibles)

    # 3. Boucle sur les seuls clients à traiter
    for index, name in enumerate(cibles):
        if status_text:
            status_text.text(f"Recherche du logo pour : {name} ({index + 1}/{total})")
        if progress_bar:
            progress_bar.progress((index + 1) / total if total else 1.0)

        key = resoudre(name)                         # clé partagée avec les slides
        if not key:
            continue
        dest = os.path.join(LOGO_DIR, key + ".png")

        existant = None
        if os.path.exists(dest):
            with open(dest, "rb") as f:
                existant = f.read()

        try:
            im, src, detail = meilleur_logo(key, name, existant)
            if im is None:
                continue
            _recadrer(im).save(dest, format="PNG")
            nb_telecharges += 1
        except Exception as e:
            print(f"Erreur sur le logo {key} : {e}")

        time.sleep(0.6)

    return nb_telecharges
