'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { listFields, triggerAnalysis, deleteField } from '@/lib/api';
import { useTodos } from '@/hooks/useTodos';
import { MAPBOX_TOKEN } from '@/lib/mapbox';
import type { Field } from '@/types/api';

// Compute centroid of a GeoJSON polygon
function fieldCenter(field: Field): [number, number] {
  const coords = field.polygon.coordinates[0] as [number, number][];
  const n = coords.length - 1;
  const lng = coords.slice(0, n).reduce((s, c) => s + c[0], 0) / n;
  const lat = coords.slice(0, n).reduce((s, c) => s + c[1], 0) / n;
  return [lng, lat];
}

// Mapbox Static Image thumbnail URL (satellite-streets style)
function thumbnailUrl(field: Field): string {
  const [lng, lat] = fieldCenter(field);
  const token = MAPBOX_TOKEN;
  return `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/static/${lng},${lat},14/320x180@2x?access_token=${token}`;
}

const URGENCY_COLOR: Record<string, string> = {
  critical: 'text-red-400 bg-red-950/40 border-red-500/30',
  high: 'text-orange-400 bg-orange-950/40 border-orange-500/30',
  medium: 'text-blue-400 bg-blue-950/40 border-blue-500/30',
  low: 'text-gray-400 bg-gray-800/40 border-gray-600/30',
};

export default function FieldsDashboard() {
  const router = useRouter();
  const [fields, setFields] = useState<Field[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTodos, setShowTodos] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const { pending, todos, markDone } = useTodos();

  useEffect(() => {
    listFields().then(setFields).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function handleDelete(e: React.MouseEvent, fieldId: string) {
    e.stopPropagation();
    if (!confirm('Delete this field and all its data? This cannot be undone.')) return;
    setDeletingId(fieldId);
    try {
      await deleteField(fieldId);
      setFields(prev => prev.filter(f => f.id !== fieldId));
    } catch {
      alert('Failed to delete field.');
    } finally {
      setDeletingId(null);
    }
  }

  async function openField(field: Field) {
    // Trigger a fresh analysis in the background, then navigate
    triggerAnalysis(field.id).catch(() => {});
    router.push(`/dashboard/${field.id}`);
  }

  return (
    <div className="min-h-screen w-full" style={{ backgroundColor: '#0d1117' }}>
      {/* ── Top bar ── */}
      <div className="border-b border-[#2a3045] px-6 py-4 flex items-center justify-between" style={{ backgroundColor: '#0d1117' }}>
        <div className="flex items-center gap-3">
          <span className="text-green-400 text-xl">◈</span>
          <span className="text-white font-bold text-lg tracking-tight">ReHarvestAI</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Notification bell */}
          <button
            onClick={() => setShowTodos(v => !v)}
            className="relative p-2 rounded-lg border border-[#2a3045] hover:border-gray-600 transition-colors"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-gray-400">
              <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
            </svg>
            {pending.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[9px] font-bold text-white flex items-center justify-center">
                {pending.length > 9 ? '9+' : pending.length}
              </span>
            )}
          </button>
          <Link
            href="/onboarding"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-semibold transition-colors"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
              <path d="M8 2v12M2 8h12" strokeLinecap="round" />
            </svg>
            New field
          </Link>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* ── Todos panel (collapsible) ── */}
        {showTodos && (
          <div className="mb-8 rounded-xl border border-[#2a3045] overflow-hidden" style={{ backgroundColor: '#111827' }}>
            <div className="px-5 py-3 border-b border-[#2a3045] flex items-center justify-between">
              <span className="text-sm font-semibold text-white">Action queue</span>
              <span className="text-xs text-gray-500">{pending.length} pending</span>
            </div>
            {todos.length === 0 ? (
              <p className="px-5 py-6 text-sm text-gray-500 text-center">No tasks yet. Accept AI recommendations to add them here.</p>
            ) : (
              <div className="divide-y divide-[#2a3045]">
                {todos.map(todo => (
                  <div key={todo.id} className={`px-5 py-3 flex items-center gap-4 ${todo.status === 'done' ? 'opacity-40' : ''}`}>
                    <div className={`shrink-0 px-2 py-0.5 rounded border text-[10px] font-semibold uppercase ${URGENCY_COLOR[todo.urgency] ?? URGENCY_COLOR.medium}`}>
                      {todo.urgency}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white font-medium truncate">{todo.action_type} — {todo.zone_label}</p>
                      <p className="text-xs text-gray-500 truncate">{todo.field_name}</p>
                    </div>
                    {todo.status === 'pending' && (
                      <button
                        onClick={() => markDone(todo.id)}
                        className="shrink-0 text-xs px-3 py-1.5 rounded-lg border border-green-700 text-green-400 hover:bg-green-900/30 transition-colors"
                      >
                        Mark done
                      </button>
                    )}
                    {todo.status === 'done' && (
                      <span className="shrink-0 text-xs text-gray-600">Done</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Page header ── */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-1">My Fields</h1>
          <p className="text-sm text-gray-500">{fields.length} field{fields.length !== 1 ? 's' : ''} monitored</p>
        </div>

        {/* ── Fields grid ── */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="rounded-xl border border-[#2a3045] overflow-hidden animate-pulse" style={{ backgroundColor: '#111827' }}>
                <div className="h-40 bg-gray-800" />
                <div className="p-4 space-y-2">
                  <div className="h-3 bg-gray-700 rounded w-2/3" />
                  <div className="h-2 bg-gray-800 rounded w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : fields.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-2xl border border-[#2a3045] flex items-center justify-center mb-4" style={{ backgroundColor: '#111827' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-7 h-7 text-gray-600">
                <path d="M9 20.25H5.25A2.25 2.25 0 013 18V5.25A2.25 2.25 0 015.25 3h13.5A2.25 2.25 0 0121 5.25V9" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M15 13.5L18 16.5 21 13.5M18 10.5v6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">No fields yet</h2>
            <p className="text-sm text-gray-500 mb-6 max-w-xs">Draw your first field on the map to start getting AI-powered harvest recommendations.</p>
            <Link
              href="/onboarding"
              className="px-6 py-3 bg-green-600 hover:bg-green-500 text-white font-semibold rounded-xl text-sm transition-colors"
            >
              Create your first field
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {fields.map(field => {
              const fieldTodos = pending.filter(t => t.field_id === field.id);
              return (
                <button
                  key={field.id}
                  onClick={() => openField(field)}
                  className="text-left rounded-xl border border-[#2a3045] overflow-hidden hover:border-green-700/60 hover:shadow-lg hover:shadow-green-900/10 transition-all group"
                  style={{ backgroundColor: '#111827' }}
                >
                  {/* Thumbnail */}
                  <div className="relative h-40 overflow-hidden bg-gray-900">
                    <img
                      src={thumbnailUrl(field)}
                      alt={field.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                    {/* Delete button */}
                    <button
                      onClick={e => handleDelete(e, field.id)}
                      disabled={deletingId === field.id}
                      className="absolute top-2 left-2 p-1.5 rounded-lg bg-gray-900/70 backdrop-blur-sm text-gray-400 hover:text-red-400 hover:bg-red-950/70 transition-colors opacity-0 group-hover:opacity-100"
                      title="Delete field"
                    >
                      {deletingId === field.id ? (
                        <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10" strokeOpacity=".25"/><path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round"/>
                        </svg>
                      ) : (
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                          <path d="M3 4h10M6 4V2.5h4V4M5 4l.5 9h5L11 4" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </button>
                    {/* Todo badge */}
                    {fieldTodos.length > 0 && (
                      <div className="absolute top-2 right-2 px-2 py-1 bg-red-600/90 rounded-lg text-[10px] font-bold text-white backdrop-blur-sm">
                        {fieldTodos.length} action{fieldTodos.length > 1 ? 's' : ''} pending
                      </div>
                    )}
                  </div>
                  {/* Card body */}
                  <div className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-semibold text-white group-hover:text-green-400 transition-colors">{field.name}</h3>
                        <p className="text-xs text-gray-500 mt-0.5 capitalize">{field.crop_type} · planted {new Date(field.planting_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
                      </div>
                      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4 text-gray-600 group-hover:text-green-500 shrink-0 mt-0.5 transition-colors">
                        <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <p className="text-[10px] text-gray-600 mt-2">{new Date(field.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
