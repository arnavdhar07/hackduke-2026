'use client';

import { useEffect, useRef, useState, createContext, useContext } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN, MAPBOX_STYLE } from '@/lib/mapbox';

const MapContext = createContext<mapboxgl.Map | null>(null);

export function useMap() {
  return useContext(MapContext);
}

interface FieldMapProps {
  center: [number, number];
  zoom: number;
  onMapReady?: (map: mapboxgl.Map) => void;
  children?: React.ReactNode;
}

export default function FieldMap({ center, zoom, onMapReady, children }: FieldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [map, setMap] = useState<mapboxgl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = MAPBOX_TOKEN;

    const instance = new mapboxgl.Map({
      container: containerRef.current,
      style: MAPBOX_STYLE,
      center,
      zoom,
    });

    instance.addControl(new mapboxgl.NavigationControl(), 'top-right');

    instance.on('load', () => {
      mapRef.current = instance;
      setMap(instance);
      onMapReady?.(instance);
    });

    return () => {
      instance.remove();
      mapRef.current = null;
      setMap(null);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fly to new center when it changes (e.g. after field data loads)
  const initializedRef = useRef(false);
  useEffect(() => {
    if (!mapRef.current) return;
    if (!initializedRef.current) {
      initializedRef.current = true;
      return; // skip the first render — map already initialized at this center
    }
    mapRef.current.flyTo({ center, zoom, duration: 800 });
  }, [center, zoom]);

  return (
    <MapContext.Provider value={map}>
      <div className="relative w-full h-full">
        <div ref={containerRef} className="w-full h-full" />
        {children}
      </div>
    </MapContext.Provider>
  );
}
