# -*- coding: utf-8 -*-
"""
_dashboard_template.py — Plantilla HTML del dashboard CISE 2026 (2 pestañas).
Iconografía: Lucide (licencia ISC, acceso libre) — sin emojis.
El marcador /*__DATA__*/ lo reemplaza generar_dashboard.py con el JSON.
"""

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Demanda Laboral - IDEP | CISE - UNL</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js" onerror="window.__noECharts=true"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js" onerror="window.__noWC=true"></script>
<script src="https://unpkg.com/lucide@latest" onerror="window.__noLucide=true"></script>
<style>
:root{
  --blue-900:#1e3a8a;--blue-700:#1d4ed8;--blue-600:#2563eb;--blue-500:#3b82f6;
  --blue-400:#60a5fa;--blue-300:#93c5fd;--blue-100:#dbeafe;--blue-50:#eff6ff;
  --bg:#f1f5fb;--panel:#fff;--border:#e4e9f2;--ink:#0f2747;--muted:#6b7a99;
  --shadow:0 1px 3px rgba(30,58,138,.06),0 6px 18px rgba(30,58,138,.06);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.4}
svg.lucide{vertical-align:-2px;stroke-width:2}
.app{display:flex;min-height:100vh}
/* Barra lateral: rail institucional claro (logo + identidad), sin filtros */
.sidebar{width:208px;flex:0 0 208px;background:#fff;border-right:1px solid var(--border);color:var(--ink);padding:24px 16px 18px;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
.sb-logo{width:100%;max-width:140px;margin:0 auto 14px;display:block}
.sb-title{font-size:16px;font-weight:800;color:var(--blue-900);text-align:center;letter-spacing:.3px}
.sb-sub{font-size:11px;color:var(--muted);text-align:center;margin-top:3px}
.sb-spacer{flex:1 1 auto;min-height:18px}
.sidebar-foot{font-size:10px;color:var(--muted);line-height:1.6;border-top:1px solid var(--border);padding-top:12px}
/* Barra de filtros superior (antes estaban en la barra lateral) */
.filterbar{display:flex;flex-wrap:wrap;align-items:flex-end;gap:14px;background:#fff;border:1px solid var(--border);border-radius:13px;padding:13px 16px;margin-bottom:16px;box-shadow:var(--shadow)}
.fb-item{display:flex;flex-direction:column;gap:5px}
.fb-item>label{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.fb-item>label svg{color:var(--blue-500);flex:0 0 auto}
.filterbar .csel{min-width:188px;max-width:230px}
.fb-dates{display:flex;gap:6px}
.fb-dates input{padding:7px 9px;border:1px solid var(--border);border-radius:7px;font-size:12px;color:var(--ink);background:#fff;outline:none}
.fb-dates input:focus{box-shadow:0 0 0 2px var(--blue-300);border-color:var(--blue-400)}
.fb-reset{align-self:flex-end;padding:0 14px;height:34px;border:1px solid var(--border);background:var(--blue-50);color:var(--blue-700);border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;display:flex;align-items:center;gap:6px}
.fb-reset:hover{background:var(--blue-100);border-color:var(--blue-300)}
main{flex:1;min-width:0;padding:20px 26px 40px}
.topbar{text-align:center;margin-bottom:16px}
.topbar .title{font-size:22px;font-weight:800;color:var(--blue-900);max-width:940px;margin:0 auto}
.topbar .title small{display:block;font-size:12px;font-weight:500;color:var(--muted);margin-top:3px;line-height:1.4}
/* Pestañas: navegación vertical dentro de la barra lateral */
.tabs{display:flex;flex-direction:column;gap:3px;margin:18px 0 0}
.tab{padding:9px 11px;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;color:var(--muted);transition:all .12s;display:flex;align-items:center;gap:9px}
.tab:hover{background:var(--blue-50);color:var(--blue-700)}
.tab.active{background:var(--blue-600);color:#fff}
.tab.active svg{color:#fff}
.fb-presets{display:flex;gap:5px;margin-top:5px}
.fb-pre{padding:4px 9px;border:1px solid var(--border);background:#fff;color:var(--blue-700);border-radius:7px;cursor:pointer;font-size:10.5px;font-weight:700}
.fb-pre:hover{background:var(--blue-50);border-color:var(--blue-300)}
.panel{display:none}.panel.active{display:block}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--blue-500)}
.kpi .ic{color:var(--blue-500);margin-bottom:8px}
.kpi .val{font-size:25px;font-weight:800;color:var(--blue-900);line-height:1}
.kpi .lbl{font-size:12px;color:var(--muted);margin-top:5px;font-weight:600}
.kpi .extra{font-size:11px;color:var(--blue-600);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);padding:14px 16px;position:relative;min-width:0}
.card h3{font-size:13px;font-weight:700;color:var(--blue-900);margin-bottom:2px;display:flex;align-items:center;gap:7px}
.card h3 svg{color:var(--blue-500)}
.card .csub{font-size:11px;color:var(--muted);margin-bottom:8px}
.col-12{grid-column:span 12}.col-7{grid-column:span 7}.col-6{grid-column:span 6}.col-5{grid-column:span 5}
.chart{width:100%;height:300px}
.note{font-size:11px;color:var(--muted);background:var(--blue-50);border:1px solid var(--blue-100);border-radius:8px;padding:8px 11px;margin-top:8px;display:flex;gap:7px;align-items:flex-start}
.dl-form{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin:12px 0 4px}
.dl-form label{display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:600;color:#475569}
.dl-sel{min-width:220px;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-size:13px;color:#1e293b}
.dl-btn{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer}
.dl-btn:hover{background:#1d4ed8}
.dl-vars{margin-top:10px}
.dl-vars summary{font-size:12px;color:#2563eb;cursor:pointer;font-weight:600}
.dl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px 18px;margin:10px 0 4px;font-size:12px;color:#475569}
.dl-grid b{color:#1e293b;font-weight:600;margin-right:5px}
.dl-nota{font-size:11px;color:#94a3b8;margin-top:8px}
.note svg{color:var(--blue-600);flex:0 0 auto;margin-top:1px}
.locked{position:absolute;inset:0;background:rgba(241,245,251,.9);border-radius:12px;display:none;align-items:center;justify-content:center;text-align:center;color:var(--muted);font-size:12px;padding:20px;z-index:5;gap:5px}
.locked b{color:var(--blue-700)}
.treebar{display:flex;align-items:center;gap:10px;margin:6px 0 2px;flex-wrap:wrap}
.treebar label{font-size:11px;color:var(--muted);font-weight:600}
.treebar select{min-width:200px;max-width:300px;padding:7px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--ink);font-size:13px;outline:none}
.ocsel{position:relative;display:inline-block;min-width:330px;max-width:480px;vertical-align:middle}
.ocsel-input{width:100%;padding:7px 11px;border:1px solid var(--border);border-radius:7px;font-size:13px;outline:none;background:#fff;color:var(--ink)}
.ocsel-input:focus{box-shadow:0 0 0 2px var(--blue-300);border-color:var(--blue-400)}
.ocsel-menu{display:none;position:absolute;z-index:40;left:0;right:0;top:calc(100% + 4px);max-height:320px;overflow:auto;background:#fff;border:1px solid var(--border);border-radius:9px;box-shadow:0 12px 30px rgba(30,58,138,.20);padding:5px}
.ocsel.open .ocsel-menu{display:block}
.ocsel-opt{padding:8px 10px;border-radius:6px;cursor:pointer;font-size:12.5px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ocsel-opt:hover{background:var(--blue-50)}
.ocsel-empty{padding:9px 10px;color:var(--muted);font-size:12px}
.page-foot{display:none;margin-top:30px;padding:20px 4px 8px;border-top:1px solid var(--border);color:var(--muted);font-size:11.5px;line-height:1.65}
.page-foot b{color:var(--blue-800);font-weight:700}
.page-foot p{max-width:1120px;margin-bottom:8px}
.page-foot .foot-cred{font-weight:700;color:var(--blue-700)}
.about{max-width:840px;background:#fff;border:1px solid var(--border);border-radius:14px;padding:30px 36px;box-shadow:var(--shadow);line-height:1.7}
.about-h{font-size:23px;font-weight:800;color:var(--blue-900);margin-bottom:8px}
.about-lead{font-size:14.5px;color:var(--ink);margin-bottom:6px}
.about-sh{font-size:13px;font-weight:700;color:var(--blue-700);text-transform:uppercase;letter-spacing:.6px;margin:22px 0 8px}
.about-steps{margin:0;padding-left:20px}
.about-steps li{margin-bottom:10px;font-size:13.5px;color:var(--ink)}
.about p{font-size:13.5px;color:var(--ink);margin-bottom:10px}
.about-note{font-size:12.5px;color:var(--muted);border-left:3px solid var(--blue-300);padding-left:13px;margin-top:16px}
.about-cred{margin-top:20px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;font-weight:700;color:var(--blue-700)}
.soc-tag{font-size:11px;font-weight:700;color:var(--blue-700);background:var(--blue-50);border:1px solid var(--blue-100);padding:4px 10px;border-radius:20px}
/* Pestaña Actividades — estilo "agenda infografica" (paleta clara) */
.tk-agenda{display:grid;grid-template-columns:288px 1fr;gap:24px;margin-top:14px}
@media(max-width:940px){.tk-agenda{grid-template-columns:1fr}}
.tk-hero{position:sticky;top:14px;align-self:start;background:linear-gradient(165deg,#fff,var(--blue-50));border:1px solid var(--blue-100);border-radius:18px;padding:26px 22px;text-align:center;box-shadow:var(--shadow)}
.tk-frame{position:relative;width:152px;height:152px;margin:0 auto 18px;display:flex;align-items:center;justify-content:center}
.tk-frame .c{position:absolute;width:32px;height:32px;border:3px solid var(--blue-400)}
.tk-frame .c1{top:0;left:0;border-right:0;border-bottom:0;border-radius:9px 0 0 0}
.tk-frame .c2{top:0;right:0;border-left:0;border-bottom:0;border-radius:0 9px 0 0}
.tk-frame .c3{bottom:0;left:0;border-right:0;border-top:0;border-radius:0 0 0 9px}
.tk-frame .c4{bottom:0;right:0;border-left:0;border-top:0;border-radius:0 0 9px 0}
.tk-bigicon{width:112px;height:112px;border-radius:50%;background:#fff;border:2px solid var(--blue-100);display:flex;align-items:center;justify-content:center;box-shadow:0 10px 26px rgba(37,99,235,.16)}
.tk-bigicon svg{width:56px;height:56px;color:var(--blue-600)}
.tk-title{font-size:11px;font-weight:800;letter-spacing:2.5px;color:var(--blue-600);text-transform:uppercase}
.tk-occname{font-size:17px;font-weight:800;color:var(--blue-900);margin:7px 0 12px;line-height:1.25}
.tk-soc-pill{display:inline-block;background:var(--blue-600);color:#fff;font-size:11px;font-weight:700;padding:6px 18px;border-radius:20px;letter-spacing:.5px}
.tk-counts{display:flex;gap:10px;justify-content:center;margin-top:18px}
.tk-cchip{background:#fff;border:1px solid var(--blue-100);border-radius:12px;padding:9px 16px}
.tk-cchip b{display:block;font-size:21px;font-weight:800;color:var(--blue-700);line-height:1}
.tk-cchip span{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.tk-timeline{display:grid;grid-template-columns:1fr 1fr;gap:0 28px}
@media(max-width:1280px){.tk-timeline{grid-template-columns:1fr}}
.tl-col{position:relative;padding-left:32px}
.tl-col::before{content:"";position:absolute;left:10px;top:16px;bottom:16px;border-left:2px dashed var(--blue-200)}
.tl-item{position:relative;margin-bottom:16px}
.tl-badge{position:absolute;left:-32px;top:7px;width:23px;height:23px;border-radius:50%;background:var(--c);color:#fff;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 4px var(--bg)}
.tl-card{background:#fff;border:1px solid var(--border);border-left:4px solid var(--c);border-radius:13px;padding:12px 15px;box-shadow:var(--shadow);transition:transform .12s,box-shadow .12s}
.tl-card:hover{transform:translateY(-2px);box-shadow:0 9px 22px rgba(30,58,138,.14)}
.tl-pill{display:inline-flex;align-items:center;gap:6px;background:var(--c);color:#fff;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;margin-bottom:9px;letter-spacing:.3px}
.tl-pill svg{width:13px;height:13px}
.tl-text{font-size:12.5px;color:var(--ink);line-height:1.45}
.seclegend{margin-top:2px}
.sleg-grid{display:flex;flex-direction:column;gap:6px;min-height:156px}
.sleg-item{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--ink)}
.sdot{width:11px;height:11px;border-radius:3px;flex:0 0 auto}
.sleg-item svg{color:var(--blue-500);flex:0 0 auto}
.sname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.spct{font-weight:700;color:var(--blue-700);flex:0 0 auto}
.sleg-nav{display:flex;align-items:center;justify-content:center;gap:14px;margin-top:8px;font-size:11px;color:var(--muted);font-weight:600}
.sleg-btn{border:1px solid var(--border);background:#fff;border-radius:6px;cursor:pointer;padding:3px 7px;display:flex;align-items:center;color:var(--blue-600)}
.sleg-btn:hover{background:var(--blue-50);border-color:var(--blue-300)}
.skq{border-bottom:1px dashed #94a3b8;cursor:help}
#tip{position:fixed;z-index:60;max-width:330px;background:#0f2747;color:#fff;font-size:12px;line-height:1.45;padding:9px 12px;border-radius:8px;box-shadow:0 8px 26px rgba(15,39,71,.28);pointer-events:none;display:none}
#tip .tip-h{color:#bfdbfe;display:block;margin-bottom:3px}
@media(max-width:1100px){.col-7,.col-6,.col-5{grid-column:span 12}}
.tbl-wrap{max-height:360px;overflow:auto;border-radius:8px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
thead th{position:sticky;top:0;background:var(--blue-600);color:#fff;text-align:left;padding:9px 11px;font-weight:600;white-space:nowrap}
tbody td{padding:8px 11px;border-bottom:1px solid #eef2f8}
tbody tr:nth-child(even){background:#f8fafd}
tbody tr:hover{background:var(--blue-50)}
.pill{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:var(--blue-50);color:var(--blue-700);border:1px solid var(--blue-100)}
.cellic{display:inline-flex;align-items:center;gap:5px}.cellic svg{color:var(--blue-500)}
.cloud{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:8px 18px;padding:26px 18px;line-height:1}
.cw{font-weight:800;cursor:default;transition:opacity .15s}.cw:hover{opacity:.55}
.onet-toggle{display:inline-flex;background:var(--blue-50);border:1px solid var(--blue-100);border-radius:8px;padding:3px;margin-bottom:14px;gap:3px}
.onet-btn{border:none;background:transparent;padding:7px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;color:var(--muted)}
.onet-btn.active{background:var(--blue-600);color:#fff}
.banner{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;padding:12px 16px;border-radius:10px;margin-bottom:16px;font-size:13px;display:none}
/* Dropdowns personalizados con icono por opción */
.csel{position:relative;font-size:13px}
.csel-btn{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--ink);cursor:pointer;font-size:13px;text-align:left}
.csel-cur{display:flex;align-items:center;gap:8px;overflow:hidden;white-space:nowrap}
.csel-cur span{overflow:hidden;text-overflow:ellipsis}
.csel-btn>i{color:var(--blue-600);flex:0 0 auto}
.csel-cur i{color:var(--blue-600);flex:0 0 auto}
.csel-menu{display:none;position:absolute;z-index:30;left:0;right:0;top:calc(100% + 4px);max-height:300px;overflow:auto;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 10px 28px rgba(30,58,138,.20);padding:4px}
.csel.open .csel-menu{display:block}
.csel.open .csel-btn{box-shadow:0 0 0 2px var(--blue-300)}
.csel.filtered .csel-btn{border-color:var(--blue-500);background:var(--blue-50)}
.csel.filtered .csel-cur>span{color:var(--blue-700);font-weight:600}
.csel.filtered .csel-cur i{color:var(--blue-600)}
.csel-item{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:6px;cursor:pointer;color:var(--ink);white-space:nowrap;overflow:hidden}
.csel-search{width:100%;box-sizing:border-box;padding:7px 9px;margin-bottom:4px;border:1px solid var(--border);border-radius:6px;font-size:12px;color:var(--ink);outline:none;position:sticky;top:0;background:#fff}
.csel-search:focus{border-color:var(--blue-500)}
.csel-item:hover{background:var(--blue-50)}
.csel-item.sel{background:var(--blue-100);font-weight:600}
.csel-item i{color:var(--blue-600);flex:0 0 auto}
.csel-item span{overflow:hidden;text-overflow:ellipsis}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <img class="sb-logo" src="__LOGO__" alt="CISE — Universidad Nacional de Loja"/>
    <div class="sb-title">Proyecto de Demanda Laboral</div>
    <div class="sb-sub">Módulo de Demanda Laboral (OE3)</div>
    <nav class="tabs">
      <div class="tab active" data-tab="general"><i data-lucide="layout-dashboard" width="16" height="16"></i> Panorama general</div>
      <div class="tab" data-tab="skills"><i data-lucide="brain" width="16" height="16"></i> O*NET</div>
      <div class="tab" data-tab="soft"><i data-lucide="messages-square" width="16" height="16"></i> Habilidades blandas</div>
      <div class="tab" data-tab="tech"><i data-lucide="terminal" width="16" height="16"></i> Habilidades técnicas</div>
      <div class="tab" data-tab="carreras"><i data-lucide="graduation-cap" width="16" height="16"></i> Carreras</div>
      
      <div class="tab" data-tab="about"><i data-lucide="info" width="16" height="16"></i> Conoce el proyecto</div>
    </nav>
    <div class="sb-spacer"></div>
    <div class="sidebar-foot"></div>
  </aside>
  <main>
    <div class="topbar">
      <div class="title">Demanda Laboral<small>Universidad Nacional de Loja · CISE</small></div>
    </div>
    <div class="filterbar" id="filterbar">
      <div class="fb-item" id="wrap-fecha"><label><i data-lucide="calendar-days" width="13" height="13"></i> Fechas</label>
        <div class="fb-dates"><input id="f-desde" type="date"/><input id="f-hasta" type="date"/></div>
        <div class="fb-presets"><button class="fb-pre" data-m="1">1 mes</button><button class="fb-pre" data-m="3">3 meses</button><button class="fb-pre" data-m="6">6 meses</button><button class="fb-pre" data-m="0">Todo</button></div></div>
      <div class="fb-item"><label><i data-lucide="layers" width="13" height="13"></i> Macrosector</label><div class="csel" id="cs-macro"></div></div>
      <div class="fb-item"><label><i data-lucide="factory" width="13" height="13"></i> Sector (CIIU)</label><div class="csel" id="cs-sector"></div></div>
      <div class="fb-item"><label><i data-lucide="users" width="13" height="13"></i> Ocupación (CIUO)</label><div class="csel" id="cs-grupo"></div></div>
      <div class="fb-item" id="wrap-ciudad"><label><i data-lucide="map-pin" width="13" height="13"></i> Ciudad</label><div class="csel" id="cs-ciudad"></div></div>
      <button class="fb-reset" id="btn-reset"><i data-lucide="rotate-ccw" width="14" height="14"></i> Limpiar</button>
    </div>
    <div class="banner" id="banner-echarts">No se pudieron cargar los gráficos (requiere conexión la primera vez). KPIs y tablas funcionan igual.</div>

    <section class="panel" id="panel-soft"><div class="kpis" id="kpis-soft"></div><div class="grid"><div class="card col-7"><h3><i data-lucide="messages-square" width="16" height="16"></i> ¿Qué habilidades blandas pide el mercado?</h3><div class="csub" id="soft-narr">—</div><div class="chart" id="cloud" style="height:360px"></div></div><div class="card col-5"><h3><i data-lucide="bar-chart-3" width="16" height="16"></i> Ranking de habilidades blandas</h3><div class="csub">Porcentaje de anuncios que la mencionan</div><div class="chart" id="soft-bar" style="height:360px"></div></div><div class="card col-12"><div class="note"><i data-lucide="info" width="14" height="14"></i><span>Competencias extraídas por diccionario de palabras clave sobre el texto de los anuncios; se filtró ruido. Reflejan frecuencia de mención, no importancia relativa. La taxonomía formal O*NET está en la pestaña anterior.</span></div></div></div></section>

    <section class="panel" id="panel-tech"><div id="tech-locked" class="banner" style="display:none">No hay habilidades técnicas extraídas. Ejecuta <b>python Codes/remina_tecnicas.py</b> y regenera.</div><div class="kpis" id="kpis-tech"></div><div class="grid"><div class="card col-5"><h3><i data-lucide="bar-chart-3" width="16" height="16"></i> Herramientas más solicitadas</h3><div class="csub">Porcentaje de anuncios que mencionan cada herramienta o tecnología</div><div class="chart" id="tech-bar" style="height:520px"></div></div><div class="card col-7"><h3><i data-lucide="scatter-chart" width="16" height="16"></i> ¿Qué herramientas se piden y en cuántos oficios?</h3><div class="csub">Cada punto es una herramienta: cuanto más a la derecha, más anuncios la piden; cuanto más arriba, en más ocupaciones distintas aparece. Arriba-derecha: transversales y muy pedidas; abajo-derecha: muy pedidas pero de nicho.</div><div class="chart" id="tech-scatter" style="height:520px"></div></div></div></section>

    <section class="panel" id="panel-carreras"><div class="kpis" id="kpis-car"></div><div class="grid"><div class="card col-12"><h3><i data-lucide="graduation-cap" width="16" height="16"></i> Demanda por carrera</h3><div class="csub">Puestos de trabajo que encajan con cada carrera de la UNL. Un mismo anuncio puede contar para varias carreras afines.</div><div class="chart" id="car-bar" style="height:600px"></div><div class="note"><i data-lucide="info" width="14" height="14"></i><span>Un mismo anuncio puede contar para varias carreras afines (por ejemplo, un puesto en banca sirve a Economía, Finanzas y Contabilidad). En el total general cada anuncio se cuenta una sola vez.</span></div></div><div class="card col-12"><h3><i data-lucide="trending-up" width="16" height="16"></i> Evolución de anuncios por carrera</h3><div class="csub">Cuántos anuncios aparecieron cada semana o cada mes para la carrera elegida</div><div class="treebar" style="flex-wrap:wrap;gap:6px 10px"><label>Carrera:</label><select id="evol-car" onchange="_evolCar=this.value;renderCarreras();"><option value="">Total (cualquier carrera)</option></select><span style="display:inline-flex;align-items:center;gap:4px"><label>Periodo:</label><button class="onet-btn active" data-ep="all" onclick="setEvolPer('all')">Todo</button><button class="onet-btn" data-ep="6m" onclick="setEvolPer('6m')">6&nbsp;meses</button><button class="onet-btn" data-ep="3m" onclick="setEvolPer('3m')">3&nbsp;meses</button><button class="onet-btn" data-ep="4w" onclick="setEvolPer('4w')">4&nbsp;sem</button></span><span style="display:inline-flex;align-items:center;gap:4px"><label>Ver por:</label><button class="onet-btn" data-eg="month" onclick="setEvolGran('month')">Mes</button><button class="onet-btn active" data-eg="week" onclick="setEvolGran('week')">Semana</button></span><span style="display:inline-flex;align-items:center;gap:4px"><label>Escala:</label><button class="onet-btn active" data-em="abs" onclick="setEvol(false)">Absoluto</button><button class="onet-btn" data-em="rel" onclick="setEvol(true)">Relativo %</button></span></div><div class="chart" id="car-evol" style="height:320px"></div></div><div class="card col-12"><h3><i data-lucide="database" width="16" height="16"></i> Descarga de datos</h3><div class="csub">Base de demanda por carrera en formato CSV, lista para abrir en Excel.</div><div class="dl-form"><label>Carrera<select id="dl-carrera" class="dl-sel"><option value="">Todas las carreras</option></select></label><label>Periodo<select id="dl-mes" class="dl-sel"><option value="">Todo el periodo</option></select></label><button class="dl-btn" onclick="descargarCarrerasCSV()"><i data-lucide="download" width="15" height="15" style="vertical-align:-3px"></i> Descargar CSV</button></div><details class="dl-vars"><summary>Ver las 18 variables incluidas</summary><div class="dl-grid"><div><b>vacante_id</b> identificador del anuncio</div><div><b>fecha</b> día en que se captó el anuncio</div><div><b>semana</b> lunes de la semana correspondiente</div><div><b>mes</b> mes calendario</div><div><b>carrera</b> carrera de la UNL</div><div><b>facultad</b> facultad a la que pertenece</div><div><b>plazas</b> puestos que pide el anuncio</div><div><b>ciudad</b> ciudad del puesto</div><div><b>provincia</b> provincia del puesto</div><div><b>ciuo_codigo</b> código de ocupación CIUO-08</div><div><b>ocupacion</b> nombre de la ocupación</div><div><b>salario_min</b> salario mínimo ofrecido (USD)</div><div><b>salario_max</b> salario máximo ofrecido (USD)</div><div><b>experiencia_anos</b> años de experiencia pedidos</div><div><b>requiere_posgrado</b> 1 si exige maestría o posgrado</div><div><b>sector_publico</b> empleador público o privado</div><div><b>cargo</b> título original del anuncio</div><div><b>palabras_clave</b> contexto del anuncio (key_words)</div></div><div class="dl-nota">La descarga también respeta los filtros aplicados en la parte superior del tablero.</div></details></div><div class="card col-12" id="car-tabla-card" style="display:none"><h3><i data-lucide="list" width="16" height="16"></i> <span id="car-tabla-title">Anuncios</span></h3><div class="csub" id="car-tabla-sub"></div><div class="tbl-wrap" style="max-height:440px;overflow-y:auto"><table id="car-tbl"><thead><tr><th>Cargo</th><th>Empresa</th><th>Ciudad</th><th>Fecha</th><th>Ocupación (CIUO)</th><th>Palabras clave</th></tr></thead><tbody id="car-tbl-body"></tbody></table></div><div class="note"><i data-lucide="info" width="14" height="14"></i><span>Anuncios del periodo seleccionado cuyo perfil califica para la carrera. Clic en "Todo" en el selector de periodo para ver el histórico completo.</span></div></div></div></section>

    <section class="panel active" id="panel-general">
      <div class="kpis" id="kpis-gen"></div>
      <div class="grid">
        <div class="card col-7"><h3><i data-lucide="target" width="16" height="16"></i> Las 15 ocupaciones más solicitadas</h3><div class="csub">Porcentaje del total de anuncios. Deslice la barra para ver los nombres completos.</div><div style="overflow-x:auto;overflow-y:hidden"><div class="chart" id="c-ocup" style="height:400px;min-width:1030px"></div></div></div>
        <div class="card col-5"><h3><i data-lucide="factory" width="16" height="16"></i> Distribución por sector económico</h3><div class="csub">Porcentaje de anuncios en cada rama de actividad económica</div><div class="chart" id="c-sector" style="height:230px"></div><div id="sec-leg" class="seclegend"></div></div>
        <div class="card col-6"><h3><i data-lucide="map" width="16" height="16"></i> Anuncios por provincia</h3><div class="csub">Haga clic en una provincia para filtrar todo el tablero</div><div class="chart" id="c-mapa" style="height:420px"></div><div class="locked" id="lock-mapa"></div></div>
        <div class="card col-6"><h3><i data-lucide="map-pin" width="16" height="16"></i> Anuncios por ciudad</h3><div class="csub">Las 12 ciudades con más anuncios de empleo</div><div class="chart" id="c-ciudad" style="height:420px"></div><div class="locked" id="lock-ciudad"></div></div>
      </div>
    </section>

    <section class="panel" id="panel-skills"><div class="onet-toggle"><button class="onet-btn active" data-v="skills" onclick="onetView('skills')">Habilidades</button><button class="onet-btn" data-v="tasks" onclick="onetView('tasks')">Tareas</button></div>
      <div id="skills-locked" class="banner" style="display:none">No hay competencias O*NET cargadas. Ejecuta <b>cargar_onet.py</b> y regenera. (vacantes.codigo_soc → onet_skills_scores → onet_skills_catalog)</div>
      <div class="kpis" id="kpis-sk"></div>
      <div class="grid">
        <div class="card col-12"><h3><i data-lucide="share-2" width="16" height="16"></i> Perfil de competencias por ocupación</h3>
          <div class="treebar"><label>Grupo</label><select id="tree-grp"></select><label>Ocupación</label><div id="tree-sel"></div><span class="soc-tag" id="tree-soc"></span></div>
          <div class="chart" id="s-tree" style="height:440px"></div><div class="locked" id="lock-tree"></div></div>
        <div class="card col-7"><h3><i data-lucide="flame" width="16" height="16"></i> Competencias más solicitadas</h3><div class="csub">Cuántos anuncios corresponden a ocupaciones que requieren cada competencia</div><div class="chart" id="s-top"></div></div>
        <div class="card col-5"><h3><i data-lucide="layers" width="16" height="16"></i> Por familia de competencia</h3><div class="csub">Las 35 competencias, agrupadas por familia</div><div class="chart" id="s-fam"></div></div>
        <div class="card col-7"><h3><i data-lucide="puzzle" width="16" height="16"></i> Competencia líder por grupo ocupacional</h3><div class="csub">La competencia más pedida en cada grupo de ocupaciones</div><div class="chart" id="s-ocup"></div></div>
        <div class="card col-5"><h3><i data-lucide="gem" width="16" height="16"></i> Competencias menos frecuentes</h3><div class="csub">Las que casi no aparecen en los anuncios</div><div class="chart" id="s-rara"></div>
          <div class="note"><i data-lucide="info" width="14" height="14"></i><span>Baja frecuencia no implica baja demanda: puede ser una competencia de nicho (propia de pocas ocupaciones) más que poco valorada. Interpretar con cautela.</span></div></div>
        <div class="card col-12"><h3><i data-lucide="list-checks" width="16" height="16"></i> Detalle de competencias O*NET</h3><div class="csub" id="sk-count"></div>
          <div class="tbl-wrap"><table id="sk-tbl"><thead><tr><th>Competencia</th><th>Familia O*NET</th><th>Anuncios</th><th>% del total</th><th>Ocupación líder</th></tr></thead><tbody id="sk-body"></tbody></table></div></div>
      </div>
    </section>

    <section class="panel" id="panel-tasks"><div class="onet-toggle"><button class="onet-btn active" data-v="skills" onclick="onetView('skills')">Habilidades</button><button class="onet-btn" data-v="tasks" onclick="onetView('tasks')">Tareas</button></div>
      <div id="tasks-locked" class="banner" style="display:none">Aún no hay tareas O*NET traducidas. Ejecuta <b>python Codes/_build_tasks_es.py</b> y regenera el dashboard.</div>
      <div class="grid">
        <div class="card col-12"><h3><i data-lucide="list-todo" width="16" height="16"></i> Actividades y tareas del puesto</h3>
          <div class="treebar"><label>Grupo</label><select id="tk-grp"></select><label>Ocupación</label><div id="tk-sel"></div><span class="soc-tag" id="tk-soc"></span></div>
          <div id="tk-list"></div></div>
      </div>
    </section>

    <section class="panel" id="panel-about">
      <div class="about">
        <h2 class="about-h">Conoce el proyecto</h2>
        <p class="about-lead">Este tablero es parte del proyecto de demanda laboral de la Universidad Nacional de Loja, que estudia la demanda de trabajo en el país para orientar la actualización de su oferta de grado y posgrado. Reúne en un solo lugar qué ocupaciones, sectores y competencias está pidiendo el mercado laboral.</p>
        <h3 class="about-sh">Cómo se construye</h3>
        <ol class="about-steps">
          <li>Recopilación. Se recogen anuncios de empleo publicados en portales web del Ecuador.</li>
          <li>Clasificación. A cada anuncio se le asigna, mediante procesamiento de lenguaje natural, un código de ocupación CIUO-08 y un código SOC, además del sector económico (CIIU) de la empresa.</li>
          <li>Enriquecimiento. El código SOC conecta cada ocupación con las competencias y las tareas o actividades que normalmente exige ese trabajo, según la base internacional O*NET.</li>
          <li>Análisis. Toda esa información se agrega aquí para ver dónde se concentra la demanda: por ocupación, sector, territorio y habilidades.</li>
        </ol>
        <h3 class="about-sh">Alcance y actualización</h3>
        <p>La base maestra se actualiza de forma semestral y cubre la demanda a nivel nacional, regional (Zona 7) y local (Loja). Sus resultados alimentan el cálculo del Índice de Demanda y Empleabilidad Potencial (IDEP).</p>
        <p class="about-note">Los datos provienen de una muestra de anuncios; por eso las cifras deben leerse como proporciones y tendencias, no como totales del mercado laboral.</p>
        <p class="about-cred">Centro de Investigación · Universidad Nacional de Loja</p>
      </div>
    </section>

    <footer class="page-foot" id="page-foot">
      <p>Fuentes y metodología. Las ocupaciones se clasifican según la CIUO-08 (Clasificación Internacional Uniforme de Ocupaciones) y los sectores económicos según la CIIU Rev.4. Las competencias y las actividades de cada puesto provienen de la base O*NET del Departamento de Trabajo de los Estados Unidos, enlazadas a cada ocupación a través de su código SOC y traducidas al español. Dentro de cada ocupación, las actividades marcadas como esenciales son las centrales del puesto y las complementarias son secundarias o de apoyo. Los datos de demanda se obtienen de anuncios de empleo publicados en portales de Ecuador, por lo que las proporciones reflejan tendencias de una muestra y deben interpretarse como tales. La base de datos maestra se actualiza semestralmente, cubriendo la demanda a nivel nacional, regional (Zona 7) y local (Loja), y sirve como insumo para el cálculo del Índice de Demanda y Empleabilidad Potencial (IDEP).</p>
      <p class="foot-cred">CISE · Universidad Nacional de Loja</p>
    </footer>
  </main>
</div>

<script>
const DATA = /*__DATA__*/;
const GEO  = /*__GEOJSON__*/;
const PALETTE=["#1d4ed8","#2563eb","#3b82f6","#60a5fa","#93c5fd","#1e40af","#38bdf8","#0ea5e9","#7dd3fc","#1e3a8a","#bfdbfe","#0284c7"];
/* ============================================================================
   MAPA DEL CODIGO DEL DASHBOARD  (referencia para mantenimiento)
   ----------------------------------------------------------------------------
   DATA            objeto con todos los datos, incrustado al generar el HTML.
   applyFilters()  aplica los filtros de la barra lateral a DATA.rows.

   PESTANA 1 — Panorama general   (renderGeneral)
     kpisGen     tarjetas KPI (anuncios, vacantes, sectores, ocupaciones)
     chOcup      barras  -> Top 15 ocupaciones mas demandadas (CIUO)
     chSector    dona    -> distribucion por sector economico (CIIU)
     chTiempo    linea   -> tendencia por fecha de extraccion
     chCiudad    barras  -> anuncios por ciudad
     chMapa      mapa    -> anuncios por provincia (choropleth Ecuador)
     tablaGen    tabla   -> explorador de anuncios

   PESTANA 2 — Habilidades (O*NET)   (renderSkills)
     skTop       barras  -> competencias O*NET mas requeridas
     skFamilia   dona    -> reparto por familia de competencia
     skOcup      barras  -> competencia lider por grupo ocupacional
     skRara      barras  -> competencias menos frecuentes (nicho)

   PESTANA 3 — Habilidades blandas   (renderSoft)
     nube (wordCloud)    -> competencias blandas, tamano = frecuencia
     soft-bar (barras)   -> ranking de habilidades blandas
   ============================================================================ */

const state={search:"",macro:"",sector:"",grupo:"",ciudad:"",provincia:"",desde:"",hasta:""};
const charts={};let activeTab="general",CUR=[];
// CIIU sección -> macrosector económico (Primario/Secundario/Terciario)
const MACRO={A:"P",B:"P",C:"S",D:"S",E:"S",F:"S",G:"T",H:"T",I:"T",J:"T",K:"T",L:"T",M:"T",N:"T",O:"T",P:"T",Q:"T",R:"T",S:"T",T:"T",U:"T"};
const macroOf=s=>MACRO[s]||"";

const ciuoDesc=c=>DATA.ciuoMap[c]||c||"—";
const secName=s=>(DATA.ciiuSec[s]||{}).name||"Sin clasificar";
const secLic=s=>(DATA.ciiuSec[s]||{}).icon||"circle";
const grpName=g=>(DATA.ciuoMajor[g]||{}).name||"Sin clasificar";
const grpLic=g=>(DATA.ciuoMajor[g]||{}).icon||"circle";
const skName=i=>DATA.skillVocab[i]||"—";
const skFam=i=>DATA.skillFam[i]||"Otra";
const lic=(n,s,col)=>`<i data-lucide="${n}" width="${s||15}" height="${s||15}"${col?` style="color:${col}"`:""}></i>`;
function drawIcons(){if(window.lucide&&!window.__noLucide)lucide.createIcons();}
function countBy(a,k){const m={};for(const r of a){const v=k(r);if(v==null||v==="")continue;m[v]=(m[v]||0)+1;}return m;}
function topN(o,n){return Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,n);}
function botN(o,n){return Object.entries(o).sort((a,b)=>a[1]-b[1]).slice(0,n);}
// Relativos: % sobre el total de anuncios (muestras pequeñas -> proporciones, no brutos)
const _pct=(v,t)=>t?(v/t*100):0;
const pctTxt=(v,t)=>_pct(v,t).toFixed(1)+"%";

function applyFilters(skipProv){const q=state.search.toLowerCase();
  return DATA.rows.filter(r=>{
    if(q&&!(r.c||"").toLowerCase().includes(q))return false;
    if(state.macro&&macroOf(r.is)!==state.macro)return false;
    if(state.sector&&r.is!==state.sector)return false;
    if(state.grupo&&r.o!==state.grupo)return false;
    if(state.ciudad&&r.tp!==state.ciudad)return false;
    if(!skipProv&&state.provincia&&r.pv!==state.provincia)return false;
    if(state.desde&&(!r.dt||r.dt<state.desde))return false;
    if(state.hasta&&(!r.dt||r.dt>state.hasta))return false;
    return true;});}
function ec(id){if(window.__noECharts)return null;const _e=document.getElementById(id);if(!_e)return null;if(!charts[id])charts[id]=echarts.init(_e);return charts[id];}
const baseGrid={left:8,right:18,bottom:8,top:18,containLabel:true};
const ax={axisLine:{lineStyle:{color:"#cbd5e1"}},axisLabel:{color:"#475569"},splitLine:{lineStyle:{color:"#eef2f8"}}};
const gH=(a,b)=>new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:a},{offset:1,color:b}]);
const gV=(a,b)=>new echarts.graphic.LinearGradient(0,1,0,0,[{offset:0,color:a},{offset:1,color:b}]);

/* General KPIs */
function kpisGen(rows){
  const sec=new Set(rows.map(r=>r.is).filter(Boolean)),ocu=new Set(rows.map(r=>r.o).filter(Boolean));
  const st=topN(countBy(rows,r=>r.is),1)[0],gt=topN(countBy(rows,r=>r.og),1)[0];
  const cards=[
    {ic:"bar-chart-3",val:rows.length.toLocaleString("es"),lbl:"Anuncios de empleo",extra:"publicaciones de empleo"},
    {ic:"briefcase",val:rows.reduce((a,r)=>a+(r.vn||1),0).toLocaleString("es"),lbl:"Vacantes (puestos)",extra:"total de plazas anunciadas"},
    {ic:"factory",val:sec.size,lbl:"Sectores económicos",eic:st?secLic(st[0]):"",extra:st?secName(st[0]):""},
    {ic:"users",val:ocu.size,lbl:"Ocupaciones distintas",eic:gt?grpLic(gt[0]):"",extra:gt?grpName(gt[0]):""},
  ];
  if(DATA.flags.experiencia){const ex=rows.map(r=>r.ex).filter(v=>v!=null);const avg=ex.length?ex.reduce((a,b)=>a+b,0)/ex.length:null;
    cards.push({ic:"history",val:avg!=null?(avg.toFixed(1).replace(".",",")+" años"):"—",lbl:"Experiencia media requerida"});}
  document.getElementById("kpis-gen").innerHTML=cards.map(c=>
    `<div class="kpi"><div class="ic">${lic(c.ic,22)}</div><div class="val">${c.val}</div><div class="lbl">${c.lbl}</div>${c.extra?`<div class="extra">${c.eic?lic(c.eic,12):""}${c.extra}</div>`:""}</div>`).join("");
}
function chTop(rows){const c=ec("c-top");if(!c)return;const bc=countBy(rows,r=>r.c);const t=topN(bc,10).reverse();
  c.setOption({grid:{...baseGrid,left:8},tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},xAxis:{type:"value",...ax},
    yAxis:{type:"category",data:t.map(([c2])=>c2),axisLabel:{color:"#334155",fontSize:11,width:230,overflow:"truncate"},...ax},
    series:[{type:"bar",data:t.map(([,v])=>v),barWidth:"62%",itemStyle:{color:gH("#60a5fa","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600}}]},true);}
let __secEnt=[],__secTot=1,__secPage=0;
function chSector(rows){const c=ec("c-sector");if(!c)return;const total=rows.length||1;const ent=topN(countBy(rows,r=>r.is),21);
  c.setOption({tooltip:{trigger:"item",formatter:"{b}<br/><b>{d}%</b> de los anuncios"},
    series:[{type:"pie",radius:["50%","76%"],center:["50%","50%"],itemStyle:{borderColor:"#fff",borderWidth:2},label:{show:false},color:PALETTE,data:ent.map(([k,v])=>({name:secName(k),value:v}))}]},true);
  __secEnt=ent;__secTot=total;__secPage=0;buildSecLegend();}
function buildSecLegend(){const host=document.getElementById("sec-leg");if(!host)return;const per=6;const pages=Math.max(1,Math.ceil(__secEnt.length/per));if(__secPage>=pages)__secPage=0;
  const slice=__secEnt.slice(__secPage*per,__secPage*per+per);
  const items=slice.map(([k,v],i)=>{const gi=__secPage*per+i;return `<div class="sleg-item"><span class="sdot" style="background:${PALETTE[gi%PALETTE.length]}"></span>${lic(secLic(k),13)}<span class="sname">${secName(k)}</span><span class="spct">${pctTxt(v,__secTot)}</span></div>`;}).join("");
  host.innerHTML=`<div class="sleg-grid">${items}</div>`+(pages>1?`<div class="sleg-nav"><button class="sleg-btn" id="sleg-prev">${lic("chevron-left",15)}</button><span>${__secPage+1}/${pages}</span><button class="sleg-btn" id="sleg-next">${lic("chevron-right",15)}</button></div>`:"");
  if(pages>1){document.getElementById("sleg-prev").onclick=()=>{__secPage=(__secPage-1+pages)%pages;buildSecLegend();};document.getElementById("sleg-next").onclick=()=>{__secPage=(__secPage+1)%pages;buildSecLegend();};}
  drawIcons();}
function chOcup(rows){const c=ec("c-ocup");if(!c)return;const total=rows.length||1;const t=topN(countBy(rows,r=>r.o),15).reverse();
  c.setOption({grid:{left:545,right:54,top:18,bottom:26},
    tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>{const cod=t[p[0].dataIndex][0];return ciuoDesc(cod)+"<br/><b>"+pctTxt(p[0].value,total)+"</b> de los anuncios ("+p[0].value+")<br/><span style='color:#94a3b8;font-size:11px'>Cód. CIUO&nbsp;"+cod+"</span>";}},
    xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,total)}},
    yAxis:{type:"category",data:t.map(([cod])=>ciuoDesc(cod)),...ax,axisLabel:{...ax.axisLabel,color:"#334155",fontSize:11,width:525,overflow:"truncate"}},
    series:[{type:"bar",data:t.map(([,v])=>v),barWidth:"62%",itemStyle:{color:gH("#60a5fa","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,total)}}]},true);}
let __mapaReg=false;
function chMapa(){if(!DATA.flags.mapa||!GEO){lock("lock-mapa","ubicación");return;}const c=ec("c-mapa");if(!c)return;
  if(!__mapaReg){echarts.registerMap("ecuador",GEO);__mapaReg=true;}
  // El mapa ignora su propio filtro de provincia: muestra siempre la distribución
  // completa (sí respeta los demás filtros) y resalta la provincia seleccionada.
  const rows=applyFilters(true);const total=rows.length||1;
  const m=countBy(rows,r=>r.pv);
  const data=DATA.provincias.map(p=>({name:p,value:+_pct(m[p]||0,total).toFixed(1),n:m[p]||0,
    itemStyle:p===state.provincia?{borderColor:"#0f2747",borderWidth:2.6}:undefined}));
  const max=Math.max(1,...data.map(d=>d.value));
  c.setOption({tooltip:{trigger:"item",formatter:p=>`${p.name}<br/><b>${(p.value||0)}%</b> de los anuncios`+(p.data&&p.data.n!=null?` (${p.data.n})`:"")+(p.name===state.provincia?" · filtrando":"")},
    visualMap:{type:"continuous",min:0,max:max,left:8,bottom:6,itemHeight:120,calculable:true,formatter:v=>Math.round(v)+"%",
      inRange:{color:["#eef4ff","#bfdbfe","#60a5fa","#2563eb","#1e3a8a"]},textStyle:{color:"#475569",fontSize:10}},
    series:[{type:"map",map:"ecuador",roam:false,nameProperty:"shapeName",
      layoutCenter:["50%","50%"],layoutSize:"100%",label:{show:false},
      itemStyle:{borderColor:"#fff",borderWidth:.8,areaColor:"#f3f6fc"},
      emphasis:{label:{show:true,color:"#0f2747",fontSize:10,fontWeight:600},itemStyle:{borderColor:"#1e3a8a",borderWidth:1.4}},
      data:data}]},true);
  c.off("click");c.on("click",p=>{if(!p||!p.name)return;
    state.provincia=(state.provincia===p.name)?"":p.name;
    // Ciudad y provincia son geográficamente excluyentes: gana la última elegida.
    if(state.provincia&&state.ciudad){state.ciudad="";if(CSELS["cs-ciudad"])buildCSel("cs-ciudad",CSELS["cs-ciudad"].items,"",CSELS["cs-ciudad"].onPick,CSELS["cs-ciudad"].ph);}
    refresh();});}
function chCiudad(rows){if(!DATA.flags.ubicacion){lock("lock-ciudad","ubicación");return;}const c=ec("c-ciudad");if(!c)return;const total=rows.length||1;const t=topN(countBy(rows,r=>r.tp),12).reverse();
  c.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br/><b>"+pctTxt(p[0].value,total)+"</b> de los anuncios ("+p[0].value+")"},
    xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,total)}},
    yAxis:{type:"category",data:t.map(([p])=>p),axisLabel:{color:"#334155",fontSize:11},...ax},
    series:[{type:"bar",data:t.map(([,v])=>v),barWidth:"60%",itemStyle:{color:gH("#60a5fa","#1e40af"),borderRadius:[0,5,5,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,total)}}]},true);}
function lock(id,campo){const el=document.getElementById(id);if(el){el.style.display="flex";el.innerHTML=`${lic("lock",15)} Requiere <b>&nbsp;${campo}&nbsp;</b>`;drawIcons();}}
function tablaGen(rows){const cols=[["c","Cargo"],["o","CIUO"]];if(DATA.flags.ubicacion)cols.push(["tp","Ciudad"]);if(DATA.flags.salario)cols.push(["sal","Salario"]);
  document.getElementById("tbl-head").innerHTML=cols.map(c=>`<th>${c[1]}</th>`).join("")+"<th>Sector</th>";
  document.getElementById("tbl-body").innerHTML=rows.slice(0,300).map(r=>{
    const tds=cols.map(([k])=>{if(k==="o")return `<td><span class="pill">${r.o||"—"}</span> ${ciuoDesc(r.o)}</td>`;
      if(k==="sal")return `<td>${r.sal?"$"+Number(r.sal).toLocaleString("es"):"—"}</td>`;return `<td>${r[k]||"—"}</td>`;}).join("");
    return `<tr>${tds}<td><span class="cellic">${lic(secLic(r.is),14)} ${secName(r.is)}</span></td></tr>`;}).join("");
  document.getElementById("tbl-count").textContent=`${rows.length.toLocaleString("es")} anuncios · mostrando ${Math.min(300,rows.length)}`;}

/* Skills (O*NET) */
function skillCounts(rows){const m={};for(const r of rows){if(!r.sk)continue;for(const id of r.sk)m[id]=(m[id]||0)+1;}return m;}
function kpisSk(rows,cnt){
  const conSk=rows.filter(r=>r.sk&&r.sk.length).length;const top=topN(cnt,1)[0];
  const fam=countBy(Object.keys(cnt).map(id=>({f:skFam(id)})),x=>x.f);const ft=topN(fam,1)[0];
  const cards=[
    {ic:"brain",val:Object.keys(cnt).length,lbl:"Competencias O*NET"},
    {ic:"flame",val:top?skName(top[0]):"—",lbl:"Más demandada",extra:top?pctTxt(top[1],rows.length)+" de los anuncios":"",small:true},
    {ic:"pin",val:rows.length?Math.round(conSk/rows.length*100)+"%":"—",lbl:"Anuncios con competencias",extra:conSk.toLocaleString("es")+" de "+rows.length.toLocaleString("es")},
    {ic:"layers",val:ft?ft[0]:"—",lbl:"Familia predominante",small:true},
  ];
  document.getElementById("kpis-sk").innerHTML=cards.map(c=>
    `<div class="kpi"><div class="ic">${lic(c.ic,22)}</div><div class="val" style="font-size:${c.small?'18px':'25px'}">${c.val}</div><div class="lbl">${c.lbl}</div>${c.extra?`<div class="extra">${c.extra}</div>`:""}</div>`).join("");
}
function skTop(cnt){const c=ec("s-top");if(!c)return;const total=CUR.length||1;const t=topN(cnt,10).reverse();
  c.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br/><b>"+pctTxt(p[0].value,total)+"</b> de los anuncios ("+p[0].value+")"},
    xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,total)}},
    yAxis:{type:"category",data:t.map(([id])=>skName(id)),axisLabel:{color:"#334155",fontSize:12},...ax},
    series:[{type:"bar",data:t.map(([,v])=>v),barWidth:"62%",itemStyle:{color:gH("#38bdf8","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,total)}}]},true);}
function skFamilia(cnt){const c=ec("s-fam");if(!c)return;const fam={};for(const[id,v]of Object.entries(cnt))fam[skFam(id)]=(fam[skFam(id)]||0)+v;
  const d=Object.entries(fam).sort((a,b)=>b[1]-a[1]).map(([k,v])=>({name:k,value:v}));
  c.setOption({tooltip:{trigger:"item",formatter:"{b}<br/><b>{d}%</b> de las menciones"},legend:{type:"scroll",orient:"vertical",right:0,top:"middle",textStyle:{fontSize:10,color:"#475569"}},
    series:[{type:"pie",radius:["40%","66%"],center:["25%","50%"],itemStyle:{borderColor:"#fff",borderWidth:2},label:{show:false},color:PALETTE,data:d}]},true);}
function skOcup(rows){const c=ec("s-ocup");if(!c)return;const total=rows.length||1;const grupos=topN(countBy(rows,r=>r.og),8).map(([g])=>g);
  const data=grupos.map(g=>{const cc=skillCounts(rows.filter(r=>r.og===g));const t=topN(cc,1)[0];return {g,skill:t?skName(t[0]):"—",val:t?t[1]:0};}).filter(d=>d.val>0).reverse();
  c.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>{const d=data[p[0].dataIndex];return grpName(d.g)+"<br/>Líder: <b>"+d.skill+"</b> ("+pctTxt(d.val,total)+")";}},
    xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,total)}},yAxis:{type:"category",data:data.map(d=>d.skill),axisLabel:{color:"#334155",fontSize:11,width:160,overflow:"truncate"},...ax},
    series:[{type:"bar",data:data.map(d=>d.val),barWidth:"60%",itemStyle:{color:gH("#7dd3fc","#1e40af"),borderRadius:[0,5,5,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,total)}}]},true);}
function skRara(cnt){const c=ec("s-rara");if(!c)return;const total=CUR.length||1;const t=botN(cnt,10).reverse();
  c.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br/><b>"+pctTxt(p[0].value,total)+"</b> de los anuncios ("+p[0].value+")"},
    xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,total)}},
    yAxis:{type:"category",data:t.map(([id])=>skName(id)),axisLabel:{color:"#334155",fontSize:11},...ax},
    series:[{type:"bar",data:t.map(([,v])=>v),barWidth:"60%",itemStyle:{color:gH("#bfdbfe","#60a5fa"),borderRadius:[0,5,5,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,total)}}]},true);}
function tablaSk(rows,cnt){const total=rows.length||1;const ord=topN(cnt,200);
  document.getElementById("sk-body").innerHTML=ord.map(([id,v])=>{
    const sub=rows.filter(r=>r.sk&&r.sk.includes(+id));const gt=topN(countBy(sub,r=>r.og),1)[0];
    const d=(DATA.skillDesc&&DATA.skillDesc[id])||"";
    return `<tr><td><span class="skq" data-desc="${esc(d)}"><b>${skName(id)}</b></span></td><td><span class="pill">${skFam(id)}</span></td><td>${v.toLocaleString("es")}</td><td>${(v/total*100).toFixed(1)}%</td><td>${gt?`<span class="cellic">${lic(grpLic(gt[0]),14)} ${grpName(gt[0])}</span>`:"—"}</td></tr>`;}).join("");
  document.getElementById("sk-count").textContent=`${Object.keys(cnt).length} competencias O*NET en ${rows.length.toLocaleString("es")} anuncios`;}

/* Cuadro sinóptico: trabajo (ocupación CIUO) -> SOC -> competencias O*NET */
function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;");}
function occSkills(code){const sub=DATA.rows.filter(r=>r.o===code&&r.sk&&r.sk.length);if(!sub.length)return null;
  const soc=topN(countBy(sub,r=>r.s),1)[0][0];const row=sub.find(r=>r.s===soc)||sub[0];return {soc,sk:row.sk};}
let __treeReady=false;
// Selector de ocupación BUSCABLE + alfabético (reemplaza al <select>)
let __ocselOutside=false;
function buildOccSelect(hostId,items,onPick){const host=document.getElementById(hostId);if(!host)return null;
  items=items.slice().sort((a,b)=>a.label.localeCompare(b.label,'es',{sensitivity:'base'}));
  const lblOf=v=>{const it=items.find(x=>x.v===v);return it?it.label:'';};
  host.className='ocsel';
  host.innerHTML='<input class="ocsel-input" type="text" autocomplete="off" placeholder="Buscar o elegir ocupación…"><div class="ocsel-menu"></div>';
  const inp=host.querySelector('.ocsel-input'),menu=host.querySelector('.ocsel-menu');let chosen=null;
  function render(f){const q=(f||'').toLowerCase();const sub=items.filter(x=>x.label.toLowerCase().includes(q)).slice(0,300);
    menu.innerHTML=sub.length?sub.map(x=>`<div class="ocsel-opt" data-v="${x.v}" title="${esc(x.label)}">${esc(x.label)}</div>`).join(''):'<div class="ocsel-empty">Sin coincidencias</div>';
    menu.querySelectorAll('.ocsel-opt').forEach(o=>o.onclick=()=>{chosen=o.dataset.v;inp.value=lblOf(chosen);host.classList.remove('open');onPick(chosen);});}
  inp.addEventListener('focus',()=>{render('');host.classList.add('open');inp.select();});
  inp.addEventListener('input',()=>{host.classList.add('open');render(inp.value);});
  inp.addEventListener('blur',()=>setTimeout(()=>{if(chosen)inp.value=lblOf(chosen);},160));
  if(!__ocselOutside){__ocselOutside=true;document.addEventListener('click',e=>{document.querySelectorAll('.ocsel.open').forEach(o=>{if(!o.contains(e.target))o.classList.remove('open');});});}
  host._pickFirst=()=>{if(items.length){chosen=items[0].v;inp.value=lblOf(chosen);onPick(chosen);}};
  render('');return host;}
function fillTreeOcc(grp){const occ=topN(countBy(DATA.rows.filter(r=>r.sk&&r.sk.length&&(!grp||r.og===grp)),r=>r.o),300);
  const items=occ.map(([code])=>({v:code,label:ciuoDesc(code)}));
  if(!items.length){document.getElementById("tree-sel").innerHTML='<input class="ocsel-input" disabled placeholder="Sin ocupaciones">';document.getElementById("tree-soc").textContent="";const c=ec("s-tree");if(c)c.clear();return;}
  const h=buildOccSelect("tree-sel",items,code=>chTree(code));if(h)h._pickFirst();}
function initTree(){if(__treeReady)return;const sel=document.getElementById("tree-sel"),grp=document.getElementById("tree-grp");if(!sel||!grp)return;
  const conSk=DATA.rows.filter(r=>r.sk&&r.sk.length);
  if(!conSk.length){lock("lock-tree","competencias O*NET");return;}
  const grupos=topN(countBy(conSk,r=>r.og),12).map(([g])=>g).sort((a,b)=>grpName(a).localeCompare(grpName(b),'es'));
  grp.innerHTML='<option value="">Todos los grupos</option>';
  grupos.forEach(g=>{const o=document.createElement("option");o.value=g;o.textContent=grpName(g);grp.appendChild(o);});
  grp.addEventListener("change",e=>fillTreeOcc(e.target.value));
  __treeReady=true;fillTreeOcc("");}
function chTree(code){const c=ec("s-tree");if(!c)return;const info=occSkills(code);
  document.getElementById("tree-soc").textContent=info?("SOC "+info.soc):"";
  if(!info){c.clear();return;}
  const root={name:ciuoDesc(code),children:info.sk.map(id=>({name:skName(id),value:id}))};
  c.setOption({tooltip:{trigger:"item",confine:true,extraCssText:"max-width:340px;white-space:normal;line-height:1.45",formatter:p=>{const id=p.data&&p.data.value;const d=(id!=null&&DATA.skillDesc)?(DATA.skillDesc[id]||""):"";return `<span style="color:#1e3a8a">${p.name}</span>`+(d?`<br/>${d}`:"");}},
    series:[{type:"tree",data:[root],top:"3%",bottom:"3%",left:"15%",right:"24%",orient:"LR",symbol:"circle",symbolSize:9,
      lineStyle:{color:"#93c5fd",width:1.3,curveness:.5},itemStyle:{color:"#1d4ed8",borderColor:"#1d4ed8"},
      label:{position:"left",verticalAlign:"middle",align:"right",fontSize:12,color:"#0f2747"},
      leaves:{label:{position:"right",align:"left",fontSize:11,color:"#334155"}},
      emphasis:{focus:"descendant"},expandAndCollapse:false,animationDuration:450}]},true);}

/* Actividades del puesto: ocupación CIUO -> SOC -> tareas O*NET traducidas */
function socOf(code){const sub=DATA.rows.filter(r=>r.o===code&&r.s);if(!sub.length)return null;return topN(countBy(sub,r=>r.s),1)[0][0];}
let __tasksReady=false;
function fillTkOcc(grp){const occ=topN(countBy(DATA.rows.filter(r=>r.o&&r.s&&DATA.socTasks[r.s]&&(!grp||r.og===grp)),r=>r.o),300);
  const items=occ.map(([code])=>({v:code,label:ciuoDesc(code)}));
  if(!items.length){document.getElementById("tk-sel").innerHTML='<input class="ocsel-input" disabled placeholder="Sin ocupaciones">';document.getElementById("tk-soc").textContent="";document.getElementById("tk-list").innerHTML="<div class='csub' style='padding:8px'>Sin tareas para este grupo.</div>";return;}
  const h=buildOccSelect("tk-sel",items,code=>renderTasks(code));if(h)h._pickFirst();}
function initTasks(){if(__tasksReady)return;const sel=document.getElementById("tk-sel"),grp=document.getElementById("tk-grp");if(!sel||!grp)return;
  if(!DATA.flags.tasks||!DATA.socTasks||!Object.keys(DATA.socTasks).length){document.getElementById("tasks-locked").style.display="block";return;}
  const con=DATA.rows.filter(r=>r.s&&DATA.socTasks[r.s]);
  const grupos=topN(countBy(con,r=>r.og),12).map(([g])=>g).sort((a,b)=>grpName(a).localeCompare(grpName(b),'es'));
  grp.innerHTML='<option value="">Todos los grupos</option>';
  grupos.forEach(g=>{const o=document.createElement("option");o.value=g;o.textContent=grpName(g);grp.appendChild(o);});
  grp.addEventListener("change",e=>fillTkOcc(e.target.value));
  __tasksReady=true;fillTkOcc("");}
// Icono según el verbo/acción de la tarea (texto sin acentos para el match)
const TASK_ICONS=[
  [/dirig|coordin|gestion|administr|lider|organiz|planif|establec/,"workflow"],
  [/prepar|elabor|redact|escrib|document|registr|complet|llen|emit/,"file-text"],
  [/analiz|evalu|revis|examin|estudi|investig|determin|diagnostic/,"search"],
  [/calcul|cont|factur|presupuest|financ|pag|cobr|cuadr|balanc/,"calculator"],
  [/comunic|reun|consult|negoci|asesor|orient|coordin.*con|conferenci/,"messages-square"],
  [/dise|desarroll|crear|formul|elabor.*plan|concept/,"lightbulb"],
  [/ensen|capacit|form|instru|entren|educ|imparti/,"graduation-cap"],
  [/vend|comerci|promo|client|despach.*venta/,"shopping-cart"],
  [/oper|manej|conduc|instal|repar|manten|ensambl|fabric|construc|ajust/,"wrench"],
  [/control|inspeccion|verif|monitor|superv|garantiz|asegur|cumpl|calidad/,"shield-check"],
  [/cuid|asist|atend.*pacient|medic|salud|enfermer|trat|administr.*medic/,"heart-pulse"],
  [/cocin|aliment|prepar.*plat|coccion|menu|reposter/,"utensils"],
  [/limpi|higien|sanitiz|desinfect|asear/,"spray-can"],
  [/transport|distribu|entreg|carga|rut|reparti|almacen|bodeg/,"truck"],
  [/proteg|seguridad|vigil|custodi|resguard/,"shield"],
];
function taskIcon(es){const t=(es||"").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g,"");
  for(const[re,ic]of TASK_ICONS)if(re.test(t))return ic;return "circle-dot";}
const TL_COLORS=["#2563eb","#0891b2","#4f46e5","#0d9488","#0284c7","#6366f1","#0e7490","#3b82f6","#1d4ed8","#0369a1"];
const TL_LETTERS="ABCDEFGHIJKLMNOPQRSTUVWXYZ";
function renderTasks(code){const soc=socOf(code);document.getElementById("tk-soc").textContent=soc?("SOC "+soc):"";
  const tasks=(soc&&DATA.socTasks)?DATA.socTasks[soc]:null;const el=document.getElementById("tk-list");
  if(!tasks||!tasks.length){el.innerHTML="<div class='csub' style='padding:8px'>Sin tareas para esta ocupación.</div>";return;}
  const nCore=tasks.filter(t=>t.core).length,nSup=tasks.length-nCore;
  const sub=DATA.rows.filter(r=>r.o===code);const og=sub.length?sub[0].og:"";
  const hero=`<div class="tk-hero">`+
    `<div class="tk-frame"><span class="c c1"></span><span class="c c2"></span><span class="c c3"></span><span class="c c4"></span><div class="tk-bigicon">${lic(grpLic(og)||"briefcase",54)}</div></div>`+
    `<div class="tk-title">Actividades del puesto</div>`+
    `<div class="tk-occname">${esc(ciuoDesc(code))}</div>`+
    (soc?`<div class="tk-soc-pill">SOC ${soc}</div>`:"")+
    `<div class="tk-counts"><div class="tk-cchip"><b>${nCore}</b><span>Esenciales</span></div><div class="tk-cchip"><b>${nSup}</b><span>Compl.</span></div></div></div>`;
  const item=(t,gi)=>{const c=TL_COLORS[gi%TL_COLORS.length];const L=TL_LETTERS[gi]||(gi+1);
    return `<div class="tl-item" style="--c:${c}"><div class="tl-badge">${L}</div>`+
      `<div class="tl-card"><span class="tl-pill">${lic(taskIcon(t.es),13)}${t.core?'Esencial':'Complementaria'}</span>`+
      `<div class="tl-text">${esc(t.es)}</div></div></div>`;};
  const half=Math.ceil(tasks.length/2);
  const col=(arr,off)=>`<div class="tl-col">${arr.map((t,i)=>item(t,off+i)).join("")}</div>`;
  const timeline=`<div class="tk-timeline">${col(tasks.slice(0,half),0)}${col(tasks.slice(half),half)}</div>`;
  el.innerHTML=`<div class="tk-agenda">${hero}${timeline}</div>`;drawIcons();}

function renderGeneral(rows){kpisGen(rows);chOcup(rows);chMapa();chCiudad(rows);chSector(rows);drawIcons();}
function renderSkills(rows){if(!DATA.flags.skills){document.getElementById("skills-locked").style.display="block";return;}
  const cnt=skillCounts(rows);kpisSk(rows,cnt);skTop(cnt);skFamilia(cnt);skOcup(rows);skRara(cnt);tablaSk(rows,cnt);initTree();drawIcons();}
function refresh(){CUR=applyFilters();if(activeTab==="general")renderGeneral(CUR);else if(activeTab==="soft")renderSoft();else if(activeTab==="tech")renderTech();else if(activeTab==="carreras")renderCarreras();else if(activeTab==="tasks")initTasks();else if(activeTab==="skills")renderSkills(CUR);setTimeout(()=>Object.values(charts).forEach(c=>c&&c.resize()),30);}

document.querySelectorAll(".tab").forEach(t=>t.addEventListener("click",()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".panel").forEach(x=>x.classList.remove("active"));
  t.classList.add("active");activeTab=t.dataset.tab;document.getElementById("panel-"+activeTab).classList.add("active");
  if(activeTab==="general")renderGeneral(CUR);else if(activeTab==="soft")renderSoft();else if(activeTab==="tech")renderTech();else if(activeTab==="carreras")renderCarreras();else if(activeTab==="tasks")initTasks();else if(activeTab==="skills")renderSkills(CUR);
  footFor(activeTab);filterbarFor(activeTab);setTimeout(()=>Object.values(charts).forEach(c=>c&&c.resize()),40);}));
// Footer (fuentes/metodología) solo en O*NET y Actividades; filtros solo en Panorama y Blandas
function footFor(tab){const f=document.getElementById("page-foot");if(f)f.style.display=(tab==="skills"||tab==="tasks")?"block":"none";}
function filterbarFor(tab){const f=document.getElementById("filterbar");if(f)f.style.display=(tab==="general"||tab==="soft"||tab==="tech"||tab==="carreras")?"flex":"none";}

function onetView(v){v=(v==="tasks")?"tasks":"skills";document.querySelectorAll(".panel").forEach(x=>x.classList.remove("active"));document.getElementById("panel-"+v).classList.add("active");document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.tab==="skills"));document.querySelectorAll(".onet-btn").forEach(b=>b.classList.toggle("active",b.dataset.v===v));activeTab=v; if(v==="tasks"){initTasks();}else{renderSkills(CUR);}setTimeout(()=>Object.values(charts).forEach(c=>c&&c.resize()),40);}
let _evolCar="",_evolRel=false,_evolPer="all",_evolGran="week";
function setEvol(rel){_evolRel=rel;document.querySelectorAll("[data-em]").forEach(b=>b.classList.toggle("active",(b.dataset.em==="rel")===rel));renderCarreras();}
function setEvolPer(p){_evolPer=p;document.querySelectorAll("[data-ep]").forEach(b=>b.classList.toggle("active",b.dataset.ep===p));renderCarreras();}
function setEvolGran(g){_evolGran=g;document.querySelectorAll("[data-eg]").forEach(b=>b.classList.toggle("active",b.dataset.eg===g));renderCarreras();}
function descargarCarrerasCSV(){
  // Panel largo publicación × carrera (mismo formato que exports/panel_demanda_carrera.csv).
  // Usa CUR: la descarga respeta los filtros activos (fechas, sector, ocupación, ciudad).
  const esc=v=>{v=(v===undefined||v===null)?"":String(v);return /[",;\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;};
  const lunes=dt=>{const d=new Date(dt);const day=d.getDay()||7;d.setDate(d.getDate()+1-day);return d.toISOString().slice(0,10);};
  const cab=["vacante_id","fecha","semana","mes","carrera","facultad","plazas","ciudad","provincia",
             "ciuo_codigo","ocupacion","salario_min","salario_max","experiencia_anos",
             "requiere_posgrado","sector_publico","cargo","palabras_clave"];
  const filas=[cab.join(";")];
  const selC=(document.getElementById("dl-carrera")||{}).value||"";
  const selM=(document.getElementById("dl-mes")||{}).value||"";
  for(const r of CUR){
    if(!r.cr||!r.cr.length)continue;
    if(selM&&(!r.dt||r.dt.slice(0,7)!==selM))continue;
    for(const c of r.cr){
      if(selC&&c!==selC)continue;
      filas.push([r.id||"",r.dt||"",r.dt?lunes(r.dt):"",r.dt?r.dt.slice(0,7):"",c,DATA.carreraFac[c]||"",
        (r.vn||1),r.tp||"",r.pv||"",r.o||"",DATA.ciuoMap[r.o]||"",
        (r.s0!==undefined?r.s0:""),(r.s1!==undefined?r.s1:""),(r.ex!==undefined?r.ex:""),
        (r.rm?1:0),(r.pb?"publico":"privado"),r.c||"",(r.kw&&r.kw.length?r.kw.join(", "):"")].map(esc).join(";"));
    }
  }
  const blob=new Blob(["﻿"+filas.join("\n")],{type:"text/csv;charset=utf-8"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  const slug=selC?selC.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^\w]+/g,"_"):"todas_las_carreras";a.download="demanda_"+slug+(selM?"_"+selM:"")+".csv";
  document.body.appendChild(a);a.click();document.body.removeChild(a);
  setTimeout(()=>URL.revokeObjectURL(a.href),4000);
}
function renderCarreras(){const cnt={},cntA={},cntM={}; let con=0, plz=0, mstTot=0;for(const r of CUR){ if(r.cr&&r.cr.length){con++; const w=(r.vn||1); plz+=w; if(r.rm)mstTot++; for(const c of r.cr){cnt[c]=(cnt[c]||0)+w;cntA[c]=(cntA[c]||0)+1;if(r.rm)cntM[c]=(cntM[c]||0)+1;}} }const tot=CUR.length; const top=topN(cnt,1)[0];const kp=document.getElementById("kpis-car");if(kp)kp.innerHTML=[["graduation-cap",Object.keys(cnt).length,"Carreras con demanda"],["award",top?top[0]:"-","Carrera mas demandada"],["briefcase",plz.toLocaleString("es"),"Plazas ofertadas"],["percent",tot?Math.round(con/tot*100)+"%":"-","Anuncios con carrera identificada"],["book-open",con?(mstTot/con*100).toFixed(1)+"%":"-","Piden posgrado"]].map(c=>`<div class="kpi"><div class="ic">${lic(c[0],22)}</div><div class="val" style="font-size:${String(c[1]).length>13?'15px':'25px'}">${c[1]}</div><div class="lbl">${c[2]}</div></div>`).join("");const c=ec("car-bar"); if(c){const tt=topN(cnt,40).reverse();const dom=document.getElementById("car-bar");if(dom){dom.style.height=Math.max(420,tt.length*26+50)+"px";}c.resize();c.setOption({grid:{...baseGrid,left:8,right:56},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>{const car=tt[p[0].dataIndex][0];const na=cntA[car]||0;const pm=na?((cntM[car]||0)/na*100).toFixed(1):0;return car+" ("+(DATA.carreraFac[car]||"")+")<br/><b>"+p[0].value.toLocaleString("es")+"</b> plazas en "+na.toLocaleString("es")+" anuncios<br/>"+pm+"% de los anuncios exige posgrado";}},xAxis:{type:"value",...ax},yAxis:{type:"category",data:tt.map(d=>d[0]),...ax,axisLabel:{color:"#334155",fontSize:11,formatter:v=>{v=v.replace("Pedagogía de las CC. Experimentales - ","Ped. CC. Exp. – ").replace("Pedagogía de los Idiomas Nacionales y Extranjeros","Ped. de Idiomas Nac. y Extranjeros").replace("Pedagogía de la Actividad Física y Deporte","Ped. Actividad Física y Deporte").replace("Pedagogía de la Lengua y la Literatura","Ped. Lengua y Literatura");return v.length>36?v.slice(0,35)+"…":v;}}},series:[{type:"bar",data:tt.map(d=>d[1]),barWidth:"68%",itemStyle:{color:gH("#60a5fa","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,fontSize:11,formatter:p=>p.value.toLocaleString("es")}}]},true);}const es=document.getElementById("evol-car"); if(es&&es.options.length<=1){Object.keys(DATA.carreraFac).sort().forEach(cc=>{const o=document.createElement("option");o.value=cc;o.textContent=cc;es.appendChild(o);});}const dc=document.getElementById("dl-carrera"); if(dc&&dc.options.length<=1){Object.keys(DATA.carreraFac).sort().forEach(cc=>{const o=document.createElement("option");o.value=cc;o.textContent=cc;dc.appendChild(o);});}
const dm=document.getElementById("dl-mes"); if(dm&&dm.options.length<=1){const MN=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];[...new Set(DATA.rows.filter(r=>r.dt).map(r=>r.dt.slice(0,7)))].sort().forEach(mk=>{const o=document.createElement("option");o.value=mk;o.textContent=MN[+mk.slice(5,7)-1]+" "+mk.slice(0,4);dm.appendChild(o);});}const ce=ec("car-evol"); if(ce){const allDts=CUR.filter(r=>r.dt).map(r=>r.dt).sort();const maxDt=allDts.length?new Date(allDts[allDts.length-1]):new Date();const cutMs={all:0,"6m":182,"3m":91,"4w":28}[_evolPer]*86400000;const inPer=r=>!cutMs||(maxDt-new Date(r.dt))<=cutMs;const bkey=dt=>{if(_evolGran!=="week")return dt.slice(0,7);const d=new Date(dt);const day=d.getDay()||7;d.setDate(d.getDate()+1-day);return d.toISOString().slice(0,10);};const mm={},tt={},cc={};for(const r of CUR){if(!r.dt||!inPer(r))continue;const k=bkey(r.dt);tt[k]=(tt[k]||0)+1;if(r.cr&&r.cr.length)cc[k]=(cc[k]||0)+1;const hit=_evolCar?(r.cr&&r.cr.includes(_evolCar)):(r.cr&&r.cr.length);if(hit)mm[k]=(mm[k]||0)+1;}const skeys=Object.keys(tt).sort();const fillKeys=(f,l)=>{if(!f)return[];if(_evolGran!=="week"){const r=[];let[y,mo]=[+f.slice(0,4),+f.slice(5,7)];const[ey,em]=[+l.slice(0,4),+l.slice(5,7)];while(y<ey||(y===ey&&mo<=em)){r.push(y+"-"+String(mo).padStart(2,"0"));mo++;if(mo>12){mo=1;y++;}}return r;}else{const r=[];let d=new Date(f);const end=new Date(l);while(d<=end){r.push(d.toISOString().slice(0,10));d.setDate(d.getDate()+7);}return r;}};const ks=skeys.length?fillKeys(skeys[0],skeys[skeys.length-1]):[];const mos=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];const fmtK=k=>_evolGran==="week"?k.slice(8)+" "+mos[+k.slice(5,7)-1]:mos[+k.slice(5,7)-1]+" "+k.slice(0,4);const dd=ks.map(k=>_evolRel?+(((mm[k]||0)/((tt[k]||0)||1)*100).toFixed(1)):(mm[k]||0));const focoNom=_evolCar||"Con carrera asignada";
// Énfasis (dataviz): la serie foco en azul (línea 2px, marcador 8px con anillo
// blanco) sobre un contexto gris de la MISMA unidad (anuncios) -> un solo eje.
// El contexto se elige a escala comparable: total publicados para la vista
// global; anuncios con carrera asignada cuando se enfoca una carrera (el total
// aplastaría una serie de ~30/semana contra ~5.000). En relativo (%) no aplica.
const ctxNom=_evolCar?"Con carrera asignada":"Publicados (total)";
const ddCtx=ks.map(k=>(_evolCar?(cc[k]||0):(tt[k]||0)));
const series=[];
if(!_evolRel){series.push({name:ctxNom,type:"bar",data:ddCtx,barWidth:"55%",itemStyle:{color:"#e2e8f0",borderRadius:[4,4,0,0]},emphasis:{itemStyle:{color:"#cbd5e1"}}});}
series.push({name:focoNom,type:"line",smooth:0.35,smoothMonotone:"x",data:dd,symbol:"circle",symbolSize:8,z:3,lineStyle:{width:2,color:"#2563eb"},itemStyle:{color:"#2563eb",borderColor:"#ffffff",borderWidth:2},areaStyle:_evolRel?{color:"rgba(37,99,235,.10)"}:undefined});
ce.setOption({grid:{...baseGrid,top:44,bottom:ks.length>10&&_evolGran==="week"?52:36},legend:_evolRel?undefined:{top:0,left:8,itemWidth:14,itemHeight:9,textStyle:{color:"#475569",fontSize:11},data:series.map(s=>s.name)},tooltip:{trigger:"axis",axisPointer:{type:"line",lineStyle:{color:"#cbd5e1"}},formatter:p=>{const k=ks[p[0].dataIndex];const n=mm[k]||0;const tot=tt[k]||0;const pct=+(n/(tot||1)*100).toFixed(1);const q=_evolCar?("anuncios para "+_evolCar):"anuncios con carrera asignada";const ini=(p[0].dataIndex===0&&_evolPer==="all")?"<br/><span style='color:#94a3b8;font-size:11px'>Inicio de la recolección: incluye anuncios acumulados</span>":"";return fmtK(k)+"<br/><b>"+n+"</b> "+q+"<br/>"+tot+" publicados en el periodo ("+pct+"%)"+ini;}},xAxis:{type:"category",data:ks,...ax,axisLabel:{color:"#475569",fontSize:10,rotate:ks.length>8?42:0,formatter:fmtK}},yAxis:{type:"value",...ax,axisLabel:{color:"#475569",formatter:_evolRel?"{value}%":"{value}"},splitLine:{lineStyle:{color:"#eef2f8"}}},series},true);}
const tcard=document.getElementById("car-tabla-card");if(tcard){if(!_evolCar){tcard.style.display="none";}else{tcard.style.display="";const _allDts=CUR.filter(r=>r.dt).map(r=>r.dt).sort();const _maxDt=_allDts.length?new Date(_allDts[_allDts.length-1]):new Date();const _cutMs={all:0,"6m":182,"3m":91,"4w":28}[_evolPer]*86400000;const _inPer=r=>!_cutMs||(_maxDt-new Date(r.dt))<=_cutMs;const fil=CUR.filter(r=>r.cr&&r.cr.includes(_evolCar)&&r.dt&&_inPer(r)).sort((a,b)=>(b.dt||"").localeCompare(a.dt||"")).reverse();const ttl=document.getElementById("car-tabla-title");if(ttl)ttl.textContent="Anuncios · "+_evolCar;const tsub=document.getElementById("car-tabla-sub");const tbody=document.getElementById("car-tbl-body");const PAGE=300;if(tsub)tsub.textContent=fil.length+(fil.length===1?" anuncio":" anuncios")+(fil.length>PAGE?" · mostrando los "+PAGE+" más recientes":"");if(tbody)tbody.innerHTML=fil.slice(0,PAGE).map(r=>"<tr><td>"+esc(r.c||"—")+"</td><td>"+esc(r.em||"—")+"</td><td>"+(r.tp||"—")+"</td><td>"+(r.dt?r.dt.slice(0,10):"—")+"</td><td>"+esc(ciuoDesc(r.o||""))+"</td><td>"+esc(r.kw&&r.kw.length?r.kw.join(", "):"—")+"</td></tr>").join("");}}
if(window.lucide)lucide.createIcons();}
function renderSoft(){const _rows=CUR;const _c={};for(const r of _rows){if(!r.sb)continue;for(const id of r.sb)_c[id]=(_c[id]||0)+1;}const _tot=_rows.length||1;const _cap=s=>s?s.charAt(0).toUpperCase()+s.slice(1):s;const data=Object.entries(_c).sort((a,b)=>b[1]-a[1]).slice(0,40).map(([id,v])=>[_cap((DATA.softVocab&&DATA.softVocab[id])||'—'),v]);const top3=data.slice(0,3).map(d=>d[0]).join(", ");const nrr=document.getElementById("soft-narr");if(nrr)nrr.innerHTML=data.length?("Predominan "+top3+". Se detectaron "+data.length+" competencias blandas distintas en los anuncios."):"Sin datos.";const kp=document.getElementById("kpis-soft");if(kp&&data.length){const tp=data[0];kp.innerHTML=[["messages-square",data.length,"Competencias blandas"],["flame",tp[0],"Más pedida"],["percent",pctTxt(tp[1],_tot),"Anuncios con la #1"]].map(c=>`<div class="kpi"><div class="ic">${lic(c[0],22)}</div><div class="val" style="font-size:${String(c[1]).length>11?'17px':'25px'}">${c[1]}</div><div class="lbl">${c[2]}</div></div>`).join("");}const BLUES=["#1e3a8a","#1d4ed8","#2563eb","#3b82f6","#60a5fa","#0ea5e9","#0284c7"];if(window.__noWC||window.__noECharts){const el=document.getElementById("cloud");if(el&&data.length){const mx=data[0][1],mn=data[data.length-1][1];el.innerHTML='<div style="display:flex;flex-wrap:wrap;gap:8px 16px;justify-content:center;align-items:center;height:100%;padding:18px">'+data.map(([w,v],k)=>{const f=(v-mn)/((mx-mn)||1);return `<span style="font-weight:800;font-size:${16+Math.round(f*40)}px;color:${BLUES[k%BLUES.length]}">${w}</span>`;}).join(" ")+'</div>';}}else{const c=ec("cloud");if(c)c.setOption({tooltip:{show:true,formatter:p=>p.name+": "+pctTxt(p.value,_tot)+" de los anuncios"},series:[{type:"wordCloud",shape:"circle",sizeRange:[16,72],rotationRange:[-30,30],rotationStep:15,gridSize:8,drawOutOfBound:false,width:"100%",height:"100%",textStyle:{fontWeight:"bold",color:()=>BLUES[Math.floor(Math.random()*BLUES.length)]},emphasis:{textStyle:{color:"#1e3a8a"}},data:data.map(([n,v])=>({name:n,value:v}))}]},true);}const b=ec("soft-bar");if(b){const tot=_tot;const tt=data.slice(0,12).reverse();b.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br/><b>"+pctTxt(p[0].value,tot)+"</b> de los anuncios ("+p[0].value+")"},xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,tot)}},yAxis:{type:"category",data:tt.map(d=>d[0]),axisLabel:{color:"#334155",fontSize:11},...ax},series:[{type:"bar",data:tt.map(d=>d[1]),barWidth:"62%",itemStyle:{color:gH("#60a5fa","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,tot)}}]},true);}if(window.lucide)lucide.createIcons();}
function renderTech(){
  if(!DATA.flags.tecnicas){const l=document.getElementById("tech-locked");if(l)l.style.display="block";return;}
  const V=DATA.techVocab||[];const cnt=new Array(V.length).fill(0);const occ=V.map(()=>new Set());let con=0;
  for(const r of CUR){if(!r.tk||!r.tk.length)continue;con++;for(const i of r.tk){cnt[i]++;if(r.o)occ[i].add(r.o);}}
  const tot=CUR.length||1;
  const orden=cnt.map((v,i)=>[i,v]).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]);
  const kp=document.getElementById("kpis-tech");
  if(kp){const top=orden[0];kp.innerHTML=[["terminal",orden.length,"Herramientas detectadas"],["flame",top?V[top[0]]:"-","Más solicitada"],["file-code",con.toLocaleString("es"),"Anuncios con herramienta"],["percent",tot?Math.round(con/tot*100)+"%":"-","% del total"]].map(c=>`<div class="kpi"><div class="ic">${lic(c[0],22)}</div><div class="val" style="font-size:${String(c[1]).length>12?'16px':'25px'}">${c[1]}</div><div class="lbl">${c[2]}</div></div>`).join("");}
  const bar=ec("tech-bar");
  if(bar){const tt=orden.slice(0,15).reverse();bar.setOption({grid:{...baseGrid,left:8,right:46},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>p[0].name+"<br/><b>"+pctTxt(p[0].value,tot)+"</b> de los anuncios ("+p[0].value+")"},xAxis:{type:"value",...ax,axisLabel:{...ax.axisLabel,formatter:v=>pctTxt(v,tot)}},yAxis:{type:"category",data:tt.map(x=>V[x[0]]),axisLabel:{color:"#334155",fontSize:11},...ax},series:[{type:"bar",data:tt.map(x=>x[1]),barWidth:"62%",itemStyle:{color:gH("#60a5fa","#1d4ed8"),borderRadius:[0,6,6,0]},label:{show:true,position:"right",color:"#1e3a8a",fontWeight:600,formatter:p=>pctTxt(p.value,tot)}}]},true);}
  const sc=ec("tech-scatter");
  if(sc){const data=orden.map(([i,v])=>({name:V[i],value:[v,occ[i].size]}));const maxV=Math.max(1,...data.map(d=>d.value[0]));
    sc.setOption({grid:{left:54,right:26,top:22,bottom:46},
      tooltip:{trigger:"item",formatter:p=>"<b>"+p.data.name+"</b><br/>"+p.data.value[0]+" anuncios · "+p.data.value[1]+" ocupaciones distintas"},
      xAxis:{type:"value",name:"Demanda (anuncios)",nameLocation:"middle",nameGap:26,nameTextStyle:{color:"#475569",fontSize:11},...ax},
      yAxis:{type:"value",name:"Amplitud (ocupaciones distintas)",nameLocation:"middle",nameGap:34,nameTextStyle:{color:"#475569",fontSize:11},...ax},
      series:[{type:"scatter",data:data,symbolSize:d=>8+Math.sqrt(d[0]/maxV)*34,itemStyle:{color:"rgba(37,99,235,.5)",borderColor:"#1d4ed8",borderWidth:1},emphasis:{itemStyle:{color:"#1d4ed8"}},label:{show:true,formatter:p=>p.data.value[0]>=Math.max(6,maxV*0.12)?p.data.name:"",position:"top",color:"#0f2747",fontSize:10,fontWeight:600}}]},true);}
  if(window.lucide)lucide.createIcons();
}
function svgI(n,s){return '<i data-lucide="'+n+'" width="'+(s||15)+'" height="'+(s||15)+'"></i>';}
const CSELS={};
function buildCSel(host,items,current,onPick,ph){
  const el=document.getElementById(host);if(!el)return;CSELS[host]={items,onPick,ph};el.classList.add('csel');
  function paint(v){const cur=items.find(x=>x.v===v)||{label:ph||"Todos",icon:"list"};
    const c=el.querySelector('.csel-cur');if(c)c.innerHTML=svgI(cur.icon)+'<span>'+cur.label+'</span>';
    el.classList.toggle('filtered', !!v);                       // azul si hay filtro aplicado
    el.querySelectorAll('.csel-item').forEach(it=>it.classList.toggle('sel', it.dataset.v===v));
    if(window.lucide)lucide.createIcons();}
  const _big=items.length>12;
  el.innerHTML='<button type="button" class="csel-btn"><span class="csel-cur"></span>'+svgI("chevron-down",14)+'</button>'+
    '<div class="csel-menu">'+(_big?'<input class="csel-search" type="text" placeholder="Buscar…"/>':'')+
    '<div class="csel-list">'+items.map(x=>'<div class="csel-item" data-v="'+x.v+'">'+svgI(x.icon)+'<span>'+x.label+'</span></div>').join('')+'</div></div>';
  el.querySelector('.csel-btn').onclick=e=>{e.stopPropagation();document.querySelectorAll('.csel.open').forEach(o=>{if(o!==el)o.classList.remove('open');});el.classList.toggle('open');const _s=el.querySelector('.csel-search');if(_s&&el.classList.contains('open'))setTimeout(()=>_s.focus(),20);};
  const _sb=el.querySelector('.csel-search');
  if(_sb){_sb.onclick=e=>e.stopPropagation();_sb.oninput=()=>{const q=_sb.value.toLowerCase();el.querySelectorAll('.csel-item').forEach(it=>{it.style.display=it.textContent.toLowerCase().includes(q)?'':'none';});};}
  el.querySelectorAll('.csel-item').forEach(it=>it.onclick=()=>{el.classList.remove('open');paint(it.dataset.v);onPick(it.dataset.v);});
  paint(current);
}
document.addEventListener('click',()=>document.querySelectorAll('.csel.open').forEach(o=>o.classList.remove('open')));
function sectorItems(macro){let ent=topN(countBy(DATA.rows,r=>r.is),40);if(macro)ent=ent.filter(([s])=>macroOf(s)===macro);
  return [{v:"",label:"Todos los sectores",icon:"list"}].concat(ent.map(([s])=>({v:s,label:secName(s),icon:secLic(s)})));}
function pickSector(v){state.sector=v;refresh();}
function initFilters(){
  buildCSel("cs-macro",[{v:"",label:"Todos los macrosectores",icon:"layers"},{v:"P",label:"Primario · agro y extractivo",icon:"sprout"},{v:"S",label:"Secundario · industria",icon:"factory"},{v:"T",label:"Terciario · servicios",icon:"briefcase"}],"",
    v=>{state.macro=v;state.sector="";buildCSel("cs-sector",sectorItems(v),"",pickSector,"Todos los sectores");refresh();},"Todos los macrosectores");
  buildCSel("cs-sector",sectorItems(""),"",pickSector,"Todos los sectores");
  buildCSel("cs-grupo",[{v:"",label:"Todas las ocupaciones",icon:"list"}].concat(topN(countBy(DATA.rows,r=>r.o),400).map(([o])=>({v:o,label:ciuoDesc(o),icon:grpLic(String(o).charAt(0))}))),"",
    v=>{state.grupo=v;refresh();},"Todas las ocupaciones");
  if(DATA.flags.ubicacion)buildCSel("cs-ciudad",[{v:"",label:"Todas las ciudades",icon:"map-pin"}].concat(topN(countBy(DATA.rows,r=>r.tp),40).map(([c])=>({v:c,label:c,icon:"map-pin"}))),"",
    v=>{state.ciudad=v;if(v)state.provincia="";refresh();},"Todas las ciudades");
  else document.getElementById("wrap-ciudad").style.opacity=.5;
  const dd=document.getElementById("f-desde"),dh=document.getElementById("f-hasta");
  if(DATA.flags.fecha&&DATA.meta.fechaMin){const _hoy=new Date().toISOString().slice(0,10);dd.max=dh.max=_hoy;dd.value=DATA.meta.fechaMin;dh.value=DATA.meta.fechaMax;state.desde=DATA.meta.fechaMin;state.hasta=DATA.meta.fechaMax;
    document.querySelectorAll(".fb-pre").forEach(b=>b.addEventListener("click",()=>{const m=+b.dataset.m;const h=new Date().toISOString().slice(0,10);if(m===0){state.desde=DATA.meta.fechaMin;state.hasta=h;}else{const d=new Date();d.setMonth(d.getMonth()-m);state.desde=d.toISOString().slice(0,10);state.hasta=h;}dd.value=state.desde;dh.value=state.hasta;refresh();}));}
  else{document.getElementById("wrap-fecha").style.opacity=.5;dd.disabled=dh.disabled=true;}
  dd.addEventListener("change",e=>{state.desde=e.target.value;refresh();});dh.addEventListener("change",e=>{state.hasta=e.target.value;refresh();});
  document.getElementById("btn-reset").addEventListener("click",()=>{state.macro="";state.sector="";state.grupo="";state.ciudad="";state.provincia="";
    buildCSel("cs-macro",CSELS["cs-macro"].items,"",CSELS["cs-macro"].onPick,CSELS["cs-macro"].ph);
    buildCSel("cs-sector",sectorItems(""),"",pickSector,"Todos los sectores");
    buildCSel("cs-grupo",CSELS["cs-grupo"].items,"",CSELS["cs-grupo"].onPick,CSELS["cs-grupo"].ph);
    if(DATA.flags.ubicacion)buildCSel("cs-ciudad",CSELS["cs-ciudad"].items,"",CSELS["cs-ciudad"].onPick,CSELS["cs-ciudad"].ph);
    if(DATA.flags.fecha&&DATA.meta.fechaMin){dd.value=DATA.meta.fechaMin;dh.value=DATA.meta.fechaMax;state.desde=DATA.meta.fechaMin;state.hasta=DATA.meta.fechaMax;}refresh();});
}
function initMeta(){
  if(window.__noECharts)document.getElementById("banner-echarts").style.display="block";}
function activarTab(name){if(!document.getElementById("panel-"+name))return;
  document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.tab===name));
  document.querySelectorAll(".panel").forEach(x=>x.classList.toggle("active",x.id==="panel-"+name));activeTab=name;}
window.addEventListener("resize",()=>Object.values(charts).forEach(c=>c&&c.resize()));
(function initTip(){const tip=document.getElementById("tip");if(!tip)return;
  document.addEventListener("mouseover",e=>{const t=e.target.closest(".skq");if(!t)return;const d=t.getAttribute("data-desc");if(!d)return;tip.innerHTML=`<span class="tip-h">${t.textContent.trim()}</span>${d}`;tip.style.display="block";});
  document.addEventListener("mousemove",e=>{if(tip.style.display!=="block")return;tip.style.left=Math.min(e.clientX+14,window.innerWidth-345)+"px";tip.style.top=(e.clientY+16)+"px";});
  document.addEventListener("mouseout",e=>{if(e.target.closest(".skq"))tip.style.display="none";});})();
initMeta();initFilters();
{const _h=(location.hash||"").replace("#","");if(_h&&document.getElementById("panel-"+_h))activarTab(_h);}
refresh();drawIcons();footFor(activeTab);filterbarFor(activeTab);
</script>
<div id="tip"></div>
</body>
</html>
"""
