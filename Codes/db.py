# -*- coding: utf-8 -*-
"""Stub de compatibilidad — la UNICA fuente de verdad es db.py en la RAIZ.

Este archivo existia como copia y divergia silenciosamente del db.py raiz
(los scrapers usan el de la raiz; algunos scripts de Codes/ importaban este).
Ahora reexporta el modulo raiz: cualquier cambio se hace SOLO en <raiz>/db.py.
"""
import os as _os
import importlib.util as _ilu

_RAIZ = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "db.py")
_spec = _ilu.spec_from_file_location("_db_raiz", _RAIZ)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
