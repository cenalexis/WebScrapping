# -*- coding: utf-8 -*-
"""corregir_codigos.py — Corrección determinista post-NLP de CIUO/SOC/CIIU.

El clasificador semántico confunde cargos cortos o con léxico engañoso
("Aseguramiento de Calidad" -> Agentes de Seguros; "Mesera" -> Matemáticos).
Esta capa aplica ANCLAS de alta precisión sobre el cargo: si el cargo matchea
un patrón inequívoco y el código asignado está FUERA de la familia esperada,
se sustituye por el código canónico del ancla con su SOC coherente.

CIIU (actividad económica): solo se corrige en ocupaciones inequívocamente
sectoriales (mesero, médico, docente, guardia...) Y cuando la empresa es
confidencial/genérica. Si el anuncio nombra una empresa real, el CIIU puede
reflejar la actividad de esa empresa (un chofer en una florícola es A01xx) y
NO se toca.

Es idempotente y forma parte del pipeline: correr SIEMPRE después del NLP.
Uso:
  python Codes/corregir_codigos.py --dry-run   # reporte, no escribe
  python Codes/corregir_codigos.py             # aplica
"""
import os, sys, re, unicodedata, argparse
import psycopg2
from psycopg2.extras import execute_values

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from db import _db_url


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# ── Anclas correctoras ────────────────────────────────────────────────────────
# (nombre, patron, excluir, familias_ok, resolver(cargo_norm) -> (ciuo, soc))
# familias_ok: prefijos CIUO que se consideran ya correctos (no se tocan).
# resolver decide el código fino según variantes dentro del ancla.

def _r_calidad(c):
    if re.search(r"software|qa\b|tester|sistemas|aplicaciones", c):
        return "2519", "15-1253.00"            # QA de software
    if re.search(r"jefe|coordinador|gerente|supervisor|lider", c):
        return "2141", "11-3051.01"            # gestión de calidad (ing. industrial)
    return "3119", "51-9061.00"                # inspección/análisis de calidad

def _r_chofer(c):
    if re.search(r"camion|trailer|tráiler|pesad|plataforma|volquet", c):
        return "8332", "53-3032.00"
    if re.search(r"bus\b|buseta|transporte de personal", c):
        return "8331", "53-3052.00"
    return "8322", "53-3033.00"

def _r_medico(c):
    if re.search(r"ocupacional|del trabajo|sst|seguridad y salud", c):
        return "2263", "29-1229.00"
    if re.search(r"cardiolog|dermatolog|pediatr|ginecol|traumatol|oftalmol|"
                 r"anestesi|radiolog|oncolog|psiquiatr|urolog|neurol|internista|"
                 r"especialista|cirujan", c):
        return "2212", "29-1229.00"
    return "2211", "29-1215.00"

def _r_docente(c):
    if re.search(r"universi|catedra|superior", c):
        return "2310", "25-1099.00"
    if re.search(r"primaria|basica elemental|elemental", c):
        return "2341", "25-2021.00"
    if re.search(r"inicial|parvul|preescolar", c):
        return "2342", "25-2011.00"
    return "2330", "25-2031.00"                # secundaria (default en portales)

def _r_rrhh(c):
    if re.search(r"jefe|gerente|director", c):
        return "1212", "11-3121.00"
    if re.search(r"asistente|auxiliar", c):
        return "4416", "43-4161.00"
    return "2423", "13-1071.00"

def _r_marketing(c):
    if re.search(r"jefe|gerente|director", c):
        return "1221", "11-2021.00"
    return "2431", "13-1161.00"

def _r_contable(c):
    if re.search(r"asistente|auxiliar", c):
        return "4311", "43-3031.00"
    return "2411", "13-2011.00"

def _r_enfermeria(c):
    if re.search(r"auxiliar", c):
        return "5321", "31-1131.00"
    return "2221", "29-1141.00"

def _r_vendedor(c):
    if re.search(r"asesor|ejecutiv", c):
        return "3322", "41-4012.00"            # representantes comerciales
    return "5223", "41-2031.00"                # vendedor de tienda/mostrador

_FIJA = lambda ciuo, soc: (lambda c: (ciuo, soc))

ANCLAS = [
    ("calidad",   r"\b(aseguramiento|control)\s+(de\s+(la\s+)?)?calidad\b", None,
     ("754", "312", "311", "214", "2519", "132"), _r_calidad),
    ("mesero",    r"\bmeser[oa]s?\b", None, ("513",), _FIJA("5131", "35-3031.00")),
    ("chofer",    r"\b(chofer|conductor(?:es)?)\b", r"licencia de conducir",
     ("83",), _r_chofer),
    ("medico",    r"\bmedic[oa]s?\b", r"visitador|insumos|equipos|venta|comercial|"
     r"reembolso|auditoria|cuentas|seguro|mercaimpulsadora|editor",
     ("221", "226", "22"), _r_medico),
    ("recepcionista", r"\brecepcionista\b", None, ("422",), _FIJA("4226", "43-4171.00")),
    ("cajero",    r"\bcajer[oa]s?\b", r"banco|bancario|financier",
     ("523", "421"), _FIJA("5230", "41-2011.00")),
    ("cajero bancario", r"\bcajer[oa]s?\b.*\b(banco|bancari[oa]|financier)", None,
     ("421",), _FIJA("4211", "43-3071.00")),
    ("bodeguero", r"\b(bodeguer[oa]s?|(?:auxiliar|ayudante|asistente) de bodega)\b", None,
     ("432", "933", "962"), _FIJA("4321", "43-5071.00")),
    ("soldador",  r"\bsoldador(?:es)?\b", None, ("721",), _FIJA("7212", "51-4121.00")),
    ("costura",   r"\b(costurer[oa]s?|operari[oa] de confeccion)\b", None,
     ("753", "815"), _FIJA("7531", "51-6052.00")),
    ("digitador", r"\bdigitador[a]?(?:es)?\b", None, ("413",), _FIJA("4132", "43-9021.00")),
    ("guardia",   r"\b(guardia|guardian|guardianes|vigilante|bouncer)e?s?\b", r"guardia de datos",
     ("541",), _FIJA("5414", "33-9032.00")),
    ("limpieza",  r"\b(auxiliar|personal|operari[oa])\b.*\blimpieza\b|\bconserje\b", None,
     ("91", "515"), _FIJA("9112", "37-2011.00")),
    ("panadero",  r"\b(panader[oa]s?|pasteler[oa]s?)\b", None, ("751",), _FIJA("7512", "51-3011.00")),
    ("electricista", r"\belectricistas?\b", None, ("741", "31"), _FIJA("7411", "47-2111.00")),
    ("mec.automotriz", r"\bmecanic[oa]s?\b.*\b(automotriz|autos|vehicul|taller)\b"
     r"|\b(automotriz|vehicul)\w*\b.*\bmecanic[oa]s?\b", None,
     ("723", "31"), _FIJA("7231", "49-3023.00")),
    ("docente",   r"\b(docente|profesor[a]?|maestr[oa])\b", r"chef|conduccion|yoga|gimnas",
     ("23",), _r_docente),
    ("callcenter", r"\b(call center|teleoperador|telefonista)\b", None,
     ("422", "524"), _FIJA("4222", "43-4051.00")),
    ("rrhh",      r"\b(recursos humanos|talento humano|rrhh)\b", None,
     ("242", "441", "12"), _r_rrhh),
    ("marketing", r"\b(marketing|mercadeo)\b", r"digitador",
     ("243", "244", "12", "35"), _r_marketing),
    ("contable",  r"\b(contador[a]?|contable)\b", None,
     ("241", "431", "331", "12"), _r_contable),
    ("bombero",   r"\bbomber[oa]s?\b", None, ("541",), _FIJA("5411", "33-2011.00")),
    ("enfermeria", r"\benfermer[oa]s?\b", None, ("222", "322", "532"), _r_enfermeria),
    ("abogado",   r"\babogad[oa]s?\b", None, ("261", "341"), _FIJA("2611", "23-1011.00")),
    ("psicologo", r"\bpsicolog[oa]s?\b", None, ("263",), _FIJA("2634", "19-3033.00")),
    ("vendedor",  r"\b(vendedor[a]?(?:es)?|asesor[a]?(?:es)? (?:comercial|de ventas?|de negocios)|"
     r"ejecutiv[oa]s? (?:comercial|de ventas?)|agentes? de ventas?)\b",
     r"visitador", ("52", "24", "33", "12", "43"), _r_vendedor),
    ("ciberseguridad", r"\bciberseguridad\b|\bseguridad (informatica|de la informacion)\b", None,
     ("25",), _FIJA("2529", "15-1212.00")),
    # ── Plaga del "código basurero" 3257/2263: el NLP los asigna a cargos sin
    #    ninguna relación con salud laboral. Anclas para los patrones masivos.
    ("adm.tienda", r"\b(administrador|encargad[oa]|lider|jefe)\b.{0,4}\bde\b.{0,4}\b(local(es)?|tienda|almacen(es)?|farmacia|concesionario)\b", None,
     ("522", "14", "13", "12"), _FIJA("5222", "41-1011.00")),
    ("mercaderista", r"\bmercaderista\b|\bmercaimpulsador", None, ("52",), _FIJA("5223", "27-1026.00")),
    ("op.produccion", r"\b(operador[a]?|operari[oa]|obrer[oa]|auxiliar|ayudante)(?:es)?\b.{0,14}\bde\b.{0,4}\b(produccion|planta|envasado|empaque|laminacion|impresion|manufactura)\b", None,
     ("81", "82", "93", "75", "72"), _FIJA("8189", "51-9199.00")),
    ("cocinero", r"\bcociner[oa]s?\b|\bsusher[oa]\b|\bitamae\b|\brepostero\b", None,
     ("512", "941", "343"), _FIJA("5120", "35-2014.00")),
    ("belleza", r"\b(manicurista|estilista|cosmetolog\w+|peluquer[oa]|barber[oa])\b|especialista en cejas", None,
     ("514",), _FIJA("5141", "39-5012.00")),
    ("bar", r"\b(bartender|barman)\b|jefe de bar\b", None, ("513",), _FIJA("5132", "35-3011.00")),
    ("posillero", r"\b(posillero|lavaplatos|lavavajillas|steward de cocina)\b", None,
     ("941",), _FIJA("9412", "35-9021.00")),
    ("lavador autos", r"\blavador(?:a|es)? de (vehiculos|autos|carros)\b", None,
     ("912",), _FIJA("9122", "53-7061.00")),
    ("flebotomista", r"\bflebotomista\b", None, ("321",), _FIJA("3212", "31-9097.00")),
    ("jefe mantenimiento", r"\b(jefe|coordinador|supervisor)\b.{0,4}\bde\b.{0,4}\bmantenimiento\b", None,
     ("311", "723", "132", "13"), _FIJA("3115", "49-1011.00")),
    ("encuestador", r"\bencuestador(?:a|es)?\b", None, ("422", "413"), _FIJA("4227", "43-4111.00")),
    ("anfitrion", r"\banfitrion(?:a|es)?\b|\bhostess\b", None, ("516", "422", "513"),
     _FIJA("5169", "35-9031.00")),
    ("trabajo social", r"\btrabajador[a]? social\b", None, ("263", "341"),
     _FIJA("2635", "21-1021.00")),
    ("arq.datos",  r"\barquitect[oa] (?:de |en )?(datos|software|soluciones|sistemas|nube|cloud|big ?data|power ?bi)\b",
     None, ("25",), _FIJA("2521", "15-1243.00")),
    ("arquitecto", r"\barquitect[oa]s?\b",
     r"arquitect[oa] (?:de |en )?(datos|software|soluciones|sistemas|nube|cloud|big ?data|power ?bi)",
     ("216", "311", "343"), _FIJA("2161", "17-1011.00")),
    ("inventarios", r"\banalista de inventarios?\b", None,
     ("432", "413", "24", "33", "12"), _FIJA("4321", "43-5081.00")),
]

# ── CIIU sectorial para ocupaciones inequívocas (solo con empresa genérica) ──
CIUO2CIIU = {
    "5131": "I5610", "7512": "C1071", "2211": "Q8620", "2212": "Q8620",
    "2263": "Q8620", "2221": "Q8610", "5321": "Q8710", "9112": "N8121",
    "5414": "N8010", "5411": "O8423", "8322": "H4922", "8331": "H4921",
    "8332": "H4923", "2310": "P8530", "2330": "P8521", "2341": "P8510",
    "2342": "P8510", "7231": "G4520",
}
_EMPRESA_GENERICA = re.compile(
    r"^(confidencial|empresa confidencial|importante empresa|empresa del sector"
    r"|empresa l[ií]der|reservado|no especificado|multinacional|prestigiosa)", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(_db_url(), connect_timeout=20, keepalives=1,
                            keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    cur = conn.cursor()
    cur.execute("""SELECT id, cargo_raw, empresa_raw, codigo_ciuo, codigo_soc, codigo_ciiu
                   FROM vacantes WHERE codigo_ciuo IS NOT NULL AND codigo_ciuo <> ''""")
    filas = cur.fetchall()
    print(f"Vacantes evaluadas: {len(filas):,}")

    comp = [(n, re.compile(rx), re.compile(ex) if ex else None, fams, res)
            for n, rx, ex, fams, res in ANCLAS]

    cambios = []          # (id, ciuo, soc, ciiu)
    por_ancla = {}
    for vid, cargo, empresa, ciuo, soc, ciiu in filas:
        c = _norm(cargo)
        cod = str(ciuo).strip()
        if cod.isdigit() and len(cod) == 3:
            cod = cod.zfill(4)
        for nombre, rx, ex, fams, res in comp:
            if not rx.search(c) or (ex and ex.search(c)):
                continue
            if any(cod.startswith(p) for p in fams):
                break                          # ya coherente: no tocar
            nuevo_ciuo, nuevo_soc = res(c)
            # CIIU solo si la ocupación es sectorial Y la empresa es genérica/vacía
            nuevo_ciiu = None
            if nuevo_ciuo in CIUO2CIIU:
                emp = (empresa or "").strip()
                if not emp or _EMPRESA_GENERICA.search(emp):
                    esperada = CIUO2CIIU[nuevo_ciuo]
                    if not str(ciiu or "").startswith(esperada[0]):
                        nuevo_ciiu = esperada
            cambios.append((vid, nuevo_ciuo, nuevo_soc, nuevo_ciiu or ciiu))
            por_ancla[nombre] = por_ancla.get(nombre, 0) + 1
            break

    print(f"\nCorrecciones propuestas: {len(cambios):,}")
    for n, k in sorted(por_ancla.items(), key=lambda x: -x[1]):
        print(f"  {n:20} {k:>4}")

    if args.dry_run:
        print("\n[DRY-RUN] Muestra:")
        for vid, nc, ns, ni in cambios[:20]:
            print(f"  id={vid:<6} -> ciuo={nc} soc={ns} ciiu={ni}")
        cur.close(); conn.close(); return

    if not cambios:
        print("Nada que corregir."); return
    for i in range(0, len(cambios), 300):
        execute_values(cur, """
            UPDATE vacantes SET codigo_ciuo = d.c::text, codigo_soc = d.s::text,
                                codigo_ciiu = d.i::text
            FROM (VALUES %s) AS d(vid, c, s, i)
            WHERE vacantes.id = d.vid::bigint
        """, [(v, c, s, i) for v, c, s, i in cambios[i:i+300]])
        conn.commit()
    print(f"OK: {len(cambios):,} vacantes corregidas en BD.")
    cur.close(); conn.close()


if __name__ == "__main__":
    main()
