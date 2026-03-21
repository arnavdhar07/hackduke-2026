'use client';

import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import { useMap } from './FieldMap';
import { useZones } from '@/hooks/useZones';

interface ZoneTooltipProps {
  fieldId: string;
}

export default function ZoneTooltip({ fieldId }: ZoneTooltipProps) {
  const map = useMap();
  const { data: zones } = useZones(fieldId);
  const popupRef = useRef<mapboxgl.Popup | null>(null);

  useEffect(() => {
    if (!map || !zones) return;

    const popup = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 8,
      className: 'zone-tooltip',
    });
    popupRef.current = popup;

    const handlers: Array<{ layerId: string; enter: () => void; leave: () => void }> = [];

    zones.forEach((zone) => {
      const fillId = `${zone.id}-fill`;

      const onEnter = (e: mapboxgl.MapMouseEvent) => {
        const coords = e.lngLat;
        popup
          .setLngLat(coords)
          .setHTML(
            `<div style="font-family:sans-serif;font-size:12px;color:#fff;background:#1f2937;padding:6px 10px;border-radius:6px;line-height:1.4">
              <strong>${zone.label}</strong><br/>NDVI: ${zone.latest_scores.ndvi}
            </div>`
          )
          .addTo(map);
      };

      const onLeave = () => popup.remove();

      map.on('mouseenter', fillId, onEnter);
      map.on('mouseleave', fillId, onLeave);
      handlers.push({ layerId: fillId, enter: onEnter, leave: onLeave });
    });

    return () => {
      popup.remove();
      handlers.forEach(({ layerId, enter, leave }) => {
        map.off('mouseenter', layerId, enter);
        map.off('mouseleave', layerId, leave);
      });
    };
  }, [map, zones]);

  return null;
}
