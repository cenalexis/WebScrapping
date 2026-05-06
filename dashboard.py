"""
CISE 2026 — Dashboard
Fase 4 del pipeline: visualización de datos de demanda laboral.
Fases 2 y 3 están reservadas (NLP y modelo de ensamble).
"""

import os
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "vacantes_laborales.db"),
)

st.set_page_config(
    page_title="CISE 2026",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS mínimo ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1e1e2e; border-radius: 8px; padding: 16px 20px;
    border-left: 4px solid #7c3aed;
}
.phase-active   { color: #22c55e; font-weight: 700; }
.phase-pending  { color: #eab308; }
.phase-future   { color: #6b7280; }
</style>
""", unsafe_allow_html=True)


# ─── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos():
    if not os.path.exists(DB_PATH):
        return None, None
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM vacantes ORDER BY fecha_extraccion DESC", conn
    )
    conn.close()
    return df, os.path.getsize(DB_PATH)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("CISE 2026")
    st.caption("Análisis de demanda laboral · Ecuador")
    st.divider()

    pagina = st.radio(
        "Navegación",
        ["📊 Resumen general", "🔍 Explorar vacantes",
         "🔬 Fase 2: NLP", "🤖 Fase 3: Modelo", "ℹ️ Pipeline"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("""
**Pipeline**

<span class='phase-active'>✅ Fase 1 — Scraping</span><br>
<span class='phase-pending'>⏳ Fase 2 — NLP</span><br>
<span class='phase-pending'>⏳ Fase 3 — Modelo</span><br>
<span class='phase-pending'>⏳ Fase 4 — Dashboard</span>
""", unsafe_allow_html=True)

    if st.button("🔄 Recargar datos"):
        st.cache_data.clear()
        st.rerun()


# ─── Datos ────────────────────────────────────────────────────────────────────
df, db_size = cargar_datos()

if df is None:
    st.error(f"Base de datos no encontrada en: `{DB_PATH}`")
    st.info("Ejecuta el launcher y haz clic en **Sincronizar y Scrapear** primero.")
    st.stop()

# Conversiones básicas
df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"], errors="coerce")
df["fecha_publicacion"] = pd.to_datetime(df["fecha_publicacion"], errors="coerce")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: Resumen general
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Resumen general":
    st.title("📊 Resumen general")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total vacantes", f"{len(df):,}")
    with col2:
        portales = df["portal_id"].nunique() if "portal_id" in df.columns else "—"
        st.metric("Portales activos", portales)
    with col3:
        ultima = df["fecha_extraccion"].max()
        st.metric("Última extracción", ultima.strftime("%Y-%m-%d") if pd.notna(ultima) else "—")
    with col4:
        st.metric("Tamaño BD", f"{db_size / 1_048_576:.1f} MB")

    st.divider()

    # Vacantes por portal
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Vacantes por portal")
        if "portal_id" in df.columns:
            por_portal = df["portal_id"].value_counts().reset_index()
            por_portal.columns = ["Portal", "Vacantes"]
            st.bar_chart(por_portal.set_index("Portal"))
        else:
            st.info("Campo portal_id no disponible.")

    with col_b:
        st.subheader("Cobertura de campos (%)")
        campos = [
            "cargo_raw", "empresa_raw", "ubicacion_raw", "jornada_raw",
            "contrato_raw", "descripcion_raw", "requisitos_raw",
            "instruccion_raw", "experiencia_anos", "modalidad_raw",
            "salario_min", "vacantes_num",
        ]
        cobertura = []
        for c in campos:
            if c in df.columns:
                pct = df[c].notna().mean() * 100
                if df[c].dtype == object:
                    pct = df[c].replace("", pd.NA).notna().mean() * 100
                cobertura.append({"Campo": c, "Cobertura (%)": round(pct, 1)})
        df_cob = pd.DataFrame(cobertura).sort_values("Cobertura (%)", ascending=False)
        st.dataframe(df_cob, use_container_width=True, hide_index=True)

    # Evolución temporal
    st.subheader("Vacantes extraídas por día")
    if df["fecha_extraccion"].notna().any():
        serie = (df.set_index("fecha_extraccion")
                   .resample("D")
                   .size()
                   .reset_index(name="Vacantes"))
        st.line_chart(serie.set_index("fecha_extraccion"))


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: Explorar vacantes
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🔍 Explorar vacantes":
    st.title("🔍 Explorar vacantes")

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        portales_disp = ["Todos"] + sorted(df["portal_id"].dropna().unique().tolist()) \
            if "portal_id" in df.columns else ["Todos"]
        portal_sel = st.selectbox("Portal", portales_disp)
    with col2:
        busqueda = st.text_input("Buscar en cargo", placeholder="ej. ingeniero, contador...")
    with col3:
        n_filas = st.slider("Filas a mostrar", 10, 500, 50)

    df_filtrado = df.copy()
    if portal_sel != "Todos" and "portal_id" in df.columns:
        df_filtrado = df_filtrado[df_filtrado["portal_id"] == portal_sel]
    if busqueda and "cargo_raw" in df.columns:
        df_filtrado = df_filtrado[
            df_filtrado["cargo_raw"].str.contains(busqueda, case=False, na=False)
        ]

    st.caption(f"{len(df_filtrado):,} vacantes encontradas")

    cols_mostrar = [c for c in
        ["portal_id", "cargo_raw", "empresa_raw", "ubicacion_raw",
         "jornada_raw", "salario_min", "fecha_publicacion"]
        if c in df_filtrado.columns]
    st.dataframe(df_filtrado[cols_mostrar].head(n_filas),
                 use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: Fase 2 — NLP
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🔬 Fase 2: NLP":
    st.title("🔬 Fase 2: Procesamiento NLP")
    st.info("Esta fase está pendiente de implementación.")
    st.markdown("""
**Objetivo:** Normalizar y enriquecer los campos de texto libre.

**Tareas planificadas:**
- Normalización de cargos (ej. "Ing. sistemas" → "Ingeniero en Sistemas")
- Extracción de skills desde `descripcion_raw` y `requisitos_raw`
- Clasificación CIUO-08 (ocupaciones) automática
- Clasificación CIIU (industria) automática
- Limpieza de `ubicacion_raw` → código DPA oficial Ecuador

**Stack propuesto:** `spaCy` + modelo `es_core_news_lg`, fine-tuning con datos propios.
""")

    with st.expander("Vista previa de datos sin normalizar"):
        if "cargo_raw" in df.columns:
            muestra = df["cargo_raw"].dropna().sample(min(20, len(df))).reset_index(drop=True)
            st.dataframe(muestra.rename("cargo_raw"), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: Fase 3 — Modelo
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🤖 Fase 3: Modelo":
    st.title("🤖 Fase 3: Modelo de ensamble")
    st.info("Esta fase está pendiente de implementación.")
    st.markdown("""
**Objetivo:** Imputar campos faltantes usando un modelo supervisado.

**Campos a imputar:**
| Campo | % faltante actual | Método |
|-------|------------------|--------|
| `salario_min` | ~80% | XGBoost regressor |
| `experiencia_anos` | ~30% | XGBoost classifier |
| `instruccion_raw` | ~25% | XGBoost classifier |
| `codigo_ciuo` | 100% | Fine-tuned BERT (Fase 2) |
| `codigo_ciiu` | 100% | Fine-tuned BERT (Fase 2) |

**Stack propuesto:** `scikit-learn` + `XGBoost`, features = cargo normalizado + ubicación + portal.

**Flag de transparencia:** campo `xgb_imputado = True` en todos los registros imputados.
""")

    with st.expander("Campos con mayor porcentaje faltante"):
        campos_num = ["salario_min", "salario_max", "vacantes_num",
                      "experiencia_anos", "instruccion_raw"]
        datos_falt = []
        for c in campos_num:
            if c in df.columns:
                pct = (1 - df[c].replace("", pd.NA).notna().mean()) * 100
                datos_falt.append({"Campo": c, "Faltante (%)": round(pct, 1)})
        if datos_falt:
            st.dataframe(pd.DataFrame(datos_falt).sort_values("Faltante (%)", ascending=False),
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: Pipeline
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "ℹ️ Pipeline":
    st.title("ℹ️ Estado del pipeline")
    st.markdown("""
| Fase | Descripción | Estado |
|------|-------------|--------|
| **1 — Scraping** | Multitrabajos + Computrabajo (24 provincias) | ✅ Producción |
| **2 — NLP** | Normalización cargos, skills, CIUO, CIIU | ⏳ Pendiente |
| **3 — Modelo** | XGBoost para imputar salario, experiencia | ⏳ Pendiente |
| **4 — Dashboard** | Este dashboard (Streamlit) | 🔄 En construcción |

**Automatización:** GitHub Actions corre el scraping diariamente a las 06:00 Ecuador.
**BD maestra:** GitHub Release `latest-data` — [descargar aquí](https://github.com/cenalexis/WebScrapping/releases/tag/latest-data)
""")

    st.subheader("Últimas ejecuciones")
    if "ejecucion_id" in df.columns:
        eje = (df.groupby("ejecucion_id")
                  .agg(vacantes=("hash_id", "count"),
                       portal=("portal_id", "first"),
                       fecha=("fecha_extraccion", "max"))
                  .reset_index()
                  .sort_values("fecha", ascending=False)
                  .head(10))
        st.dataframe(eje, use_container_width=True, hide_index=True)
    else:
        st.info("Tabla de ejecuciones no disponible.")
