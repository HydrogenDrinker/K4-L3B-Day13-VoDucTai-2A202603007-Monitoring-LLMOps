from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    k = (len(values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return round(float(d0 + d1), 2)


@router.get("/api/dashboard-data")
async def get_dashboard_data() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue

    # Filter last 60 minutes or all records
    req_received = [r for r in records if r.get("event") == "request_received"]
    req_failed = [r for r in records if r.get("event") == "request_failed"]
    resp_sent = [r for r in records if r.get("event") == "response_sent"]

    # Latencies
    latencies = sorted([float(r["latency_ms"]) for r in resp_sent if "latency_ms" in r])
    ttfts = sorted([float(r["ttft_ms"]) for r in resp_sent if "ttft_ms" in r])
    p50_lat = _percentile(latencies, 50)
    p95_lat = _percentile(latencies, 95)
    p99_lat = _percentile(latencies, 99)
    p95_ttft = _percentile(ttfts, 95)

    # Traffic
    total_reqs = len(req_received)
    # Errors
    err_rate = round((len(req_failed) / total_reqs * 100), 2) if total_reqs > 0 else 0.0
    tool_events = [r for r in records if r.get("tool_success") is not None]
    tool_successes = [r for r in tool_events if r.get("tool_success") is True]
    tool_success_rate = (
        round(len(tool_successes) / len(tool_events) * 100, 2) if tool_events else 100.0
    )

    # Cost
    total_cost = round(sum(float(r.get("cost_usd", 0.0)) for r in resp_sent), 4)

    # Tokens
    tokens_in = sum(int(r.get("tokens_in", 0)) for r in resp_sent)
    tokens_out = sum(int(r.get("tokens_out", 0)) for r in resp_sent)

    # Quality
    qualities = [float(r["quality_score"]) for r in resp_sent if "quality_score" in r]
    avg_quality = round(sum(qualities) / len(qualities), 3) if qualities else 0.0

    return {
        "summary": {
            "p50_lat": p50_lat,
            "p95_lat": p95_lat,
            "p99_lat": p99_lat,
            "p95_ttft": p95_ttft,
            "total_reqs": total_reqs,
            "err_rate": err_rate,
            "tool_success_rate": tool_success_rate,
            "total_cost": total_cost,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "avg_quality": avg_quality,
        },
        "records_count": len(records),
        "latencies": latencies,
        "ttfts": ttfts,
        "time_series": [
            {
                "ts": r.get("ts", "")[11:19],
                "event": r.get("event"),
                "latency_ms": r.get("latency_ms"),
                "correlation_id": r.get("correlation_id"),
                "cost_usd": r.get("cost_usd"),
                "tokens": (r.get("tokens_in", 0) + r.get("tokens_out", 0)) if r.get("event") == "response_sent" else 0,
            }
            for r in records[-50:]
        ],
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #38bdf8;
      --accent: #818cf8;
      --warning: #f59e0b;
      --danger: #ef4444;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px; }
    header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    h1 { font-size: 24px; font-weight: 700; color: #fff; }
    .badge { background: #0369a1; color: #e0f2fe; padding: 4px 12px; border-radius: 999px; font-size: 13px; }
    .meta { display: flex; gap: 16px; color: var(--muted); font-size: 14px; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; min-height: 280px; }
    .card-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
    .card-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }
    .threshold { font-size: 12px; color: var(--warning); background: rgba(245, 158, 11, 0.1); padding: 2px 8px; border-radius: 4px; }
    .stat-row { display: flex; gap: 16px; margin-bottom: 12px; }
    .stat-val { font-size: 22px; font-weight: 700; color: var(--primary); }
    .stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; }
    .chart-container { flex: 1; position: relative; width: 100%; min-height: 160px; }
    footer { margin-top: 24px; text-align: center; color: var(--muted); font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
      <p style="color: var(--muted); font-size: 13px; margin-top: 4px;">Service: day13-l3b-monitoring-llmops-lab | Time Range: Last 60m | Refresh: 30s</p>
    </div>
    <div class="meta">
      <span class="badge" id="status-badge">Live: data/logs.jsonl</span>
      <span id="last-updated">Updating...</span>
    </div>
  </header>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="card" id="panel-latency">
      <div class="card-header">
        <div class="card-title">1. Latency Percentiles & TTFT</div>
        <div class="threshold">Threshold: P95 ≤ 3000ms</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-p50">-</div><div class="stat-label">P50 (ms)</div></div>
        <div><div class="stat-val" id="val-p95">-</div><div class="stat-label">P95 (ms)</div></div>
        <div><div class="stat-val" id="val-p99">-</div><div class="stat-label">P99 (ms)</div></div>
        <div><div class="stat-val" id="val-ttft" style="color: var(--accent);">-</div><div class="stat-label">TTFT P95</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-latency"></canvas></div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="card" id="panel-traffic">
      <div class="card-header">
        <div class="card-title">2. Request Traffic</div>
        <div class="threshold">Threshold: Rate ≥ 1 rpm</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-traffic">-</div><div class="stat-label">Total Requests</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-traffic"></canvas></div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="card" id="panel-errors">
      <div class="card-header">
        <div class="card-title">3. Error Rate & Retrieval Success</div>
        <div class="threshold">Threshold: Error ≤ 2%</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-err-rate">-</div><div class="stat-label">Error Rate (%)</div></div>
        <div><div class="stat-val" id="val-tool-success" style="color: var(--success);">-</div><div class="stat-label">Retrieval Success (%)</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-errors"></canvas></div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="card" id="panel-cost">
      <div class="card-header">
        <div class="card-title">4. Cost Over Time</div>
        <div class="threshold">Threshold: Total ≤ $2.50</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-cost">-</div><div class="stat-label">Total Cost ($ USD)</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-cost"></canvas></div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="card" id="panel-tokens">
      <div class="card-header">
        <div class="card-title">5. Input & Output Tokens</div>
        <div class="threshold">Threshold: Sum ≤ 50,000</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-tokens-in">-</div><div class="stat-label">Tokens In</div></div>
        <div><div class="stat-val" id="val-tokens-out">-</div><div class="stat-label">Tokens Out</div></div>
        <div><div class="stat-val" id="val-tokens-total" style="color: var(--accent);">-</div><div class="stat-label">Total Tokens</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-tokens"></canvas></div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="card" id="panel-quality">
      <div class="card-header">
        <div class="card-title">6. Quality Proxy</div>
        <div class="threshold">Threshold: Mean ≥ 0.75</div>
      </div>
      <div class="stat-row">
        <div><div class="stat-val" id="val-quality">-</div><div class="stat-label">Avg Quality Score (0-1)</div></div>
      </div>
      <div class="chart-container"><canvas id="chart-quality"></canvas></div>
    </div>
  </div>

  <footer>
    Contract compliant with config/dashboard.yaml | Student: Vo Duc Tai (2A202603007)
  </footer>

  <script>
    let latencyChart, trafficChart, errorsChart, costChart, tokensChart, qualityChart;

    async function loadData() {
      try {
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();
        const s = data.summary;

        document.getElementById('val-p50').textContent = s.p50_lat + ' ms';
        document.getElementById('val-p95').textContent = s.p95_lat + ' ms';
        document.getElementById('val-p99').textContent = s.p99_lat + ' ms';
        document.getElementById('val-ttft').textContent = s.p95_ttft + ' ms';

        document.getElementById('val-traffic').textContent = s.total_reqs;
        document.getElementById('val-err-rate').textContent = s.err_rate + '%';
        document.getElementById('val-tool-success').textContent = s.tool_success_rate + '%';
        document.getElementById('val-cost').textContent = '$' + s.total_cost.toFixed(4);
        document.getElementById('val-tokens-in').textContent = s.tokens_in.toLocaleString();
        document.getElementById('val-tokens-out').textContent = s.tokens_out.toLocaleString();
        document.getElementById('val-tokens-total').textContent = (s.tokens_in + s.tokens_out).toLocaleString();
        document.getElementById('val-quality').textContent = s.avg_quality.toFixed(2);
        document.getElementById('last-updated').textContent = 'Last refreshed: ' + new Date().toLocaleTimeString();

        renderCharts(data);
      } catch (e) {
        console.error("Dashboard refresh error:", e);
      }
    }

    function renderCharts(data) {
      const ts = data.time_series || [];
      const labels = ts.map(t => t.ts || '');
      const latData = ts.map(t => t.latency_ms || 0);

      // Latency Chart
      if (!latencyChart) {
        latencyChart = new Chart(document.getElementById('chart-latency'), {
          type: 'line',
          data: {
            labels: labels,
            datasets: [{
              label: 'Latency (ms)',
              data: latData,
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              fill: true,
              tension: 0.2
            }, {
              label: 'SLO Threshold (3000ms)',
              data: Array(labels.length).fill(3000),
              borderColor: '#f59e0b',
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false
            }]
          },
          options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#334155' } }, x: { grid: { color: '#1e293b' } } } }
        });
      } else {
        latencyChart.data.labels = labels;
        latencyChart.data.datasets[0].data = latData;
        latencyChart.data.datasets[1].data = Array(labels.length).fill(3000);
        latencyChart.update();
      }

      // Traffic Bar
      if (!trafficChart) {
        trafficChart = new Chart(document.getElementById('chart-traffic'), {
          type: 'bar',
          data: {
            labels: ['Requests Received'],
            datasets: [{ label: 'Total', data: [data.summary.total_reqs], backgroundColor: '#38bdf8' }]
          },
          options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#334155' } } } }
        });
      } else {
        trafficChart.data.datasets[0].data = [data.summary.total_reqs];
        trafficChart.update();
      }

      // Errors Donut
      if (!errorsChart) {
        errorsChart = new Chart(document.getElementById('chart-errors'), {
          type: 'doughnut',
          data: {
            labels: ['Success', 'Errors'],
            datasets: [{ data: [100 - data.summary.err_rate, data.summary.err_rate], backgroundColor: ['#10b981', '#ef4444'] }]
          },
          options: { responsive: true, maintainAspectRatio: false }
        });
      } else {
        errorsChart.data.datasets[0].data = [100 - data.summary.err_rate, data.summary.err_rate];
        errorsChart.update();
      }

      // Cost Chart
      const costData = ts.map(t => t.cost_usd || 0);
      if (!costChart) {
        costChart = new Chart(document.getElementById('chart-cost'), {
          type: 'line',
          data: {
            labels: labels,
            datasets: [{ label: 'Cost ($ USD)', data: costData, borderColor: '#10b981', tension: 0.2 }]
          },
          options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#334155' } } } }
        });
      } else {
        costChart.data.labels = labels;
        costChart.data.datasets[0].data = costData;
        costChart.update();
      }

      // Tokens Chart
      if (!tokensChart) {
        tokensChart = new Chart(document.getElementById('chart-tokens'), {
          type: 'bar',
          data: {
            labels: ['Tokens In', 'Tokens Out'],
            datasets: [{ label: 'Tokens', data: [data.summary.tokens_in, data.summary.tokens_out], backgroundColor: ['#38bdf8', '#818cf8'] }]
          },
          options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#334155' } } } }
        });
      } else {
        tokensChart.data.datasets[0].data = [data.summary.tokens_in, data.summary.tokens_out];
        tokensChart.update();
      }

      // Quality Chart
      if (!qualityChart) {
        qualityChart = new Chart(document.getElementById('chart-quality'), {
          type: 'doughnut',
          data: {
            labels: ['Score', 'Remaining'],
            datasets: [{ data: [data.summary.avg_quality, Math.max(0, 1 - data.summary.avg_quality)], backgroundColor: ['#818cf8', '#334155'] }]
          },
          options: { responsive: true, maintainAspectRatio: false }
        });
      } else {
        qualityChart.data.datasets[0].data = [data.summary.avg_quality, Math.max(0, 1 - data.summary.avg_quality)];
        qualityChart.update();
      }
    }

    loadData();
    setInterval(loadData, 10000);
  </script>
</body>
</html>"""
