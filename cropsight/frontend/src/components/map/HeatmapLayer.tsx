'use client';

import { useEffect } from 'react';
import mapboxgl from 'mapbox-gl';
import { useMap } from './FieldMap';
import type { FieldHeatmap } from '@/lib/api';

const SOURCE_ID = 'field-heatmap';
const LAYER_ID  = 'field-heatmap-layer';

interface HeatmapLayerProps {
  heatmap: FieldHeatmap | null;
  visible: boolean;
}

export default function HeatmapLayer({ heatmap, visible }: HeatmapLayerProps) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    if (!heatmap || !visible) {
      if (map.getLayer(LAYER_ID))  map.removeLayer(LAYER_ID);
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
      return;
    }

    const [minLng, minLat, maxLng, maxLat] = heatmap.bounds;
    const imageUrl = `data:image/png;base64,${heatmap.image_png_b64}`;
    const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [
      [minLng, maxLat],  // top-left
      [maxLng, maxLat],  // top-right
      [maxLng, minLat],  // bottom-right
      [minLng, minLat],  // bottom-left
    ];

    if (map.getSource(SOURCE_ID)) {
      (map.getSource(SOURCE_ID) as mapboxgl.ImageSource).updateImage({
        url: imageUrl,
        coordinates,
      });
      if (map.getLayer(LAYER_ID)) {
        map.setLayoutProperty(LAYER_ID, 'visibility', 'visible');
      }
    } else {
      map.addSource(SOURCE_ID, { type: 'image', url: imageUrl, coordinates });
      map.addLayer({
        id: LAYER_ID,
        type: 'raster',
        source: SOURCE_ID,
        paint: { 'raster-opacity': 0.70 },
      });
    }
  }, [map, heatmap, visible]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (!map) return;
      try {
        if (map.getLayer(LAYER_ID))  map.removeLayer(LAYER_ID);
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
      } catch (_) { /* map may already be destroyed */ }
    };
  }, [map]);

  return null;
}
