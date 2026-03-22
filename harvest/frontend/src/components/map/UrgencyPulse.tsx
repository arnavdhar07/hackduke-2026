'use client';

import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import { useMap } from './FieldMap';
import type { Recommendation, Zone } from '@/types/api';

interface UrgencyPulseProps {
  recommendations: Recommendation[];
  zones: Zone[];
}

function centroid(polygon: GeoJSON.Polygon): [number, number] {
  const coords = polygon.coordinates[0];
  const len = coords.length - 1; // last point duplicates first
  const lng = coords.slice(0, len).reduce((sum, c) => sum + c[0], 0) / len;
  const lat = coords.slice(0, len).reduce((sum, c) => sum + c[1], 0) / len;
  return [lng, lat];
}

export default function UrgencyPulse({ recommendations, zones }: UrgencyPulseProps) {
  const map = useMap();
  const markersRef = useRef<mapboxgl.Marker[]>([]);

  useEffect(() => {
    if (!map) return;

    // Remove existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const criticals = recommendations.filter((r) => r.urgency === 'critical' && r.status === 'pending');

    criticals.forEach((rec) => {
      const zone = zones.find((z) => z.id === rec.zone_id);
      if (!zone) return;

      const [lng, lat] = centroid(zone.polygon);

      // Build the pulsing HTML element
      const el = document.createElement('div');
      el.className = 'relative flex items-center justify-center';
      el.style.width = '32px';
      el.style.height = '32px';
      el.innerHTML = `
        <span style="
          position:absolute;
          width:32px;height:32px;
          border-radius:50%;
          background-color:#ef4444;
          opacity:0.4;
          animation:ping 1.5s cubic-bezier(0,0,0.2,1) infinite;
        "></span>
        <span style="
          position:relative;
          width:14px;height:14px;
          border-radius:50%;
          background-color:#ef4444;
          border:2px solid #fff;
        "></span>
      `;

      // Inject keyframes once
      if (!document.getElementById('urgency-pulse-style')) {
        const style = document.createElement('style');
        style.id = 'urgency-pulse-style';
        style.textContent = `
          @keyframes ping {
            75%, 100% { transform: scale(2); opacity: 0; }
          }
        `;
        document.head.appendChild(style);
      }

      const marker = new mapboxgl.Marker({ element: el, anchor: 'center' })
        .setLngLat([lng, lat])
        .addTo(map);

      markersRef.current.push(marker);
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [map, recommendations, zones]);

  return null;
}
