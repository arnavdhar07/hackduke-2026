'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN, MAPBOX_STYLE, DEFAULT_CENTER, DEFAULT_ZOOM } from '@/lib/mapbox';
import { detectField } from '@/lib/api';
import type { Polygon } from 'geojson';

interface OnboardingMapProps {
  onPolygonChange: (polygon: GeoJSON.Polygon | null) => void;
  mode: 'detect' | 'draw';
}

const DETECT_SOURCE_ID = 'detected-field';
const DETECT_FILL_LAYER = 'detected-field-fill';
const DETECT_LINE_LAYER = 'detected-field-line';

export default function OnboardingMap({ onPolygonChange, mode }: OnboardingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const drawRef = useRef<MapboxDraw | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectedConfidence, setDetectedConfidence] = useState<number | null>(null);
  const [detectedSource, setDetectedSource] = useState<string | null>(null);
  const [hasDetected, setHasDetected] = useState(false);

  // Show detected polygon on map
  const showDetectedPolygon = useCallback((map: mapboxgl.Map, polygon: Polygon) => {
    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: polygon, properties: {} }],
    };

    const src = map.getSource(DETECT_SOURCE_ID) as mapboxgl.GeoJSONSource | undefined;
    if (src) {
      src.setData(geojson);
    } else {
      map.addSource(DETECT_SOURCE_ID, { type: 'geojson', data: geojson });
      map.addLayer({
        id: DETECT_FILL_LAYER,
        type: 'fill',
        source: DETECT_SOURCE_ID,
        paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.25 },
      });
      map.addLayer({
        id: DETECT_LINE_LAYER,
        type: 'line',
        source: DETECT_SOURCE_ID,
        paint: { 'line-color': '#22c55e', 'line-width': 2 },
      });
    }
  }, []);

  const clearDetectedPolygon = useCallback((map: mapboxgl.Map) => {
    if (map.getLayer(DETECT_FILL_LAYER)) map.removeLayer(DETECT_FILL_LAYER);
    if (map.getLayer(DETECT_LINE_LAYER)) map.removeLayer(DETECT_LINE_LAYER);
    if (map.getSource(DETECT_SOURCE_ID)) map.removeSource(DETECT_SOURCE_ID);
  }, []);

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
      defaultMode: 'simple_select',
    });

    map.addControl(draw, 'top-right');
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    function handleDrawChange() {
      const data = draw.getAll();
      const feature = data.features[0];
      if (feature && feature.geometry.type === 'Polygon') {
        onPolygonChange(feature.geometry as GeoJSON.Polygon);
        clearDetectedPolygon(map);
        setHasDetected(false);
        setDetectedConfidence(null);
      } else {
        onPolygonChange(null);
      }
    }

    map.on('draw.create', handleDrawChange);
    map.on('draw.update', handleDrawChange);
    map.on('draw.delete', handleDrawChange);

    // Click to detect field boundary
    map.on('click', async (e) => {
      if (modeRef.current === 'draw') return;  // draw mode active
      const { lat, lng } = e.lngLat;

      setDetecting(true);
      setHasDetected(false);
      setDetectedConfidence(null);
      onPolygonChange(null);

      try {
        const result = await detectField(lat, lng);
        showDetectedPolygon(map, result.polygon as Polygon);
        setDetectedConfidence(result.confidence);
        setDetectedSource(result.source);
        setHasDetected(true);
        onPolygonChange(result.polygon as GeoJSON.Polygon);
      } catch (err) {
        console.error('Field detection failed:', err);
      } finally {
        setDetecting(false);
      }
    });

    mapRef.current = map;
    drawRef.current = draw;

    return () => {
      map.remove();
      mapRef.current = null;
      drawRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ref so the click handler closure sees current mode without stale closure
  const modeRef = useRef(mode);
  useEffect(() => { modeRef.current = mode; }, [mode]);

  // React to parent toggling mode
  useEffect(() => {
    const draw = drawRef.current;
    const map = mapRef.current;
    if (!draw || !map) return;

    if (mode === 'draw') {
      clearDetectedPolygon(map);
      setHasDetected(false);
      setDetectedConfidence(null);
      onPolygonChange(null);
      draw.changeMode('draw_polygon');
    } else {
      draw.deleteAll();
      draw.changeMode('simple_select');
      onPolygonChange(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Instruction overlay */}
      <div className="absolute top-4 left-4 pointer-events-none">
        <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 max-w-[200px]">
          {mode === 'draw'
            ? 'Draw your field boundary on the map'
            : detecting
            ? 'Detecting field boundary…'
            : 'Click on your field to auto-detect its boundary'}
        </div>
      </div>

      {/* Confidence badge */}
      {hasDetected && detectedConfidence !== null && !detecting && (
        <div className="absolute top-16 left-4">
          <div className="bg-green-900/90 backdrop-blur-sm border border-green-700 rounded-lg px-3 py-1.5 text-xs text-green-300 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
            {Math.round(detectedConfidence * 100)}% confident
            {detectedSource === 'fallback' && (
              <span className="text-green-500 ml-1">(approx)</span>
            )}
          </div>
        </div>
      )}

      {/* Loading indicator */}
      {detecting && (
        <div className="absolute top-16 left-4">
          <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-600 rounded-lg px-3 py-1.5 text-xs text-gray-300 flex items-center gap-2">
            <div className="w-3 h-3 border border-gray-500 border-t-white rounded-full animate-spin" />
            Detecting…
          </div>
        </div>
      )}

    </div>
  );
}
