'use client';

import type { WeatherDay, WeatherCondition } from '@/types/api';

const ICONS: Record<WeatherCondition, React.ReactNode> = {
  clear: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-yellow-400">
      <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeLinecap="round"/>
    </svg>
  ),
  cloudy: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-gray-400">
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  rain: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-blue-400">
      <path d="M17.5 16H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M8 19v2M12 19v2M16 19v2" strokeLinecap="round"/>
    </svg>
  ),
  storm: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-amber-400">
      <path d="M17.5 16H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M13 12l-2 4h4l-2 4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

function formatDay(dateStr: string) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return 'Today';
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

interface WeatherStripProps {
  days: WeatherDay[];
}

export default function WeatherStrip({ days }: WeatherStripProps) {
  const rainDay = days.find((d) => d.precip_mm > 10);
  const hoursUntilRain = rainDay
    ? Math.max(0, Math.round((new Date(rainDay.date + 'T08:00:00').getTime() - Date.now()) / 3_600_000))
    : null;

  return (
    <div className="shrink-0 border-b border-[#2a3045] px-4 py-3" style={{ backgroundColor: '#0f1117' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">3-Day Forecast</span>
        {hoursUntilRain !== null && (
          <span className="animate-pulse bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full font-semibold">
            Rain in ~{hoursUntilRain}h
          </span>
        )}
      </div>
      <div className="flex gap-2">
        {days.map((day) => (
          <div
            key={day.date}
            className={`flex-1 flex flex-col items-center gap-1 rounded-lg px-2.5 py-2.5 border ${
              day.precip_mm > 10
                ? 'border-blue-700/50 bg-blue-950/30'
                : 'border-[#2a3045]'
            }`}
            style={day.precip_mm <= 10 ? { backgroundColor: '#1a1f2e' } : undefined}
          >
            <span className="text-[10px] text-gray-400 font-medium">{formatDay(day.date)}</span>
            {ICONS[day.condition]}
            <span className="text-sm font-bold text-white">{day.temp_high_c}°</span>
            <span className="text-[10px] text-gray-500">{day.temp_low_c}°</span>
            {day.precip_mm > 0 && (
              <span className="bg-blue-900/60 border border-blue-500/30 text-blue-300 text-[10px] px-1.5 rounded font-medium">
                {day.precip_mm}mm
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
