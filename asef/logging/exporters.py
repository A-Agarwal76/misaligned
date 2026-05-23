"""Export log data to JSON, CSV, and self-contained HTML reports.

Provides :class:`LogExporter` which pulls evaluation data from the
:class:`~asef.logging.db_logger.DatabaseLogger` and serialises it
into portable file formats suitable for sharing, archival, and
offline analysis.
"""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .db_logger import (
    AgentActionRecord,
    AnomalyRecord,
    DatabaseLogger,
    MetricRecord,
)


def _dt_iso(dt: datetime | None) -> str:
    """Return an ISO-8601 string or ``'—'`` for *None* timestamps."""
    return dt.isoformat() if dt else "—"


def _safe(text: Any) -> str:
    """HTML-escape arbitrary text, handling *None* gracefully."""
    return html.escape(str(text)) if text is not None else ""


class LogExporter:
    """Export evaluation log data to various file formats.

    Parameters:
        db_logger: An initialised :class:`DatabaseLogger` instance
            used to fetch persisted records.
    """

    def __init__(self, db_logger: DatabaseLogger) -> None:
        self._db: DatabaseLogger = db_logger

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    async def export_json(self, evaluation_id: str, output_path: str) -> str:
        """Export all data for an evaluation as a single JSON file.

        The output contains top-level keys ``evaluation``, ``actions``,
        ``metrics``, and ``anomalies`` each holding the respective
        record data.

        Args:
            evaluation_id: The evaluation to export.
            output_path: Destination file path.

        Returns:
            The absolute path of the written file.
        """
        evaluation = await self._db.get_evaluation(evaluation_id)
        actions = await self._db.get_agent_actions(evaluation_id)
        metrics = await self._db.get_metrics(evaluation_id)
        anomalies = await self._db.get_anomalies(evaluation_id)

        payload: dict[str, Any] = {
            "evaluation": self._eval_dict(evaluation) if evaluation else None,
            "actions": [self._action_dict(a) for a in actions],
            "metrics": [self._metric_dict(m) for m in metrics],
            "anomalies": [self._anomaly_dict(a) for a in anomalies],
        }

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(out.resolve())

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    async def export_csv(self, evaluation_id: str, output_path: str) -> str:
        """Export evaluation data as a single combined CSV file.

        Each row is tagged with a ``record_type`` column so the three
        record kinds (actions, metrics, anomalies) can coexist in a
        single flat file and be separated by downstream tooling.

        Args:
            evaluation_id: The evaluation to export.
            output_path: Destination file path.

        Returns:
            The absolute path of the written file.
        """
        actions = await self._db.get_agent_actions(evaluation_id)
        metrics = await self._db.get_metrics(evaluation_id)
        anomalies = await self._db.get_anomalies(evaluation_id)

        fieldnames = [
            "record_type",
            "id",
            "evaluation_id",
            "timestamp",
            "agent_id",
            "turn_number",
            "action_type",
            "visible_content",
            "hidden_content",
            "state",
            "metric_name",
            "metric_value",
            "metric_type",
            "tags",
            "anomaly_type",
            "severity",
            "evidence",
        ]

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for a in actions:
            writer.writerow(
                {
                    "record_type": "action",
                    "id": a.id,
                    "evaluation_id": a.evaluation_id,
                    "timestamp": _dt_iso(a.timestamp),
                    "agent_id": a.agent_id,
                    "turn_number": a.turn_number,
                    "action_type": a.action_type,
                    "visible_content": a.visible_content,
                    "hidden_content": a.hidden_content,
                    "state": a.state,
                }
            )

        for m in metrics:
            writer.writerow(
                {
                    "record_type": "metric",
                    "id": m.id,
                    "evaluation_id": m.evaluation_id,
                    "timestamp": _dt_iso(m.timestamp),
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "metric_type": m.metric_type,
                    "tags": json.dumps(m.tags) if m.tags else "",
                }
            )

        for a in anomalies:
            writer.writerow(
                {
                    "record_type": "anomaly",
                    "id": a.id,
                    "evaluation_id": a.evaluation_id,
                    "timestamp": _dt_iso(a.timestamp),
                    "agent_id": a.agent_id,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "evidence": json.dumps(a.evidence) if a.evidence else "",
                }
            )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(buf.getvalue(), encoding="utf-8")
        return str(out.resolve())

    # ------------------------------------------------------------------
    # HTML export (self-contained dark-themed report)
    # ------------------------------------------------------------------

    async def export_html(self, evaluation_id: str, output_path: str) -> str:
        """Generate a self-contained HTML report with embedded CSS.

        The report uses a dark theme with syntax-highlighted sections
        for the agent timeline, metrics table, and anomaly list.  No
        external resources are referenced — the file is fully portable.

        Args:
            evaluation_id: The evaluation to export.
            output_path: Destination file path.

        Returns:
            The absolute path of the written file.
        """
        evaluation = await self._db.get_evaluation(evaluation_id)
        actions = await self._db.get_agent_actions(evaluation_id)
        metrics = await self._db.get_metrics(evaluation_id)
        anomalies = await self._db.get_anomalies(evaluation_id)

        eval_type = _safe(evaluation.evaluation_type) if evaluation else "unknown"
        eval_status = _safe(evaluation.status) if evaluation else "unknown"
        eval_started = _dt_iso(evaluation.started_at) if evaluation else "—"
        eval_completed = _dt_iso(evaluation.completed_at) if evaluation else "—"
        eval_summary = _safe(evaluation.result_summary) if evaluation else "—"
        eval_metrics_json = (
            _safe(json.dumps(evaluation.metrics, indent=2)) if evaluation and evaluation.metrics else "{}"
        )

        timeline_html = self._format_timeline_html(actions)
        metrics_html = self._format_metrics_table_html(metrics)
        anomalies_html = self._format_anomalies_html(anomalies)

        report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASEF Evaluation Report — {_safe(evaluation_id)}</title>
<style>
/* ---- Dark theme palette ---- */
:root {{
    --bg-primary: #0f1117;
    --bg-secondary: #161b22;
    --bg-card: #1c2128;
    --bg-highlight: #23292f;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-yellow: #d29922;
    --accent-red: #f85149;
    --accent-purple: #bc8cff;
    --accent-cyan: #39d2c0;
    --font-sans: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ font-size: 15px; }}
body {{
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
    line-height: 1.65;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}}
h1 {{
    font-size: 1.75rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: .25rem;
}}
h2 {{
    font-size: 1.25rem;
    color: var(--accent-cyan);
    margin: 2.5rem 0 1rem;
    padding-bottom: .4rem;
    border-bottom: 1px solid var(--border);
}}
h3 {{ font-size: 1rem; color: var(--text-secondary); margin-bottom: .5rem; }}
p {{ color: var(--text-secondary); margin-bottom: .75rem; }}
.subtitle {{ color: var(--text-muted); font-size: .85rem; margin-bottom: 2rem; }}
/* Cards */
.card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}}
.card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}}
.kv {{ display: flex; justify-content: space-between; padding: .3rem 0; }}
.kv .label {{ color: var(--text-muted); font-size: .85rem; }}
.kv .value {{ font-weight: 600; font-size: .9rem; }}
/* Status badges */
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .04em;
}}
.badge-completed {{ background: rgba(63,185,80,.15); color: var(--accent-green); }}
.badge-failed {{ background: rgba(248,81,73,.15); color: var(--accent-red); }}
.badge-running {{ background: rgba(210,153,34,.15); color: var(--accent-yellow); }}
.badge-started {{ background: rgba(88,166,255,.15); color: var(--accent-blue); }}
/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .85rem;
    margin-bottom: 1rem;
}}
th {{
    text-align: left;
    padding: .65rem .75rem;
    background: var(--bg-secondary);
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: .7rem;
    letter-spacing: .06em;
    border-bottom: 2px solid var(--border);
}}
td {{
    padding: .6rem .75rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-primary);
    vertical-align: top;
}}
tr:hover td {{ background: var(--bg-highlight); }}
/* Timeline */
.timeline {{ position: relative; padding-left: 2rem; }}
.timeline::before {{
    content: '';
    position: absolute;
    left: .55rem;
    top: 0; bottom: 0;
    width: 2px;
    background: var(--border);
}}
.tl-item {{
    position: relative;
    margin-bottom: 1.25rem;
    padding: 1rem 1.25rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
}}
.tl-item::before {{
    content: '';
    position: absolute;
    left: -1.65rem;
    top: 1.2rem;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--accent-blue);
    border: 2px solid var(--bg-primary);
}}
.tl-item.tool_call::before {{ background: var(--accent-purple); }}
.tl-item.observe::before {{ background: var(--accent-cyan); }}
.tl-item.reason::before {{ background: var(--accent-yellow); }}
.tl-meta {{
    font-size: .75rem;
    color: var(--text-muted);
    margin-bottom: .35rem;
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}}
.tl-content {{ font-size: .85rem; white-space: pre-wrap; word-break: break-word; }}
.tl-hidden {{
    margin-top: .5rem;
    padding: .6rem .8rem;
    background: var(--bg-secondary);
    border-left: 3px solid var(--accent-red);
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: .8rem;
    color: var(--accent-red);
    white-space: pre-wrap;
    word-break: break-word;
}}
/* Anomalies */
.anomaly-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent-red);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: .75rem;
}}
.severity-bar {{
    display: inline-block;
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, var(--accent-green), var(--accent-yellow), var(--accent-red));
    position: relative;
    width: 80px;
    vertical-align: middle;
    margin-left: .5rem;
}}
.severity-dot {{
    position: absolute;
    top: -3px;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--text-primary);
    border: 2px solid var(--bg-card);
}}
.empty-state {{
    text-align: center;
    padding: 2rem;
    color: var(--text-muted);
    font-style: italic;
}}
pre.json {{
    background: var(--bg-secondary);
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: .8rem;
    color: var(--accent-cyan);
    border: 1px solid var(--border);
}}
footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-muted);
    font-size: .75rem;
}}
</style>
</head>
<body>
<h1>ASEF Evaluation Report</h1>
<p class="subtitle">Evaluation <code>{_safe(evaluation_id)}</code></p>

<h2>Overview</h2>
<div class="card-grid">
    <div class="card">
        <div class="kv"><span class="label">Type</span><span class="value">{eval_type}</span></div>
        <div class="kv"><span class="label">Status</span><span class="value"><span class="badge badge-{eval_status}">{eval_status}</span></span></div>
    </div>
    <div class="card">
        <div class="kv"><span class="label">Started</span><span class="value">{_safe(eval_started)}</span></div>
        <div class="kv"><span class="label">Completed</span><span class="value">{_safe(eval_completed)}</span></div>
    </div>
    <div class="card">
        <div class="kv"><span class="label">Actions</span><span class="value">{len(actions)}</span></div>
        <div class="kv"><span class="label">Metrics</span><span class="value">{len(metrics)}</span></div>
        <div class="kv"><span class="label">Anomalies</span><span class="value">{len(anomalies)}</span></div>
    </div>
</div>

<h3>Result Summary</h3>
<p>{eval_summary}</p>

<h3>Final Metrics</h3>
<pre class="json">{eval_metrics_json}</pre>

<h2>Agent Timeline</h2>
{timeline_html}

<h2>Metrics</h2>
{metrics_html}

<h2>Anomalies</h2>
{anomalies_html}

<footer>
    Generated by ASEF LogExporter &middot; {_safe(datetime.utcnow().isoformat(timespec='seconds'))} UTC
</footer>
</body>
</html>"""

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        return str(out.resolve())

    # ------------------------------------------------------------------
    # Multi-format export
    # ------------------------------------------------------------------

    async def export_all_formats(
        self, evaluation_id: str, output_dir: str
    ) -> dict[str, str]:
        """Export the evaluation to JSON, CSV, and HTML simultaneously.

        Files are named ``<evaluation_id>.<ext>`` inside *output_dir*.

        Args:
            evaluation_id: The evaluation to export.
            output_dir: Directory in which to place the files.

        Returns:
            Mapping of format name to absolute file path.
        """
        base = Path(output_dir)
        base.mkdir(parents=True, exist_ok=True)
        prefix = evaluation_id.replace("/", "_").replace("\\", "_")

        paths: dict[str, str] = {}
        paths["json"] = await self.export_json(
            evaluation_id, str(base / f"{prefix}.json")
        )
        paths["csv"] = await self.export_csv(
            evaluation_id, str(base / f"{prefix}.csv")
        )
        paths["html"] = await self.export_html(
            evaluation_id, str(base / f"{prefix}.html")
        )
        return paths

    # ------------------------------------------------------------------
    # HTML fragment helpers
    # ------------------------------------------------------------------

    def _format_timeline_html(self, actions: list[AgentActionRecord]) -> str:
        """Render agent actions as an interactive vertical timeline.

        Args:
            actions: Ordered list of action records.

        Returns:
            An HTML fragment string.
        """
        if not actions:
            return '<div class="empty-state">No agent actions recorded.</div>'

        items: list[str] = []
        for a in actions:
            hidden_block = ""
            if a.hidden_content:
                hidden_block = (
                    f'<div class="tl-hidden">'
                    f"🔒 Scratchpad\n{_safe(a.hidden_content)}</div>"
                )

            items.append(
                f'<div class="tl-item {_safe(a.action_type)}">'
                f'  <div class="tl-meta">'
                f"    <span>Turn {a.turn_number}</span>"
                f"    <span>{_safe(a.action_type)}</span>"
                f"    <span>{_dt_iso(a.timestamp)}</span>"
                f"    <span>Agent: {_safe(a.agent_id)}</span>"
                f"  </div>"
                f'  <div class="tl-content">{_safe(a.visible_content)}</div>'
                f"  {hidden_block}"
                f"</div>"
            )
        return f'<div class="timeline">{"".join(items)}</div>'

    def _format_metrics_table_html(self, metrics: list[MetricRecord]) -> str:
        """Render metrics as a styled HTML table.

        Args:
            metrics: List of metric records.

        Returns:
            An HTML fragment string.
        """
        if not metrics:
            return '<div class="empty-state">No metrics recorded.</div>'

        rows: list[str] = []
        for m in metrics:
            tag_str = ", ".join(
                f"{_safe(k)}={_safe(v)}" for k, v in (m.tags or {}).items()
            )
            rows.append(
                f"<tr>"
                f"<td>{_safe(m.metric_name)}</td>"
                f"<td>{m.metric_value:.4f}</td>"
                f"<td>{_safe(m.metric_type)}</td>"
                f"<td>{_dt_iso(m.timestamp)}</td>"
                f"<td>{tag_str}</td>"
                f"</tr>"
            )

        return (
            "<table>"
            "<thead><tr>"
            "<th>Metric</th><th>Value</th><th>Type</th><th>Timestamp</th><th>Tags</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )

    def _format_anomalies_html(self, anomalies: list[AnomalyRecord]) -> str:
        """Render anomaly records as styled cards with severity bars.

        Args:
            anomalies: List of anomaly records.

        Returns:
            An HTML fragment string.
        """
        if not anomalies:
            return '<div class="empty-state">No anomalies detected. ✅</div>'

        cards: list[str] = []
        for a in anomalies:
            pct = min(max(a.severity, 0.0), 1.0) * 100
            evidence_list = ""
            if a.evidence:
                evidence_items = "".join(
                    f"<li>{_safe(e)}</li>" for e in (a.evidence or [])
                )
                evidence_list = f"<ul>{evidence_items}</ul>"

            cards.append(
                f'<div class="anomaly-card">'
                f"  <h3>{_safe(a.anomaly_type)}"
                f'    <span class="severity-bar">'
                f'      <span class="severity-dot" style="left:{pct:.0f}%"></span>'
                f"    </span>"
                f"    <span style=\"color:var(--text-muted);font-size:.75rem\"> severity {a.severity:.2f}</span>"
                f"  </h3>"
                f'  <div class="tl-meta">'
                f"    <span>Agent: {_safe(a.agent_id)}</span>"
                f"    <span>{_dt_iso(a.timestamp)}</span>"
                f"  </div>"
                f"  {evidence_list}"
                f"</div>"
            )
        return "".join(cards)

    # ------------------------------------------------------------------
    # Internal serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _eval_dict(record: Any) -> dict[str, Any]:
        """Serialise an :class:`EvaluationRecord` to a plain dict."""
        return {
            "id": record.id,
            "evaluation_type": record.evaluation_type,
            "status": record.status,
            "started_at": _dt_iso(record.started_at),
            "completed_at": _dt_iso(record.completed_at),
            "config": record.config,
            "metrics": record.metrics,
            "result_summary": record.result_summary,
        }

    @staticmethod
    def _action_dict(record: AgentActionRecord) -> dict[str, Any]:
        """Serialise an :class:`AgentActionRecord` to a plain dict."""
        return {
            "id": record.id,
            "evaluation_id": record.evaluation_id,
            "agent_id": record.agent_id,
            "turn_number": record.turn_number,
            "action_type": record.action_type,
            "visible_content": record.visible_content,
            "hidden_content": record.hidden_content,
            "state": record.state,
            "timestamp": _dt_iso(record.timestamp),
            "metadata": record.metadata_json,
        }

    @staticmethod
    def _metric_dict(record: MetricRecord) -> dict[str, Any]:
        """Serialise a :class:`MetricRecord` to a plain dict."""
        return {
            "id": record.id,
            "evaluation_id": record.evaluation_id,
            "metric_name": record.metric_name,
            "metric_value": record.metric_value,
            "metric_type": record.metric_type,
            "timestamp": _dt_iso(record.timestamp),
            "tags": record.tags,
        }

    @staticmethod
    def _anomaly_dict(record: AnomalyRecord) -> dict[str, Any]:
        """Serialise an :class:`AnomalyRecord` to a plain dict."""
        return {
            "id": record.id,
            "evaluation_id": record.evaluation_id,
            "agent_id": record.agent_id,
            "anomaly_type": record.anomaly_type,
            "severity": record.severity,
            "evidence": record.evidence,
            "timestamp": _dt_iso(record.timestamp),
        }
