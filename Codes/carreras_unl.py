# -*- coding: utf-8 -*-
"""Clasificacion de vacantes por carrera de la UNL (40 carreras).
match_carreras(texto) -> lista de carreras cuyos terminos aparecen (multi-etiqueta)."""
import re, unicodedata

TERMINOS_POR_CARRERA = {
 "Agronomía": [
  "agrónomo",
  "ingeniero agrónomo",
  "producción agrícola",
  "cultivos",
  "fitotecnia",
  "agronomía"
 ],
 "Ingeniería Agrícola": [
  "ingeniero agrícola",
  "riego y drenaje",
  "infraestructura agrícola",
  "mecanización agrícola",
  "hidráulica agrícola"
 ],
 "Ingeniería Ambiental": [
  "ingeniero ambiental",
  "gestión ambiental",
  "consultor ambiental",
  "analista ambiental",
  "auditor ambiental",
  "coordinador de sostenibilidad",
  "especialista de sostenibilidad",
  "especialista en sostenibilidad"
 ],
 "Ingeniería Forestal": [
  "ingeniero forestal",
  "silvicultura",
  "manejo forestal",
  "gestión forestal",
  "reforestación",
  "recursos forestales"
 ],
 "Medicina Veterinaria": [
  "médico veterinario",
  "veterinario",
  "zootecnista",
  "clínica veterinaria",
  "sanidad animal"
 ],
 "Agronegocios": [
  "agronegocios",
  "negocios agrícolas",
  "comercialización agropecuaria",
  "cadena de valor agrícola",
  "agroempresa"
 ],
 "Artes Musicales": [
  "músico",
  "director musical",
  "instructor de música",
  "docente de música",
  "musicólogo",
  "productor musical"
 ],
 "Artes Visuales": [
  "diseñador gráfico",
  "artista visual",
  "ilustrador",
  "diseñador multimedia",
  "diseñador de contenido visual"
 ],
 "Comunicación": [
  "comunicador social",
  "periodista",
  "relacionador público",
  "comunicación corporativa",
  "community manager",
  "editor de contenidos"
 ],
 "Educación Básica": [
  "docente educación básica",
  "maestro de primaria",
  "profesor educación general básica",
  "tutor escolar"
 ],
 "Educación Especial": [
  "educador especial",
  "docente educación especial",
  "inclusión educativa",
  "terapista de lenguaje"
 ],
 "Educación Inicial": [
  "docente educación inicial",
  "parvulario",
  "profesor inicial",
  "estimulación temprana",
  "educadora de párvulos"
 ],
 "Pedagogía de la Actividad Física y Deporte": [
  "educación física",
  "entrenador deportivo",
  "profesor de deportes",
  "preparador físico",
  "entrenador personal"
 ],
 "Pedagogía de la Lengua y la Literatura": [
  "docente lengua y literatura",
  "profesor de español",
  "corrector de estilo",
  "docente de lenguaje"
 ],
 "Pedagogía de las CC. Experimentales - Informática": [
  "docente de informática",
  "profesor de computación",
  "tecnología educativa",
  "docente TIC"
 ],
 "Pedagogía de las CC. Experimentales - Matemáticas y Física": [
  "docente de matemáticas",
  "profesor de física",
  "tutor de matemáticas",
  "docente ciencias exactas"
 ],
 "Pedagogía de las CC. Experimentales - Química y Biología": [
  "docente de química",
  "profesor de biología",
  "docente ciencias naturales",
  "laboratorista escolar"
 ],
 "Pedagogía de los Idiomas Nacionales y Extranjeros": [
  "docente de inglés",
  "profesor de idiomas",
  "traductor",
  "intérprete",
  "docente bilingüe"
 ],
 "Psicopedagogía": [
  "psicopedagogo",
  "orientador educativo",
  "consejero estudiantil",
  "orientador vocacional",
  "DECE"
 ],
 "Arquitectura Sostenible": [
  "arquitecto",
  "arquitecto sostenible",
  "diseño arquitectónico",
  "urbanismo",
  "planificación urbana",
  "BIM"
 ],
 "Computación": [
  "ingeniero en sistemas",
  "analista de sistemas",
  "técnico en computación",
  "soporte técnico",
  "administrador de sistemas"
 ],
 "Electricidad": [
  "ingeniero eléctrico",
  "técnico electricista",
  "electricidad industrial",
  "redes eléctricas",
  "instalaciones eléctricas"
 ],
 "Electromecánica": [
  "ingeniero electromecánico",
  "técnico electromecánico",
  "mantenimiento industrial",
  "automatización industrial"
 ],
 "Ingeniería Automotriz": [
  "ingeniero automotriz",
  "mecánico automotriz",
  "diagnóstico automotriz",
  "técnico automotriz"
 ],
 "Ingeniería Civil": [
  "ingeniero civil",
  "residente de obra",
  "director de obra",
  "obras civiles",
  "gerente de construcción",
  "fiscalizador de obras"
 ],
 "Minas": [
  "ingeniero de minas",
  "ingeniero minero",
  "geólogo",
  "extracción minera",
  "seguridad minera",
  "topógrafo minero"
 ],
 "Telecomunicaciones": [
  "ingeniero en telecomunicaciones",
  "redes y telecomunicaciones",
  "técnico en redes",
  "administrador de redes",
  "infraestructura de redes"
 ],
 "Administración de Empresas": [
  "administrador de empresas",
  "gerente administrativo",
  "jefe administrativo",
  "coordinador administrativo",
  "director de operaciones",
  "gestor empresarial"
 ],
 "Administración Pública": [
  "administrador público",
  "gestión pública",
  "servidor público",
  "funcionario público",
  "gestión municipal",
  "coordinador de gobierno"
 ],
 "Contabilidad y Auditoría": [
  "contador general",
  "auditor",
  "tributación",
  "analista contable",
  "jefe contable",
  "asistente contable",
  "contador CPA"
 ],
 "Derecho": [
  "abogado",
  "asesor legal",
  "jurídico",
  "abogado corporativo",
  "asesor jurídico",
  "notario",
  "abogado laboral"
 ],
 "Economía": [
  "economista",
  "analista económico",
  "investigador económico",
  "consultor económico",
  "analista de políticas económicas"
 ],
 "Finanzas": [
  "analista financiero",
  "tesorero",
  "jefe financiero",
  "director financiero",
  "analista de riesgos",
  "controller financiero"
 ],
 "Trabajo Social": [
  "trabajador social",
  "asistente social",
  "gestor social",
  "promotor social",
  "coordinador social"
 ],
 "Turismo": [
  "guía turístico",
  "gerente de hotel",
  "agente de viajes",
  "coordinador de turismo",
  "operador turístico",
  "recepcionista de hotel"
 ],
 "Enfermería": [
  "enfermero",
  "enfermera",
  "auxiliar de enfermería",
  "enfermero clínico",
  "enfermero comunitario"
 ],
 "Laboratorio Clínico": [
  "bioquímico",
  "laboratorista clínico",
  "analista de laboratorio",
  "tecnólogo médico",
  "analista de laboratorio clínico"
 ],
 "Medicina": [
  "médico general",
  "médico especialista",
  "médico rural",
  "residente médico",
  "médico tratante"
 ],
 "Odontología": [
  "odontólogo",
  "dentista",
  "cirujano oral",
  "odontólogo general",
  "especialista en ortodoncia"
 ],
 "Psicología Clínica": [
  "psicólogo clínico",
  "psicoterapeuta",
  "psicólogo organizacional",
  "psicólogo educativo",
  "salud mental"
 ]
}

FACULTAD = {
 "Agropecuaria y RNNR": [
  "Agronomía",
  "Ingeniería Agrícola",
  "Ingeniería Ambiental",
  "Ingeniería Forestal",
  "Medicina Veterinaria",
  "Agronegocios"
 ],
 "Educación, Arte y Comunicación": [
  "Artes Musicales",
  "Artes Visuales",
  "Comunicación",
  "Educación Básica",
  "Educación Especial",
  "Educación Inicial",
  "Pedagogía de la Actividad Física y Deporte",
  "Pedagogía de la Lengua y la Literatura",
  "Pedagogía de las CC. Experimentales - Informática",
  "Pedagogía de las CC. Experimentales - Matemáticas y Física",
  "Pedagogía de las CC. Experimentales - Química y Biología",
  "Pedagogía de los Idiomas Nacionales y Extranjeros",
  "Psicopedagogía"
 ],
 "Energía, Industrias y RNNR": [
  "Arquitectura Sostenible",
  "Computación",
  "Electricidad",
  "Electromecánica",
  "Ingeniería Automotriz",
  "Ingeniería Civil",
  "Minas",
  "Telecomunicaciones"
 ],
 "Jurídica, Social y Administrativa": [
  "Administración de Empresas",
  "Administración Pública",
  "Contabilidad y Auditoría",
  "Derecho",
  "Economía",
  "Finanzas",
  "Trabajo Social",
  "Turismo"
 ],
 "Salud Humana": [
  "Enfermería",
  "Laboratorio Clínico",
  "Medicina",
  "Odontología",
  "Psicología Clínica"
 ]
}

def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))

_RE = {car: re.compile(r"\b(?:" + "|".join(re.escape(_norm(x)) for x in terms) + r")\b")
       for car, terms in TERMINOS_POR_CARRERA.items()}

# Frases de ruido que mencionan terminos de carrera sin ser el perfil del puesto
# (beneficios: "seguro medico", "seguro odontologico", ...). Se neutralizan antes
# de emparejar para evitar falsos positivos (p. ej. "seguro medico" -> Medicina).
_FRASES_RUIDO = re.compile(
    r"seguro\s+(?:medico|de\s+salud|odontologico|dental|de\s+vida|privado)\w*"
    r"|atencion\s+medica|chequeos?\s+medicos?|examenes?\s+medicos?"
    # Campo de escolaridad del CANDIDATO en CT/MT ("Educacion minima: Educacion
    # Basica / Bachillerato..."): NO es demanda de docentes — sin esto, cualquier
    # anuncio de ventas disparaba Educacion Basica (y sus afines Inicial y
    # Psicopedagogia). Se neutraliza la frase completa hasta fin de linea.
    r"|(?:educacion|instruccion|formacion)\s+minima[^\n]{0,80}"
    r"|nivel\s+de\s+(?:educacion|instruccion|estudios?)[^\n]{0,80}"
    # Requisito ofimatico ("manejo de sistemas informaticos" = saber usar la
    # computadora): NO es demanda de profesionales de Computacion.
    r"|(?:manejo|conocimientos?|dominio|uso)\s+de\s+(?:sistemas|paquetes|herramientas|utilitarios)\s+informatic\w+"
    # "Arquitecto de datos/software/nube/Power BI" es figura informatica,
    # no demanda de la carrera de Arquitectura.
    r"|arquitect\w*\s+(?:de\s+|en\s+)?(?:datos|software|soluciones|sistemas|nube|cloud|big\s*data|power\s*bi|microservicios|informacion)")

def match_carreras(texto):
    """Devuelve la lista de carreras UNL para las que el texto califica."""
    t = _FRASES_RUIDO.sub(" ", _norm(texto))
    return [car for car, rx in _RE.items() if rx.search(t)]


# === Mapeo CIUO-08 -> carrera (para cobertura de titulos no explicitos) ===
CIUO_POR_CARRERA = {'Agronomía': ['2132'], 'Ingeniería Agrícola': ['2132'], 'Ingeniería Forestal': ['2132'], 'Ingeniería Ambiental': ['2133'], 'Medicina Veterinaria': ['2250'], 'Artes Musicales': ['2652'], 'Artes Visuales': ['2166', '2651'], 'Comunicación': ['2642', '2432'], 'Educación Básica': ['2341'], 'Educación Inicial': ['2342'], 'Educación Especial': ['2352'], 'Pedagogía de los Idiomas Nacionales y Extranjeros': ['2353', '2643'], 'Arquitectura Sostenible': ['2161'], 'Computación': ['2511', '2512', '2513', '2514', '2519', '2521', '2522', '2529', '3511', '3512', '3513', '2356'], 'Electricidad': ['2151', '7411', '7412'], 'Electromecánica': ['2144'], 'Ingeniería Automotriz': ['7231'], 'Ingeniería Civil': ['2142'], 'Minas': ['2146', '2114'], 'Telecomunicaciones': ['2153', '2523', '3522'], 'Administración de Empresas': ['1120', '2421', '1219', '2431', '1221'], 'Administración Pública': ['1112'], 'Contabilidad y Auditoría': ['2411', '3313', '4311'], 'Derecho': ['2611', '2612', '2619'], 'Economía': ['2631'], 'Finanzas': ['2412', '1211', '3311', '2413', '3312', '1346'], 'Trabajo Social': ['2635'], 'Turismo': ['1411', '4221'], 'Enfermería': ['2221', '3221'], 'Laboratorio Clínico': ['3212', '2212'], 'Medicina': ['2211'], 'Odontología': ['2261'], 'Psicología Clínica': ['2634']}
_COD2CAR = {}
for _car, _cods in CIUO_POR_CARRERA.items():
    for _cod in _cods: _COD2CAR.setdefault(_cod, []).append(_car)

def carreras_por_codigo(ciuo):
    return _COD2CAR.get(str(ciuo or "").strip(), [])

# Carreras del area de salud y prefijos CIUO-08 que les corresponden
# (22 = profesionales de la salud, 32 = tecnicos/asociados de la salud).
_CARRERAS_SALUD = {"Medicina", "Enfermería", "Odontología",
                   "Laboratorio Clínico", "Psicología Clínica",
                   "Medicina Veterinaria"}
_CIUO_SALUD_PREF = ("22", "32")

def clasificar(texto, ciuo=None, con_afines=True):
    """Asigna carreras UNL a una vacante (multi-etiqueta).

    Senal PRIMARIA: la mineria de texto (profesion_requerida + cargo). El codigo
    CIUO es solo RESPALDO: se usa unicamente cuando el texto no asigno ninguna
    carrera, para no inflar ni contradecir lo que dice el anuncio.

    A cada carrera base se le suman sus AFINES curadas (clusters cerrados de
    sustituibilidad real). Las disciplinas que la UNL no oferta (ing. industrial,
    logistica, gastronomia...) se enrutan a su carrera UNL mas cercana via
    EXTERNAS, sin volver a expandir afines.

    Vetos: (a) ocupacion elemental (CIUO gran grupo 9) -> sin carrera; (b) carrera
    de salud cuando el CIUO no es del area de salud (prefijo != 22/32) -> se
    descarta (p. ej. 'seguro medico' -> Medicina en un puesto de ventas)."""
    cod = str(ciuo or "").strip()
    if cod.isdigit() and len(cod) == 3:
        cod = cod.zfill(4)
    # (a) Ocupacion elemental: sin carrera (ni por texto ni por codigo).
    if cod[:1] == "9":
        return []
    veta_salud = bool(cod) and len(cod) >= 2 and cod[:2] not in _CIUO_SALUD_PREF
    # Senal primaria: texto del anuncio.  Externas = disciplinas que no oferta UNL.
    base = set(match_carreras(texto))
    ext  = set(match_externas(texto))
    # Respaldo por codigo CIUO solo si el texto no asigno nada.
    if not base and not ext and cod:
        base |= set(carreras_por_codigo(cod))
    # Afines curadas de las carreras base (no de las externas, ya acotadas).
    if con_afines:
        for c in list(base):
            base.update(AFINES_POR_CARRERA.get(c, ()))
    resultado = base | ext
    # (b) Veto de salud sobre el resultado final (incluye afines).
    if veta_salud:
        resultado -= _CARRERAS_SALUD
    return sorted(resultado)


def clasificar_vacante(profesion=None, cargo=None, ciuo=None, con_afines=True):
    """Wrapper del pipeline: combina profesion_requerida + cargo como texto.
    Devuelve lista ordenada; vacia = vacante no profesional / sin carrera UNL."""
    texto = " || ".join(x for x in (profesion, cargo) if x)
    return clasificar(texto, ciuo=ciuo, con_afines=con_afines)


# Enriquecimiento: nombres de campo/carrera + variantes (robustez)
_EXTRA = {'Finanzas': ['finanzas', 'financiero', 'financiera'], 'Contabilidad y Auditoría': ['contabilidad', 'contable', 'auditoria', 'contador', 'contadora', 'cpa'], 'Economía': ['economia', 'economista', 'economico'], 'Derecho': ['derecho', 'juridico', 'juridica', 'abogada'], 'Administración de Empresas': ['administracion de empresas', 'administracion comercial', 'administracion de negocios', 'ingenieria comercial', 'ingeniero comercial'], 'Administración Pública': ['administracion publica'], 'Computación': ['computacion', 'informatica', 'ingenieria en sistemas', 'sistemas informaticos', 'desarrollador de software', 'desarrollador web', 'desarrollador de aplicaciones', 'desarrollador full stack', 'desarrollador backend', 'desarrollador frontend', 'desarrollador de sistemas', 'desarrollador movil', 'programador', 'ingeniero de software', 'tecnologo en sistemas', 'tecnologia en sistemas'], 'Electromecánica': ['electromecanica', 'mecatronica', 'mecatronico', 'ingenieria mecanica', 'ingeniero mecanico'], 'Electricidad': ['electricidad'], 'Ingeniería Automotriz': ['automotriz'], 'Ingeniería Civil': ['ingenieria civil'], 'Ingeniería Ambiental': ['ingenieria ambiental', 'gestion ambiental'], 'Telecomunicaciones': ['telecomunicaciones'], 'Minas': ['mineria', 'ingenieria en minas'], 'Arquitectura Sostenible': ['arquitectura', 'arquitecto', 'arquitecta'], 'Medicina': ['medicina', 'medico', 'medica'], 'Enfermería': ['enfermeria', 'enfermero', 'enfermera'], 'Odontología': ['odontologia', 'odontologo', 'odontologa'], 'Laboratorio Clínico': ['laboratorio clinico', 'bioquimica', 'laboratorista'], 'Psicología Clínica': ['psicologia', 'psicologo', 'psicologa'], 'Medicina Veterinaria': ['veterinaria', 'veterinario'], 'Trabajo Social': ['trabajo social'], 'Turismo': ['turismo', 'hoteleria', 'hotelera'], 'Comunicación': ['comunicacion social', 'periodismo'], 'Agronomía': ['agronomia', 'agronomica', 'agronomico'], 'Ingeniería Forestal': ['forestal'], 'Agronegocios': ['agronegocios'], 'Artes Musicales': ['musical', 'musico'], 'Artes Visuales': ['artes visuales', 'diseno grafico', 'diseno de modas'], 'Educación Básica': ['educacion basica'], 'Educación Especial': ['educacion especial'], 'Educación Inicial': ['educacion inicial', 'parvularia'], 'Pedagogía de la Actividad Física y Deporte': ['educacion fisica', 'cultura fisica'], 'Pedagogía de la Lengua y la Literatura': ['lengua y literatura'], 'Pedagogía de los Idiomas Nacionales y Extranjeros': ['pedagogia de los idiomas'], 'Psicopedagogía': ['psicopedagogia']}
for _c, _xs in _EXTRA.items():
    TERMINOS_POR_CARRERA.setdefault(_c, []).extend(_xs)


# ════════════════════════════════════════════════════════════════════════════
# v2 — Afines curados, disciplinas externas y cobertura ampliada por codigo
# ════════════════════════════════════════════════════════════════════════════

# 1) Variantes faltantes de carreras que SI oferta la UNL
_EXTRA2 = {
 "Administración de Empresas": ["talento humano", "recursos humanos",
   "gestion de proyectos", "gestion de procesos"],
 "Contabilidad y Auditoría":   ["nomina", "roles de pago", "costos"],
 "Computación":                ["ciencia de datos", "data scientist", "ingenieria de software"],
 "Comunicación":               ["relaciones publicas", "comunicacion organizacional"],
 "Ingeniería Ambiental":       ["seguridad industrial", "salud ocupacional",
   "seguridad y salud ocupacional", "higiene laboral"],
 "Turismo":                    ["hospitalidad", "agencia de viajes"],
}
for _c, _xs in _EXTRA2.items():
    TERMINOS_POR_CARRERA.setdefault(_c, []).extend(_xs)

# _RE final: se reconstruye una sola vez tras TODAS las extensiones de terminos.
_RE = {car: re.compile(r"\b(?:" + "|".join(re.escape(_norm(x)) for x in terms) + r")\b")
       for car, terms in TERMINOS_POR_CARRERA.items()}

# 2) Cobertura ampliada por codigo CIUO (tecnicos/auxiliares del mismo campo y
#    cargos directivos/profesionales de negocios). Solo codigos profesionalizables;
#    los no profesionales (5xxx ventas/servicios, 4xxx admin. general, 7-8xxx
#    operativos, 9xxx elementales) se omiten a proposito -> quedan sin carrera.
_CIUO_EXTRA = {
 "Contabilidad y Auditoría":   ["4313"],                  # empleados de nomina
 "Finanzas":                   ["3315"],                  # tasadores y valuadores
 "Administración de Empresas": ["1212", "1213", "1223", "1324", "1420", "1439",
                                "2423", "2424", "2433", "2434"],  # direccion, RRHH, marketing y ventas profesionales
 "Administración Pública":     ["1114"],                  # dirigentes de organizaciones de interes
 # OJO: 3257 y 2263 NO se mapean — el NLP los usa como "codigo basurero"
 # (Bouncer, Manicurista, Cocinero terminaban 3257) y el respaldo por codigo
 # contaminaba la carrera. Los cargos SST/ambientales legitimos entran por
 # TEXTO ("seguridad industrial", "salud ocupacional", "gestion ambiental").
 "Derecho":                    ["3411"],                  # profesionales de nivel medio del derecho
 "Trabajo Social":             ["3412"],                  # trabajadores sociales de nivel medio
 "Laboratorio Clínico":        ["3211"],                  # tecnicos en imagenologia y equipo medico
 "Artes Visuales":             ["3432"],                  # decoradores y disenadores
 "Turismo":                    ["3332"],                  # organizadores de eventos y conferencias
 "Electricidad":               ["3113"],                  # tecnicos en ingenieria electrica
 "Electromecánica":            ["3115", "3139"],          # tecnicos mecanicos y de control de procesos
 "Telecomunicaciones":         ["3114"],                  # tecnicos en electronica
 "Ingeniería Civil":           ["3112"],                  # tecnicos en ingenieria civil
 "Arquitectura Sostenible":    ["3118"],                  # delineantes y dibujantes tecnicos
}
for _car, _cods in _CIUO_EXTRA.items():
    CIUO_POR_CARRERA.setdefault(_car, []).extend(_cods)
# Reconstruir el indice inverso codigo -> carreras (deduplicado).
_COD2CAR = {}
for _car, _cods in CIUO_POR_CARRERA.items():
    for _cod in _cods:
        if _car not in _COD2CAR.setdefault(_cod, []):
            _COD2CAR[_cod].append(_car)

# 3) Afines curadas por carrera (clusters cerrados; no se expanden recursivamente)
AFINES_POR_CARRERA = {
 "Agronomía":                 ["Ingeniería Agrícola", "Agronegocios", "Ingeniería Forestal"],
 "Ingeniería Agrícola":       ["Agronomía", "Ingeniería Forestal", "Ingeniería Ambiental"],
 "Ingeniería Ambiental":      ["Ingeniería Forestal", "Ingeniería Agrícola"],
 "Ingeniería Forestal":       ["Ingeniería Ambiental", "Agronomía"],
 "Medicina Veterinaria":      ["Agronomía"],
 "Agronegocios":              ["Administración de Empresas", "Agronomía", "Economía"],
 "Artes Musicales":           [],
 "Artes Visuales":            ["Comunicación"],
 "Comunicación":              ["Artes Visuales"],
 "Educación Básica":          ["Educación Inicial", "Psicopedagogía"],
 "Educación Especial":        ["Psicopedagogía", "Educación Básica", "Psicología Clínica"],
 "Educación Inicial":         ["Educación Básica", "Psicopedagogía"],
 "Pedagogía de la Actividad Física y Deporte": [],
 "Pedagogía de la Lengua y la Literatura": ["Pedagogía de los Idiomas Nacionales y Extranjeros"],
 "Pedagogía de las CC. Experimentales - Informática": ["Computación"],
 "Pedagogía de las CC. Experimentales - Matemáticas y Física": ["Pedagogía de las CC. Experimentales - Química y Biología"],
 "Pedagogía de las CC. Experimentales - Química y Biología": ["Pedagogía de las CC. Experimentales - Matemáticas y Física", "Laboratorio Clínico"],
 "Pedagogía de los Idiomas Nacionales y Extranjeros": ["Pedagogía de la Lengua y la Literatura"],
 "Psicopedagogía":            ["Psicología Clínica", "Educación Especial"],
 "Arquitectura Sostenible":   ["Ingeniería Civil"],
 "Computación":               ["Telecomunicaciones", "Pedagogía de las CC. Experimentales - Informática"],
 "Electricidad":              ["Electromecánica", "Telecomunicaciones"],
 "Electromecánica":           ["Electricidad", "Ingeniería Automotriz"],
 "Ingeniería Automotriz":     ["Electromecánica"],
 "Ingeniería Civil":          ["Arquitectura Sostenible"],   # Minas NO: un ing. civil no ejerce minería (la afinidad inversa Minas->Civil sí se mantiene)
 "Minas":                     ["Ingeniería Civil", "Ingeniería Ambiental"],
 "Telecomunicaciones":        ["Computación", "Electricidad"],
 # "Economía" se saca de las afines de estas 3: cualquier vacante generica de
 # ventas/RRHH/contabilidad/cajero (texto o CIUO amplio) caía en alguna de
 # ellas y arrastraba Economía sin relación real con el puesto (ej. "Contador"
 # o "Cajero Financiero" no piden un economista). La dirección inversa
 # (Economía -> estas 3) sí se mantiene: a quien se le pide explícitamente un
 # economista es razonable sugerirle también empresas/contabilidad/finanzas.
 "Administración de Empresas":["Contabilidad y Auditoría", "Finanzas"],
 "Administración Pública":    ["Administración de Empresas", "Economía", "Derecho"],
 "Contabilidad y Auditoría":  ["Finanzas", "Administración de Empresas"],
 "Derecho":                   ["Administración Pública"],
 "Economía":                  ["Finanzas", "Administración de Empresas", "Contabilidad y Auditoría"],
 "Finanzas":                  ["Contabilidad y Auditoría", "Administración de Empresas"],
 "Trabajo Social":            ["Psicología Clínica", "Psicopedagogía"],
 "Turismo":                   ["Administración de Empresas"],
 "Enfermería":                ["Medicina", "Laboratorio Clínico"],
 "Laboratorio Clínico":       ["Enfermería", "Medicina"],
 "Medicina":                  ["Enfermería", "Laboratorio Clínico"],
 "Odontología":               ["Medicina"],
 "Psicología Clínica":        ["Psicopedagogía", "Trabajo Social"],
}

# 4) Disciplinas que la UNL NO oferta -> carrera(s) UNL mas cercana(s) (afines directas)
EXTERNAS = {
 ("ingenieria industrial", "ingeniero industrial", "ingenieria en procesos",
  "ingenieria de procesos", "ingenieria de produccion"): ["Electromecánica", "Administración de Empresas"],
 ("marketing", "mercadotecnia", "mercadeo", "publicidad"): ["Administración de Empresas"],   # Comunicación UNL = comunicación social/periodismo, no ventas
 ("logistica", "cadena de suministro", "cadena de abastecimiento", "supply chain"): ["Administración de Empresas"],
 ("comercio exterior", "negocios internacionales", "comercio internacional"): ["Administración de Empresas", "Economía"],
 ("gastronomia", "chef", "arte culinario", "cocina profesional"): ["Turismo"],
 ("ingenieria electronica", "ingeniero electronico"): ["Electricidad", "Telecomunicaciones", "Electromecánica"],
 ("ingenieria quimica", "ingeniero quimico"): ["Ingeniería Ambiental"],
 ("nutricion", "nutricionista", "dietetica"): ["Medicina", "Enfermería"],
 ("ingenieria en alimentos", "industria alimentaria", "tecnologia de alimentos"): ["Agronegocios", "Agronomía"],
 ("estadistica", "estadistico"): ["Economía", "Finanzas"],
 ("biotecnologia",): ["Laboratorio Clínico", "Ingeniería Ambiental"],
}
_EXT_RE = []
for _terms, _cars in EXTERNAS.items():
    _EXT_RE.append((re.compile(r"\b(?:" + "|".join(re.escape(_norm(t)) for t in _terms) + r")\b"), _cars))

def match_externas(texto):
    """Carreras UNL afines a una disciplina que la universidad no oferta."""
    t = _norm(texto)
    out = []
    for rx, cars in _EXT_RE:
        if rx.search(t):
            out.extend(cars)
    return out
