'use client';

import { useState } from 'react';

const PROJECTED_YIELD = 847;
const MARKET_CAPACITY = 843;  // surplus = 4 bu → ~187 meals

const AGENCIES = [
  { name: 'Inter-Faith Food Shuttle',          distance: '8.2 mi',  phone: '(919) 250-0043' },
  { name: 'Food Bank of Central & Eastern NC', distance: '18.4 mi', phone: '(919) 875-0707' },
  { name: 'Urban Ministries of Durham',        distance: '9.1 mi',  phone: '(919) 687-6529' },
];

interface CommunityImpactPanelProps {
  cropType: string;
  fieldName: string;
}

export default function CommunityImpactPanel({ cropType, fieldName }: CommunityImpactPanelProps) {
  const [open, setOpen] = useState(false);

  const surplus = Math.max(0, PROJECTED_YIELD - MARKET_CAPACITY);
  const lbs     = surplus * 56;
  const meals   = Math.round(lbs / 1.2);

  function mailtoHref() {
    const subject = encodeURIComponent('Surplus Crop Donation — Harvest');
    const body    = encodeURIComponent(
      `Hi,\n\nI have ${surplus} bushels of surplus ${cropType} available for donation from my farm (${fieldName}). Please contact me to arrange pickup.\n\nThank you.`
    );
    return `mailto:?subject=${subject}&body=${body}`;
  }

  return (
    <div className="border-b border-[#2a3045] mx-4 mt-3 mb-1 rounded-xl overflow-hidden bg-green-950/20 border border-green-500/20">
      {/* Collapsible header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-green-900/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-white uppercase tracking-widest">Community Impact</span>
          {surplus > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-950/60 border border-green-800/60 text-green-400 font-medium">
              {surplus} bu surplus
            </span>
          )}
        </div>
        <svg
          viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"
          className={`w-3.5 h-3.5 text-gray-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="border-t border-green-500/20 px-4 pb-4 pt-3 flex flex-col gap-3">
          {/* Surplus callout */}
          {surplus > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-2xl">🌱</span>
              <div>
                <span className="text-3xl font-bold text-green-400">{surplus}</span>
                <span className="text-sm text-green-400 ml-1">bu surplus</span>
              </div>
            </div>
          )}

          {/* Yield breakdown */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Projected', value: PROJECTED_YIELD, color: 'text-white' },
              { label: 'Sold',      value: MARKET_CAPACITY, color: 'text-gray-300' },
              { label: 'Surplus',   value: surplus,         color: surplus > 0 ? 'text-green-400' : 'text-gray-500' },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex flex-col items-center rounded-lg px-2 py-2.5 border border-[#2a3045]" style={{ backgroundColor: '#242938' }}>
                <span className={`text-base font-bold leading-none ${color}`}>{value}</span>
                <span className="text-[9px] text-gray-500 mt-0.5">bu</span>
                <span className="text-[9px] text-gray-600 mt-1">{label}</span>
              </div>
            ))}
          </div>

          {/* Meals callout */}
          {surplus > 0 && (
            <div className="rounded-lg border border-green-800/40 bg-green-950/25 px-3 py-2.5">
              <p className="text-xs font-semibold text-green-400 mb-0.5">~{meals} meals equivalent</p>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                {surplus} bu surplus = {lbs} lbs — enough for{' '}
                <span className="text-white font-medium">~{meals} meals</span> for families in need.
              </p>
            </div>
          )}

          {/* Agency cards */}
          {surplus > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Nearby food agencies</p>
              {AGENCIES.map((agency) => (
                <div key={agency.name} className="flex items-center justify-between rounded-xl px-3 py-2.5 gap-3 border border-[#2a3045]" style={{ backgroundColor: '#242938' }}>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-white truncate">{agency.name}</p>
                    <p className="text-[10px] text-gray-500 mt-0.5">{agency.distance} · {agency.phone}</p>
                  </div>
                  <a
                    href={mailtoHref()}
                    className="shrink-0 text-[11px] font-semibold px-3 py-1.5 rounded-lg bg-green-700 hover:bg-green-600 text-white transition-colors whitespace-nowrap"
                  >
                    Contact
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
