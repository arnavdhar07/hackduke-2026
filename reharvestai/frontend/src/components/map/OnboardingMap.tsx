'use client';

import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN, MAPBOX_STYLE, DEFAULT_CENTER, DEFAULT_ZOOM } from '@/lib/mapbox';

interface OnboardingMapProps {
  onPolygonChange: (polygon: GeoJSON.Polygon | null) => void;
}

export default function OnboardingMap({ onPolygonChange }: OnboardingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const drawRef = useRef<MapboxDraw | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: MAPBOX_STYLE,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: { polygon: true, trash: true },
      defaultMode: 'draw_polygon',
    });

    map.addControl(draw, 'top-right');
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    function handleDrawChange() {
      const data = draw.getAll();
      const feature = data.features[0];
      if (feature && feature.geometry.type === 'Polygon') {
        onPolygonChange(feature.geometry as GeoJSON.Polygon);
      } else {
        onPolygonChange(null);
      }
    }

    map.on('draw.create', handleDrawChange);
    map.on('draw.update', handleDrawChange);
    map.on('draw.delete', handleDrawChange);

    mapRef.current = map;
    drawRef.current = draw;

    return () => {
      map.remove();
      mapRef.current = null;
      drawRef.current = null;
    };
  }, [onPolygonChange]);

  return <div ref={containerRef} className="w-full h-full" />;
}
