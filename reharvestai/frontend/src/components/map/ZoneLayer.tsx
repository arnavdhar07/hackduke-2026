'use client';

import { useEffect, useRef } from 'react';
import { useMap } from './FieldMap';
import { useZones } from '@/hooks/useZones';
import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneLayerProps {
  fieldId: string;
  onZoneSelect: (zone: Zone) => void;
  selectedZoneId?: string;
}

function centroid(polygon: GeoJSON.Polygon): [number, number] {
  const coords = polygon.coordinates[0];
  const len = coords.length - 1;
  const lng = coords.slice(0, len).reduce((s, c) => s + c[0], 0) / len;
  const lat = coords.slice(0, len).reduce((s, c) => s + c[1], 0) / len;
  return [lng, lat];
}

export default function ZoneLayer({ fieldId, onZoneSelect, selectedZoneId }: ZoneLayerProps) {
  const map = useMap();
  const { data: zones } = useZones(fieldId);
  const zonesRef = useRef<Zone[]>([]);
  const hasFitRef = useRef(false);

  // Add zone fill/outline/label layers once when map + zones are ready
  useEffect(() => {
    if (!map || !zones) return;
    zonesRef.current = zones;

    // ── Per-zone fill + outline layers ──────────────────────────────────────
    zones.forEach((zone) => {
      if (!map.getSource(zone.id)) {
        map.addSource(zone.id, {
          type: 'geojson',
          data: { type: 'Feature', geometry: zone.polygon, properties: { id: zone.id } },
        });
      }

      const fillId = `${zone.id}-fill`;
      const outlineId = `${zone.id}-outline`;

      if (!map.getLayer(fillId)) {
        map.addLayer({
          id: fillId,
          type: 'fill',
          source: zone.id,
          paint: { 'fill-color': ndviColor(zone.latest_scores.ndvi), 'fill-opacity': 0.18 },
        });
      }

      const glowId = `${zone.id}-glow`;
      if (!map.getLayer(glowId)) {
        map.addLayer({
          id: glowId,
          type: 'line',
          source: zone.id,
          paint: {
            'line-color': ndviColor(zone.latest_scores.ndvi),
            'line-width': 6,
            'line-opacity': 0.15,
            'line-blur': 4,
          },
        });
      }

      if (!map.getLayer(outlineId)) {
        map.addLayer({
          id: outlineId,
          type: 'line',
          source: zone.id,
          paint: {
            'line-color': ndviColor(zone.latest_scores.ndvi),
            'line-width': 1.5,
            'line-opacity': 0.85,
            'line-dasharray': [4, 2],
          },
        });
      }

      map.on('click', fillId, () => onZoneSelect(zone));
      map.on('click', glowId, () => onZoneSelect(zone));
      map.on('mouseenter', fillId, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', fillId, () => { map.getCanvas().style.cursor = ''; });
    });

    // ── Zone label layer ─────────────────────────────────────────────────────
    if (!map.getSource('zone-labels')) {
      map.addSource('zone-labels', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: zones.map((z) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: centroid(z.polygon) },
            properties: { label: z.label },
          })),
        },
      });
    }

    if (!map.getLayer('zone-labels-text')) {
      map.addLayer({
        id: 'zone-labels-text',
        type: 'symbol',
        source: 'zone-labels',
        layout: {
          'text-field': ['get', 'label'],
          'text-size': 12,
          'text-font': ['DIN Offc Pro Bold', 'Arial Unicode MS Bold'],
          'text-anchor': 'center',
          'text-allow-overlap': true,
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0,0,0,0.85)',
          'text-halo-width': 2,
          'text-opacity': 0.9,
        },
      });
    }

    // ── Selected zone highlight source (empty initially) ─────────────────────
    if (!map.getSource('zone-highlight')) {
      map.addSource('zone-highlight', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
    }

    if (!map.getLayer('zone-highlight-outline')) {
      map.addLayer({
        id: 'zone-highlight-outline',
        type: 'line',
        source: 'zone-highlight',
        paint: {
          'line-color': '#ffffff',
          'line-width': 3,
          'line-opacity': 1,
        },
      });
    }

    if (!hasFitRef.current && zones.length > 0) {
      hasFitRef.current = true;
      // Compute bounding box of all zone polygons
      let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
      zones.forEach((zone) => {
        zone.polygon.coordinates[0].forEach(([lng, lat]) => {
          if (lng < minLng) minLng = lng;
          if (lat < minLat) minLat = lat;
          if (lng > maxLng) maxLng = lng;
          if (lat > maxLat) maxLat = lat;
        });
      });
      map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 80, duration: 800 });
    }

    return () => {
      zones.forEach((zone) => {
        const fillId = `${zone.id}-fill`;
        const glowId = `${zone.id}-glow`;
        const outlineId = `${zone.id}-outline`;
        if (map.getLayer(outlineId)) map.removeLayer(outlineId);
        if (map.getLayer(glowId)) map.removeLayer(glowId);
        if (map.getLayer(fillId)) map.removeLayer(fillId);
        if (map.getSource(zone.id)) map.removeSource(zone.id);
      });
      if (map.getLayer('zone-labels-text')) map.removeLayer('zone-labels-text');
      if (map.getSource('zone-labels')) map.removeSource('zone-labels');
      if (map.getLayer('zone-highlight-outline')) map.removeLayer('zone-highlight-outline');
      if (map.getSource('zone-highlight')) map.removeSource('zone-highlight');
    };
  }, [map, zones, onZoneSelect]);

  // ── Update highlight when selected zone changes ──────────────────────────
  useEffect(() => {
    if (!map || !map.getSource('zone-highlight')) return;
    const source = map.getSource('zone-highlight') as mapboxgl.GeoJSONSource;
    if (!selectedZoneId) {
      source.setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const zone = zonesRef.current.find((z) => z.id === selectedZoneId);
    if (!zone) return;
    source.setData({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: zone.polygon, properties: {} }],
    });
  }, [map, selectedZoneId]);

  return null;
}
