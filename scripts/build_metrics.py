import json
import re
from datetime import datetime, timezone
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────
DATA_PATH    = Path("data/issues.json")   # Archivo de entrada con todos los issues
OUTPUT_PATH  = Path("docs/metrics.json")   # Archivo de salida con las métricas
HOURLY_RATE  = 20                           # Tarifa por hora en USD (ajusta según proyecto)
EXPECTED_VALUE = 600                        # Valor esperado del proyecto en USD (para ROI)

# ── Funciones de extracción ─────────────────────────────────────────────────
def parse_value(body, key, default=0):
    """Lee un número del cuerpo del issue. Ej: 'estimate_hours: 3' → 3.0"""
    pattern = rf"{key}:\s*([0-9]+(?:\.[0-9]+)?)"
    match = re.search(pattern, body or "")
    return float(match.group(1)) if match else default

def parse_date(body, key):
    """Lee una fecha del cuerpo del issue. Ej: 'planned_due: 2026-05-20' → datetime"""
    pattern = rf"{key}:\s*([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})"
    match = re.search(pattern, body or "")
    if not match: return None
    return datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)

def hours_between(start, end):
    """Calcula horas entre fecha de creación y fecha de cierre del issue"""
    if not start or not end: return None
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt   = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return round((end_dt - start_dt).total_seconds() / 3600, 2)

def has_label(issue, label_name):
    """Verifica si el issue tiene una etiqueta específica"""
    return any(label["name"] == label_name for label in issue.get("labels", []))

# ── Lectura y clasificación de issues ────────────────────────────────────────
issues      = json.loads(DATA_PATH.read_text(encoding="utf-8"))
total       = len(issues)
closed      = [i for i in issues if i["state"] == "CLOSED"]
open_issues = [i for i in issues if i["state"] == "OPEN"]
bugs        = [i for i in issues if has_label(i, "bug")]
open_bugs   = [i for i in bugs   if i["state"] == "OPEN"]
closed_bugs = [i for i in bugs   if i["state"] == "CLOSED"]

# ── Cálculo de horas y costos ────────────────────────────────────────────────
estimated_hours     = sum(parse_value(i.get("body",""), "estimate_hours") for i in issues)
actual_hours        = sum(parse_value(i.get("body",""), "actual_hours")   for i in issues)
closed_story_points = sum(parse_value(i.get("body",""), "story_points")   for i in closed)

# ── Tiempo promedio de resolución ────────────────────────────────────────────
resolution_times = [hours_between(i.get("createdAt"), i.get("closedAt")) for i in closed if i.get("closedAt")]
resolution_times = [r for r in resolution_times if r is not None]

# ── Tareas vencidas (fecha límite pasada y aún abiertas) ─────────────────────
now     = datetime.now(timezone.utc)
overdue = [i for i in open_issues if (due := parse_date(i.get("body",""), "planned_due")) and due < now]

# ── Cálculo de costos y ROI ───────────────────────────────────────────────────
actual_cost    = actual_hours    * HOURLY_RATE
estimated_cost = estimated_hours * HOURLY_RATE
cost_variance  = actual_cost - estimated_cost                         # positivo = sobrecosto
roi = ((EXPECTED_VALUE - actual_cost) / actual_cost * 100) if actual_cost > 0 else 0

# ── Nivel de riesgo automático ────────────────────────────────────────────────
risk_level = ("Alto"  if len(overdue) >= 2 or len(open_bugs) >= 2
         else "Medio" if len(overdue) == 1 or len(open_bugs) == 1
         else "Bajo")

# ── Construcción del objeto de métricas ──────────────────────────────────────
metrics = {
    "total_issues":             total,
    "closed_issues":            len(closed),
    "open_issues":              len(open_issues),
    "completion_rate_percent":   round(len(closed) / total * 100, 2) if total else 0,
    "total_bugs":               len(bugs),
    "open_bugs":                len(open_bugs),
    "closed_bugs":              len(closed_bugs),
    "average_resolution_hours": round(sum(resolution_times) / len(resolution_times), 2) if resolution_times else 0,
    "estimated_hours":          estimated_hours,
    "actual_hours":             actual_hours,
    "estimated_cost_usd":       estimated_cost,
    "actual_cost_usd":          actual_cost,
    "cost_variance_usd":        cost_variance,
    "roi_percent":              round(roi, 2),
    "velocity_story_points":    closed_story_points,
    "overdue_open_issues":      len(overdue),
    "risk_level":               risk_level
}

# ── Guardar el resultado ──────────────────────────────────────────────────────
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(metrics, indent=2, ensure_ascii=False))
