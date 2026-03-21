'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { getField } from '@/lib/api';
import { useZones } from '@/hooks/useZones';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { Field, Zone, Recommendation } from '@/types/api';
import { DEFAULT_CENTER, DEFAULT_ZOOM } from '@/lib/mapbox';
import ActionQueue from '@/app/sidebar/ActionQueue';
import ZoneDetailPanel from '@/app/panels/ZoneDetailPanel';
import AgentTraceModal from '@/app/sidebar/AgentTraceModal';
import Toast from '@/app/ui/Toast';

const FieldMap = dynamic(() => import('@/components/map/FieldMap'), { ssr: false });
const ZoneLayer = dynamic(() => import('@/components/map/ZoneLayer'), { ssr: false });
const ZoneTooltip = dynamic(() => import('@/components/map/ZoneTooltip'), { ssr: false });
const UrgencyPulse = dynamic(() => import('@/components/map/UrgencyPulse'), { ssr: false });

export default function DashboardPage() {
  const { field_id } = useParams<{ field_id: string }>();
  const [field, setField] = useState<Field | null>(null);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);
  const [activeRec, setActiveRec] = useState<Recommendation | null>(null);

  const { data: zones = [] } = useZones(field_id);
  const { recommendations, criticalToast, clearToast } = useRecommendations(field_id);

  useEffect(() => {
    if (!field_id) return;
    getField(field_id).then(setField).catch(console.error);
  }, [field_id]);

  const center: [number, number] = field
    ? (field.polygon.coordinates[0][0] as [number, number])
    : DEFAULT_CENTER;

  return (
    <div className="flex flex-col md:flex-row h-screen w-screen overflow-hidden bg-gray-950">
      {/* Map — 65% on desktop, full width on mobile */}
      <div className="w-full h-[50vh] md:h-screen md:w-[65%] relative">
        <FieldMap center={center} zoom={DEFAULT_ZOOM}>
          <ZoneLayer fieldId={field_id} onZoneSelect={setSelectedZone} />
          <ZoneTooltip fieldId={field_id} />
          <UrgencyPulse recommendations={recommendations} zones={zones} />
        </FieldMap>
      </div>

      {/* Sidebar — 35% on desktop, stacks below on mobile */}
      <div className="w-full md:w-[35%] h-[50vh] md:h-screen flex flex-col overflow-hidden border-l border-gray-800">
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-800 shrink-0">
          <h1 className="text-sm font-semibold text-white">
            {field ? field.name : 'Loading…'}
          </h1>
          {field && (
            <p className="text-xs text-gray-400 mt-0.5">
              {field.crop_type.charAt(0).toUpperCase() + field.crop_type.slice(1)} · Planted{' '}
              {new Date(field.planting_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          )}
        </div>

        {/* Action queue */}
        <ActionQueue fieldId={field_id} onWhyClick={setActiveRec} />

        {/* Zone detail panel */}
        {selectedZone && (
          <ZoneDetailPanel zone={selectedZone} onClose={() => setSelectedZone(null)} />
        )}
      </div>

      {/* Agent trace modal */}
      {activeRec && (
        <AgentTraceModal fieldId={field_id} onClose={() => setActiveRec(null)} />
      )}

      {/* Critical toast */}
      {criticalToast && (
        <div className="fixed bottom-4 right-4 z-50">
          <Toast message={criticalToast} onDismiss={clearToast} />
        </div>
      )}
    </div>
  );
}
