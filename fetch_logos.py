"""
fetch_logos.py — Récupère le MEILLEUR logo de chaque marque en comparant
plusieurs sources, puis l'enregistre (recadré) dans data/logos/.

Sources interrogées (best-effort, sans clé API) :
  1. Wikidata (propriété P154 "logo image")   [par nom]
  2. Wikimedia Commons (recherche de fichier)  [par nom]
  3. Wikipedia FR (image principale de page)   [par nom]
  4. DuckDuckGo (favicon)                       [par domaine]
  5. Google (favicon 256px)                     [par domaine]

L'agent télécharge les candidats, les NOTE (résolution, transparence, pas un
favicon minuscule, ratio raisonnable) et conserve le mieux noté.

Lancer :  python fetch_logos.py         (saute les logos déjà présents)
          python fetch_logos.py force   (re-télécharge tout)
"""
import urllib.parse, urllib.request, json, os, sys, time
from io import BytesIO
from PIL import Image, ImageChops

from src.logos import SEARCH, KNOWN_QID, COMMONS_FILE, DOMAINS, LOGO_DIR

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


# ── Helpers Wikidata / Commons ──────────────────────────────────────────────
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


def commons_file(name):
    d = _json("https://commons.wikimedia.org/w/api.php?action=query&list=search"
              f"&srsearch={urllib.parse.quote(name + ' logo')}&srnamespace=6&format=json&srlimit=8")
    for r in d.get("query", {}).get("search", []):
        t = r["title"].split("File:", 1)[-1]
        if t.lower().endswith((".svg", ".png")):
            return t
    return None


# ── Les 5 sources : renvoient des octets d'image (ou None) ──────────────────
def src_wikidata(key, name, domain):
    q = KNOWN_QID.get(key) or qid(name)
    fn = logo_file(q) if q else None
    return _get(thumb_png(fn)) if fn else None


def src_commons(key, name, domain):
    fn = commons_file(name)
    return _get(thumb_png(fn)) if fn else None


def src_iconhorse(key, name, domain):
    return _get(f"https://icon.horse/icon/{domain}") if domain else None


def src_ddg(key, name, domain):
    return _get(f"https://icons.duckduckgo.com/ip3/{domain}.ico") if domain else None


def src_google(key, name, domain):
    return _get(f"https://www.google.com/s2/favicons?domain={domain}&sz=256") if domain else None


# NB : pas de Wikipedia "pageimage" -> renvoie souvent une PHOTO (siège), pas le logo.
SOURCES = [("wikidata", src_wikidata), ("commons", src_commons),
           ("iconhorse", src_iconhorse), ("ddg", src_ddg), ("google", src_google)]


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


def meilleur_logo(key, name, domain, existant=None):
    """Interroge toutes les sources (+ le logo actuel comme candidat), note les
    candidats, renvoie le meilleur. Le logo actuel garantit qu'on ne dégrade
    jamais vers un favicon si une source échoue transitoirement."""
    best = (0.0, None, None)      # score, image, source
    detail = []
    if existant:
        sc, im = _qualite(existant)
        if sc > 0:
            best = (sc, im, "actuel"); detail.append(f"actuel={int(sc)}")
    for nom, fn in SOURCES:
        try:
            data = fn(key, name, domain)
        except Exception:
            data = None
        if not data:
            detail.append(f"{nom}=∅"); continue
        sc, im = _qualite(data)
        detail.append(f"{nom}={int(sc) if sc > 0 else '✗'}")
        if sc > best[0]:
            best = (sc, im, nom)
        time.sleep(0.3)
    return best[1], best[2], detail


if __name__ == "__main__":
    os.makedirs(LOGO_DIR, exist_ok=True)
    for key, name in SEARCH.items():
        dest = os.path.join(LOGO_DIR, key + ".png")
        if os.path.exists(dest) and not FORCE:
            print(f"SKIP {key}")
            continue
        existant = None
        if os.path.exists(dest):
            with open(dest, "rb") as f:
                existant = f.read()
        try:
            if key in COMMONS_FILE:               # fichier vérifié -> on le garde
                data = _get(thumb_png(COMMONS_FILE[key]))
                try:
                    im, src, detail = Image.open(BytesIO(data)), "commons-file", []
                    im.load()
                except Exception:                 # échec -> on retombe sur la comparaison
                    im, src, detail = meilleur_logo(key, name, DOMAINS.get(key), existant)
            else:
                im, src, detail = meilleur_logo(key, name, DOMAINS.get(key), existant)
            if im is None:
                print(f"MISS {key:18} | {'  '.join(detail)}")
                continue
            _recadrer(im).save(dest)
            print(f"OK   {key:18} <- {src:11} | {'  '.join(detail)}")
        except Exception as e:
            print(f"ERR  {key:18} {e}")
        time.sleep(0.6)
