'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { createField } from '@/lib/api';
import { MAPBOX_STYLE, MAPBOX_TOKEN, DEFAULT_CENTER, DEFAULT_ZOOM } from '@/lib/mapbox';

// Dynamically import mapbox to avoid SSR issues
const MapboxOnboarding = dynamic(() => import('@/components/map/OnboardingMap'), { ssr: false });

export default function OnboardingPage() {
  const router = useRouter();
  const [polygon, setPolygon] = useState<GeoJSON.Polygon | null>(null);
  const [farmName, setFarmName] = useState('');
  const [cropType, setCropType] = useState('');
  const [plantingDate, setPlantingDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!polygon) return;
    setLoading(true);
    setError(null);
    try {
      const field = await createField({
        name: farmName,
        polygon,
        crop_type: cropType,
        planting_date: plantingDate,
      });
      router.push(`/dashboard/${field.id}`);
    } catch (err) {
      setError('Failed to create field. Please try again.');
      setLoading(false);
    }
  }

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {/* Full-screen map */}
      <MapboxOnboarding onPolygonChange={setPolygon} />

      {/* Form overlay */}
      <div className="absolute bottom-6 left-6 z-10 w-80 bg-gray-900/90 backdrop-blur-sm border border-gray-700 rounded-xl p-5 shadow-2xl">
        <h1 className="text-lg font-bold text-white mb-1"><a href="/" className="hover:opacity-70 transition-opacity">ReHarvestAI</a></h1>
        <p className="text-xs text-gray-400 mb-4">
          Draw your field on the map, then fill in the details below.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Farm name</label>
            <input
              type="text"
              value={farmName}
              onChange={e => setFarmName(e.target.value)}
              required
              placeholder="e.g. Thornfield Farm"
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Crop type</label>
            <input
              type="text"
              value={cropType}
              onChange={e => setCropType(e.target.value)}
              required
              placeholder="e.g. corn, wheat, soybeans, coffee…"
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Planting date</label>
            <input
              type="date"
              value={plantingDate}
              onChange={e => setPlantingDate(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-green-500 [color-scheme:dark]"
            />
          </div>

          {/* Polygon status */}
          <div className={`text-xs px-3 py-2 rounded-lg ${polygon ? 'bg-green-900/40 text-green-400' : 'bg-gray-800 text-gray-500'}`}>
            {polygon ? '✓ Field polygon drawn' : 'Draw a polygon on the map to continue'}
          </div>

          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={!polygon || !farmName || !cropType || !plantingDate || loading}
            className="w-full bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
          >
            {loading ? 'Creating field…' : 'Create field →'}
          </button>
        </form>
      </div>
    </div>
  );
}
