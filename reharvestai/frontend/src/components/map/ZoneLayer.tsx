'use client';

import { useEffect } from 'react';
import { useMap } from './FieldMap';
import { useZones } from '@/hooks/useZones';
import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneLayerProps {
  fieldId: string;
  onZoneSelect: (zone: Zone) => void;
}

export default function ZoneLayer({ fieldId, onZoneSelect }: ZoneLayerProps) {
  const map = useMap();
  const { data: zones } = useZones(fieldId);

  useEffect(() => {
    if (!map || !zones) return;

    // Add each zone as a source + fill layer
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
          paint: {
            'fill-color': ndviColor(zone.latest_scores.ndvi),
            'fill-opacity': 0.45,
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
            'line-width': 2,
            'line-opacity': 0.9,
          },
        });
      }

      // Click to select zone
      map.on('click', fillId, () => onZoneSelect(zone));

      // Cursor change on hover
      map.on('mouseenter', fillId, () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', fillId, () => {
        map.getCanvas().style.cursor = '';
      });
    });

    // Cleanup: remove layers and sources
    return () => {
      zones.forEach((zone) => {
        const fillId = `${zone.id}-fill`;
        const outlineId = `${zone.id}-outline`;
        if (map.getLayer(fillId)) map.removeLayer(fillId);
        if (map.getLayer(outlineId)) map.removeLayer(outlineId);
        if (map.getSource(zone.id)) map.removeSource(zone.id);
      });
    };
  }, [map, zones, onZoneSelect]);

  return null;
}
