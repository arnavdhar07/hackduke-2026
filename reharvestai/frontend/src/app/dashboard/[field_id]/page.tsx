'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { getField, estimatedRevenueAtRisk } from '@/lib/api';
import { useZones } from '@/hooks/useZones';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { Field, Zone, Recommendation } from '@/types/api';
import { DEFAULT_CENTER, DEFAULT_ZOOM } from '@/lib/mapbox';
import { ndviColor } from '@/lib/colors';
import ActionQueue from '@/app/sidebar/ActionQueue';
import ZoneSparklines from '@/app/ui/ZoneSparklines';
import ZoneDetailPanel from '@/app/panels/ZoneDetailPanel';
import Toast from '@/app/ui/Toast';

const FieldMap = dynamic(() => import('@/components/map/FieldMap'), { ssr: false });
const ZoneLayer = dynamic(() => import('@/components/map/ZoneLayer'), { ssr: false });
const ZoneTooltip = dynamic(() => import('@/components/map/ZoneTooltip'), { ssr: false });
const UrgencyPulse = dynamic(() => import('@/components/map/UrgencyPulse'), { ssr: false });

// ─── Field health donut (pure SVG) ───────────────────────────────────────────

function FieldHealthDonut({ zones }: { zones: Zone[] }) {
  if (!zones.length) return null;
  const bands = [
    { color: '#16a34a', count: zones.filter(z => z.latest_scores.ndvi >= 80).length },
    { color: '#84cc16', count: zones.filter(z => z.latest_scores.ndvi >= 65 && z.latest_scores.ndvi < 80).length },
    { color: '#f59e0b', count: zones.filter(z => z.latest_scores.ndvi >= 40 && z.latest_scores.ndvi < 65).length },
    { color: '#ef4444', count: zones.filter(z => z.latest_scores.ndvi < 40).length },
  ].filter(b => b.count > 0);

  const total = zones.length;
  const R = 17, r = 10, cx = 20, cy = 20;
  let angle = -Math.PI / 2;
  const arcs = bands.map((b, i) => {
    const sweep = (b.count / total) * 2 * Math.PI;
    const end = angle + sweep;
    const large = sweep > Math.PI ? 1 : 0;
    const x1 = cx + R * Math.cos(angle), y1 = cy + R * Math.sin(angle);
    const x2 = cx + R * Math.cos(end),   y2 = cy + R * Math.sin(end);
    const ix1 = cx + r * Math.cos(angle), iy1 = cy + r * Math.sin(angle);
    const ix2 = cx + r * Math.cos(end),   iy2 = cy + r * Math.sin(end);
    const d = `M${x1} ${y1} A${R} ${R} 0 ${large} 1 ${x2} ${y2} L${ix2} ${iy2} A${r} ${r} 0 ${large} 0 ${ix1} ${iy1}Z`;
    angle = end;
    return <path key={i} d={d} fill={b.color} />;
  });

  return (
    <svg width="40" height="40" viewBox="0 0 40 40" title="Zone health breakdown">
      {arcs}
      <circle cx={cx} cy={cy} r={r - 1} fill="#0f1117" />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontSize="8" fill="white" fontWeight="bold">{total}</text>
    </svg>
  );
}

// ─── Inline stat pill for the top bar ────────────────────────────────────────

function StatPill({
  label,
  value,
  accent,
  critical,
}: {
  label: string;
  value: string | number;
  accent?: string;
  critical?: boolean;
}) {
  return (
    <div className={`flex flex-col items-center px-3 py-1 rounded-lg border ${
      critical ? 'bg-red-950/20 border-red-500/20' : 'border-[#2a3045] bg-[#1a1f2e]'
    }`}>
      <span className={`text-base font-bold leading-none ${accent ?? 'text-white'}`}>{value}</span>
      <span className="text-[10px] text-gray-400 mt-0.5 whitespace-nowrap">{label}</span>
    </div>
  );
}

// ─── Export report ────────────────────────────────────────────────────────────

function exportReport(field: Field, zones: Zone[], recommendations: Recommendation[]) {
  const accepted = recommendations.filter(r => r.status === 'accepted');
  const critical = recommendations.filter(r => r.urgency === 'critical');
  const avgNdvi = zones.length
    ? Math.round(zones.reduce((s, z) => s + z.latest_scores.ndvi, 0) / zones.length)
    : 'N/A';

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ReHarvestAI Field Report — ${field.name}</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; color: #111; }
  h1 { color: #16a34a; } h2 { border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; background: #f3f4f6; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #f3f4f6; }
  .badge { display:inline-block; padding:2px 8px; border-radius:9999px; font-size:11px; font-weight:600; }
  .critical { background:#fee2e2; color:#991b1b; }
  .high { background:#ffedd5; color:#9a3412; }
  .medium { background:#dbeafe; color:#1e40af; }
  .low { background:#f3f4f6; color:#374151; }
  footer { margin-top:40px; font-size:11px; color:#9ca3af; }
</style></head><body>
<h1>ReHarvestAI — Field Report</h1>
<p><strong>Field:</strong> ${field.name} &nbsp;|&nbsp; <strong>Crop:</strong> ${field.crop_type} &nbsp;|&nbsp;
<strong>Planted:</strong> ${new Date(field.planting_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })} &nbsp;|&nbsp;
<strong>Report date:</strong> ${new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>

<h2>Field Summary</h2>
<table><tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total zones</td><td>${zones.length}</td></tr>
<tr><td>Average NDVI</td><td>${avgNdvi}</td></tr>
<tr><td>Critical zones</td><td>${critical.length}</td></tr>
<tr><td>Recommendations accepted</td><td>${accepted.length}</td></tr>
</table>

<h2>Zone Health</h2>
<table><tr><th>Zone</th><th>NDVI</th><th>NDWI</th><th>NDRE</th><th>Captured</th></tr>
${zones.map(z => `<tr><td>${z.label}</td><td>${z.latest_scores.ndvi}</td><td>${z.latest_scores.ndwi}</td><td>${z.latest_scores.ndre}</td>
<td>${new Date(z.latest_scores.captured_at).toLocaleDateString()}</td></tr>`).join('')}
</table>

<h2>Recommendations</h2>
<table><tr><th>Zone</th><th>Action</th><th>Urgency</th><th>Confidence</th><th>Status</th></tr>
${recommendations.map(r => `<tr><td>${r.zone_label}</td><td>${r.action_type}</td>
<td><span class="badge ${r.urgency}">${r.urgency}</span></td>
<td>${Math.round(r.confidence * 100)}%</td><td>${r.status}</td></tr>`).join('')}
</table>

<footer>Generated by ReHarvestAI · ${new Date().toISOString()}</footer>
</body></html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `reharvestai-report-${field.name.toLowerCase().replace(/\s+/g, '-')}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { field_id } = useParams<{ field_id: string }>();
  const [field, setField] = useState<Field | null>(null);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);

  const { data: zones = [] } = useZones(field_id);
  const { recommendations, criticalToast, clearToast } = useRecommendations(field_id);

  useEffect(() => {
    if (!field_id) return;
    getField(field_id).then(setField).catch(console.error);
  }, [field_id]);

  const center: [number, number] = field
    ? (field.polygon.coordinates[0][0] as [number, number])
    : DEFAULT_CENTER;

  // ── Computed header stats ─────────────────────────────────────────────────
  const criticalCount = recommendations.filter(r => r.urgency === 'critical' && r.status === 'pending').length;
  const avgNdvi = zones.length
    ? Math.round(zones.reduce((s, z) => s + z.latest_scores.ndvi, 0) / zones.length)
    : null;
  const daysSincePass = zones.length
    ? Math.floor((Date.now() - new Date(zones[0].latest_scores.captured_at).getTime()) / 86_400_000)
    : null;

  // Total revenue at risk for pending recommendations
  const totalRevAtRisk = recommendations
    .filter(r => r.status === 'pending')
    .reduce((sum, rec) => sum + estimatedRevenueAtRisk(
      rec.estimated_yield_bushels ?? 0,
      field?.crop_type ?? '',
      rec.confidence
    ), 0);

  // Waste reduction: accepted recs × rough tonnes saved per action
  const acceptedCount = recommendations.filter(r => r.status === 'accepted').length;
  const estTonnesSaved = +(acceptedCount * 3.2).toFixed(1);


  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-gray-950">

      {/* ── Full-width top bar ──────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-[#2a3045] px-4 py-2.5" style={{ backgroundColor: '#0d1117' }}>
        <div className="flex items-center justify-center gap-3">

          {/* Farm identity */}
          <div className="flex items-center gap-3 shrink-0">
            <FieldHealthDonut zones={zones} />
            <div>
              <h1 className="text-base font-bold text-white leading-tight flex items-center gap-1.5">
                <span className="text-green-400">●</span>
                {field ? field.name : 'Loading…'}
              </h1>
              {field && (
                <p className="text-xs text-gray-400">
                  {zones.length} zones · {field.crop_type.charAt(0).toUpperCase() + field.crop_type.slice(1)}
                </p>
              )}
            </div>
          </div>

          <div className="w-px h-10 bg-[#2a3045] shrink-0" />

          {/* Stat pills */}
          <div className="flex items-center gap-2 shrink-0">
            <StatPill label="Zones" value={zones.length || '—'} />
            <StatPill
              label="Critical"
              value={criticalCount}
              accent={criticalCount > 0 ? 'text-red-400' : 'text-white'}
              critical={criticalCount > 0}
            />
            <StatPill
              label="Avg NDVI"
              value={avgNdvi ?? '—'}
              accent={
                avgNdvi === null ? 'text-white'
                  : avgNdvi < 40 ? 'text-red-400'
                  : avgNdvi < 65 ? 'text-amber-400'
                  : avgNdvi < 80 ? 'text-lime-400'
                  : 'text-green-400'
              }
            />
            <StatPill
              label="Last Pass"
              value={daysSincePass !== null ? `${daysSincePass}d` : '—'}
              accent={daysSincePass !== null && daysSincePass > 4 ? 'text-amber-400' : 'text-gray-300'}
            />
            {totalRevAtRisk > 0 && (
              <StatPill
                label="$ at risk"
                value={`$${(totalRevAtRisk / 1000).toFixed(1)}k`}
                accent="text-red-400"
                critical
              />
            )}
          </div>

          {/* Actions pushed right */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => field && exportReport(field, zones, recommendations)}
              disabled={!field}
              title="Export report"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-green-600 text-green-400 hover:bg-green-900/30 transition-colors disabled:opacity-30 text-xs font-medium"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M3 10v3h10v-3M8 2v7M5 6l3 3 3-3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Export
            </button>
            <span className="text-[10px] px-2 py-1 rounded-full border border-green-800 text-green-400 bg-green-950/40 font-medium">LIVE</span>
          </div>
        </div>
      </div>

      {/* ── Data freshness warning ──────────────────────────────────────────── */}
      {daysSincePass !== null && daysSincePass >= 7 && (
        <div className={`shrink-0 px-4 py-2 flex items-center gap-2 text-xs ${
          daysSincePass >= 14
            ? 'bg-red-950/40 border-b border-red-500/20 text-red-300'
            : 'bg-amber-950/40 border-b border-amber-500/20 text-amber-300'
        }`}>
          <span>{daysSincePass >= 14 ? '⚠️' : '⚠'}</span>
          <span>
            Satellite imagery is <strong>{daysSincePass} days old</strong>
            {daysSincePass >= 14
              ? ' — recommendations may be significantly less accurate. Cloud cover may be blocking new observations.'
              : ' — check back soon for updated imagery.'}
          </span>
        </div>
      )}

      {/* ── Map + sidebar row ───────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0">

        {/* Map */}
        <div className="flex-1 relative">
          <FieldMap center={center} zoom={DEFAULT_ZOOM}>
            <ZoneLayer fieldId={field_id} onZoneSelect={setSelectedZone} selectedZoneId={selectedZone?.id} />
            <ZoneTooltip fieldId={field_id} />
            <UrgencyPulse recommendations={recommendations} zones={zones} />
          </FieldMap>
        </div>

        {/* Sidebar */}
        <div
          className="w-[35%] flex flex-col overflow-hidden border-l border-[#2a3045]"
          style={{ backgroundColor: '#0f1117' }}
        >
          {/* Scrollable area */}
          <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
            <ActionQueue
              fieldId={field_id}
              cropType={field?.crop_type}
              fieldName={field?.name}
            />

            {selectedZone && (
              <ZoneDetailPanel zone={selectedZone} onClose={() => setSelectedZone(null)} />
            )}
          </div>

          {/* Fixed bottom sparklines */}
          <ZoneSparklines zones={zones} />
        </div>
      </div>

      {/* Critical toast */}
      {criticalToast && (
        <div className="fixed bottom-4 right-4 z-50">
          <Toast message={criticalToast} onDismiss={clearToast} />
        </div>
      )}
    </div>
  );
}
