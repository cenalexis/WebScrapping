# -*- coding: utf-8 -*-
"""generar_keywords.py — Variable `key_words`: contextualiza cada fila de
`vacantes` con las palabras más DISTINTIVAS de su propio anuncio.

No es una clasificación (eso lo hacen nlp_pipeline.py y revisar_ia.py): es una
foto rápida y legible del anuncio en sí, útil para auditar a simple vista si
un código CIUO/carrera asignado tiene sentido frente a lo que el anuncio
realmente dice, sin abrir la descripción completa cada vez.

Método (determinista, sin llamadas a modelos de lenguaje — corre sobre toda
la base en minutos):
  1. cargo_raw + requisitos_raw + descripcion_raw, limpiando el ruido propio
     del portal (mismo patrón que revisar_ia.py).
  2. spaCy (es_core_news_sm, ya es dependencia del proyecto): se lematizan
     los sustantivos y nombres propios (NOUN/PROPN) — son los que de verdad
     funcionan como palabra clave en un aviso de empleo.
  3. TF-IDF, no solo frecuencia: "educación", "año", "perfil", "gestión"
     aparecen en la enorme mayoría de los anuncios (cualquier rubro) y no
     distinguen nada; se calcula la frecuencia de documento (DF) de cada
     lema sobre TODO el corpus una vez, y se pondera cada candidato por
     TF_en_el_anuncio x IDF (con un bono si el lema también aparece en el
     título, la señal más confiable de qué es el puesto). Así "ecografista"
     o "cuchillo" pesan más que "perfil" o "aptitud", sin mantener una lista
     de palabras prohibidas a mano.
  4. Se guardan las 8 palabras con mayor puntaje, en el orden en que aparecen
     por primera vez en el texto (para que la fila se lea como una frase).

El IDF se calcula sobre el corpus completo y se cachea en
exports/nlp/idf_lemas.json; con el paso de nuevas vacantes el cache sigue
siendo representativo — usar --recalc-idf para refrescarlo (recomendable
cada tanto, no en cada corrida incremental).

Uso:
  python Codes/generar_keywords.py --dry-run          ejemplo sin escribir
  python Codes/generar_keywords.py --max 500           procesa hasta 500 filas
  python Codes/generar_keywords.py                     todas las pendientes
  python Codes/generar_keywords.py --todos             recalcula TODAS (idempotente)
  python Codes/generar_keywords.py --recalc-idf        refresca el IDF con el corpus actual
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from db import conectar, _db_url
import psycopg2 as _pg

EXPORT_DIR = os.path.join(ROOT, "exports", "nlp")
IDF_CACHE = os.path.join(EXPORT_DIR, "idf_lemas.json")

_RUIDO_PORTAL = re.compile(
    r"(Volver al listado|Ocultaste esta oferta[^.]*?listados|Eliminado de Ofertas ocultas"
    r"|Deshacer|pulsa Recuperar oferta[^.]*?|Descripci[oó]n de la oferta"
    r"|Postulaci[oó]n r[aá]pida|Actualizado (hace|ayer)[^\n]*|[Uu]nete a nuestro equipo!?)",
    re.I)

N_PALABRAS = 8
MIN_LARGO = 3
BONO_TITULO = 2.0     # multiplicador de TF si el lema también está en cargo_raw

_NLP_ES = None


def _cargar_spacy():
    global _NLP_ES
    if _NLP_ES is not None:
        return _NLP_ES
    import spacy
    try:
        _NLP_ES = spacy.load("es_core_news_sm", disable=["parser", "ner"])
    except OSError:
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "es_core_news_sm"], check=True)
        _NLP_ES = spacy.load("es_core_news_sm", disable=["parser", "ner"])
    print("  spaCy es_core_news_sm cargado (solo tagger+lemmatizer)")
    return _NLP_ES


def _limpiar(texto):
    t = _RUIDO_PORTAL.sub(" ", str(texto or ""))
    return re.sub(r"\s+", " ", t).strip()


def _texto_completo(cargo, requisitos, descripcion):
    cargo_l = _limpiar(cargo)[:200]
    cuerpo = " ".join(_limpiar(x) for x in (requisitos, descripcion) if x)[:3000]
    return cargo_l, (f"{cargo_l}. {cuerpo}" if cuerpo else cargo_l)


def _lemas_noun_propn(doc):
    for tok in doc:
        if tok.pos_ in ("NOUN", "PROPN") and not tok.is_stop and tok.is_alpha \
           and len(tok.lemma_) >= MIN_LARGO:
            yield tok.lemma_.lower()


def calcular_idf(filas, nlp, lote_spacy=64):
    """DF (nº de anuncios donde aparece cada lema) sobre todo el corpus."""
    df = Counter()
    n = 0
    textos = [_texto_completo(c, r, d)[1] for _, c, r, d in filas]
    for doc in nlp.pipe(textos, batch_size=lote_spacy):
        n += 1
        df.update(set(_lemas_noun_propn(doc)))
        if n % 1000 == 0:
            print(f"    IDF: {n:,}/{len(textos):,} anuncios procesados")
    idf = {lema: math.log(n / (1 + c)) for lema, c in df.items()}
    return idf, n


def guardar_idf(idf, n_docs):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    json.dump({"n_docs": n_docs, "idf": idf}, open(IDF_CACHE, "w", encoding="utf-8"),
               ensure_ascii=False)
    print(f"  IDF guardado: {len(idf):,} lemas sobre {n_docs:,} anuncios -> {IDF_CACHE}")


def cargar_idf():
    if not os.path.exists(IDF_CACHE):
        return None
    data = json.load(open(IDF_CACHE, encoding="utf-8"))
    return data["idf"], data["n_docs"]


def extraer_keywords(cargo, requisitos, descripcion, idf, nlp=None, doc=None):
    """Devuelve la cadena `key_words` (pipe-separado) para un anuncio, dado
    un IDF ya calculado sobre el corpus."""
    nlp = nlp or _cargar_spacy()
    cargo_l, texto = _texto_completo(cargo, requisitos, descripcion)
    if not texto.strip():
        return ""
    doc = doc or nlp(texto)
    titulo_lemas = set(_lemas_noun_propn(nlp(cargo_l)))

    tf, primera_pos = Counter(), {}
    for i, tok in enumerate(doc):
        if tok.pos_ not in ("NOUN", "PROPN"):
            continue
        if tok.is_stop or not tok.is_alpha or len(tok.lemma_) < MIN_LARGO:
            continue
        lema = tok.lemma_.lower()
        tf[lema] += 1
        primera_pos.setdefault(lema, i)

    if not tf:
        return ""
    idf_media = (sum(idf.values()) / len(idf)) if idf else 1.0
    def _score(lema):
        peso_tf = tf[lema] * (BONO_TITULO if lema in titulo_lemas else 1.0)
        return peso_tf * idf.get(lema, idf_media)

    top = sorted(tf, key=lambda k: (-_score(k), primera_pos[k]))[:N_PALABRAS]
    top.sort(key=lambda k: primera_pos[k])   # se leen en el orden del anuncio
    return " | ".join(top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="tope de filas; 0 = todas las pendientes")
    ap.add_argument("--todos", action="store_true", help="recalcula TODAS las filas, no solo las pendientes")
    ap.add_argument("--lote", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recalc-idf", action="store_true", help="recalcula el IDF sobre el corpus actual")
    args = ap.parse_args()

    conn = conectar()
    cur = conn.cursor()
    cur.execute("ALTER TABLE vacantes ADD COLUMN IF NOT EXISTS key_words TEXT")
    conn.commit()

    nlp = _cargar_spacy()

    idf_cache = cargar_idf()
    if args.recalc_idf or idf_cache is None:
        print("Calculando IDF sobre todo el corpus (una sola vez, se cachea)...")
        cur.execute("SELECT id, cargo_raw, requisitos_raw, descripcion_raw FROM vacantes")
        todas = cur.fetchall()
        idf, n_docs = calcular_idf(todas, nlp)
        guardar_idf(idf, n_docs)
    else:
        idf, n_docs = idf_cache
        print(f"IDF cacheado: {len(idf):,} lemas sobre {n_docs:,} anuncios (usa --recalc-idf para refrescar)")

    filtro = "" if args.todos else "AND (key_words IS NULL OR key_words = '')"
    cur.execute(f"SELECT COUNT(*) FROM vacantes WHERE 1=1 {filtro}")
    total_pend = cur.fetchone()[0]
    tope = args.max if args.max > 0 else total_pend
    print(f"Pendientes: {total_pend:,} | esta corrida: {min(tope, total_pend):,}")

    cur.execute(f"""SELECT id, cargo_raw, requisitos_raw, descripcion_raw
                    FROM vacantes WHERE 1=1 {filtro} ORDER BY id LIMIT %s""", (tope,))
    filas = cur.fetchall()
    if not filas:
        print("Nada que hacer."); return

    if args.dry_run:
        for vid, cargo, req, desc in filas[:8]:
            kw = extraer_keywords(cargo, req, desc, idf, nlp)
            print(f"  [{vid}] {cargo!r} -> {kw}")
        print(f"\n[DRY-RUN] {len(filas):,} filas se procesarian. Sin escribir.")
        return

    hechas = 0
    for i in range(0, len(filas), args.lote):
        lote = filas[i:i + args.lote]
        for intento in (1, 2):
            try:
                cur = conn.cursor()
                for vid, cargo, req, desc in lote:
                    kw = extraer_keywords(cargo, req, desc, idf, nlp)
                    cur.execute("UPDATE vacantes SET key_words = %s WHERE id = %s", (kw, vid))
                conn.commit()
                break
            except (_pg.OperationalError, _pg.InterfaceError):
                if intento == 2:
                    raise
                conn = _pg.connect(_db_url(), connect_timeout=20, keepalives=1,
                                   keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
        hechas += len(lote)
        print(f"  {hechas:,}/{len(filas):,} procesadas")

    print(f"\nOK: {hechas:,} filas actualizadas con key_words.")


if __name__ == "__main__":
    main()
