'use client';

import Link from 'next/link';
import React from 'react';
import { ContainerScroll } from '@/components/ui/container-scroll-animation';
import DatabaseWithRestApi from '@/components/ui/database-with-rest-api';

// ─── Nav ──────────────────────────────────────────────────────────────────────

const Nav = React.memo(function Nav() {
  const [open, setOpen] = React.useState(false);
  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-gray-800/50 bg-black/80 backdrop-blur-md">
      <nav className="max-w-6xl mx-auto px-6 py-3.5 flex items-center justify-between relative">
        <span className="text-xl font-bold tracking-tight text-white">
          ReHarvest<span className="text-green-400">AI</span>
        </span>

        {/* Center links */}
        <div className="hidden md:flex items-center gap-8 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          {['Problem', 'How it works', 'Features'].map((label) => (
            <a
              key={label}
              href={`#${label.toLowerCase().replace(/ /g, '-')}`}
              className="text-sm text-white/50 hover:text-white transition-colors"
            >
              {label}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/dashboard/field-001"
            className="text-sm text-white/60 hover:text-white transition-colors px-3 py-1.5"
          >
            Demo
          </Link>
          <Link
            href="/fields"
            className="text-sm font-semibold px-4 py-1.5 rounded-lg bg-green-500 hover:bg-green-400 text-gray-950 transition-colors"
          >
            Get started
          </Link>
        </div>

        <button
          className="md:hidden text-white/60 hover:text-white"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><path d="M18 6 6 18M6 6l12 12" strokeLinecap="round"/></svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round"/></svg>
          )}
        </button>
      </nav>

      {open && (
        <div className="md:hidden bg-black/95 border-t border-gray-800/50 px-6 py-4 flex flex-col gap-3">
          {['Problem', 'How it works', 'Features'].map((label) => (
            <a key={label} href={`#${label.toLowerCase().replace(/ /g, '-')}`} className="text-sm text-white/60 hover:text-white py-1" onClick={() => setOpen(false)}>{label}</a>
          ))}
          <div className="pt-3 border-t border-gray-800/50 flex flex-col gap-2">
            <Link href="/dashboard/field-001" className="text-sm text-white/60 text-center py-2">Demo dashboard</Link>
            <Link href="/fields" className="text-sm font-semibold text-center py-2 rounded-lg bg-green-500 text-gray-950">Get started</Link>
          </div>
        </div>
      )}
    </header>
  );
});

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <Nav />

      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center pt-28 pb-16 px-6 text-center overflow-hidden min-h-screen">
        {/* Drone video background */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover"
          style={{ zIndex: 0 }}
        >
          <source src="https://assets.mixkit.co/videos/7839/7839-720.mp4" type="video/mp4" />
        </video>
        {/* Dark overlay so text stays readable */}
        <div className="absolute inset-0 bg-black/55" style={{ zIndex: 1 }} />
        {/* Green glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[640px] h-[400px] bg-green-500/10 rounded-full blur-[100px] pointer-events-none" style={{ zIndex: 2 }} />

        {/* Content — sits above video + overlay */}
        <div className="relative flex flex-col items-center text-center" style={{ zIndex: 3 }}>
          {/* Badge */}
          <div className="mb-6 inline-flex items-center gap-2 px-3 py-1 rounded-full border border-gray-700 bg-gray-800/50 backdrop-blur-sm text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Powered by Sentinel-2 · 5-day revisit
            <span className="ml-1 text-white/30">→</span>
          </div>

          <h1
            className="text-5xl md:text-7xl font-bold leading-[1.1] tracking-tight mb-5 max-w-3xl"
            style={{
              background: 'linear-gradient(to bottom, #ffffff 60%, rgba(255,255,255,0.45))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Harvest at the<br />
            <span style={{ WebkitTextFillColor: '#4ade80' }}>right moment.</span>
          </h1>

          <p className="text-base md:text-lg text-gray-300 max-w-lg mb-8 leading-relaxed">
            Satellite-powered harvest intelligence. Know exactly when and where to harvest.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/fields"
              className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-xl font-bold text-sm text-gray-950 transition-all hover:scale-105 active:scale-95 shadow-lg shadow-green-500/20"
              style={{ background: 'linear-gradient(to bottom, #ffffff, rgba(255,255,255,0.85))' }}
            >
              Draw your field
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </Link>
            <Link
              href="/dashboard/field-001"
              className="inline-flex items-center justify-center px-7 py-3 rounded-xl border border-white/20 hover:border-white/40 text-white/80 hover:text-white font-semibold text-sm transition-colors backdrop-blur-sm"
            >
              View demo
            </Link>
          </div>
        </div>
      </section>

      {/* 3D Scroll — Dashboard Preview */}
      <section className="bg-black -mt-8 md:-mt-12">
        <ContainerScroll
          titleComponent={
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-widest text-green-400 mb-3">Live Dashboard</p>
              <h2
                className="text-3xl md:text-5xl font-bold leading-tight"
                style={{
                  background: 'linear-gradient(to bottom, #ffffff 50%, rgba(255,255,255,0.45))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                Every zone. Every risk.<br />One dashboard.
              </h2>
            </div>
          }
        >
          {/* Mini dashboard mockup */}
          <div className="flex h-full w-full bg-[#0d1117] overflow-hidden rounded-xl">
            {/* Map panel */}
            <div className="relative flex-1 overflow-hidden">
              <img
                src="https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1400&q=85"
                alt="Satellite farm view"
                className="w-full h-full object-cover"
                style={{ objectPosition: 'center 30%' }}
              />


              {/* Fade into sidebar */}
              <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-r from-transparent to-[#0d1117]" />
            </div>

            {/* Sidebar */}
            <div className="w-52 md:w-64 bg-[#0d1117] border-l border-white/5 flex flex-col overflow-hidden shrink-0">
              {/* Header */}
              <div className="px-4 py-3 border-b border-white/5">
                <p className="text-[11px] font-bold text-white">Sandling Farm</p>
                <p className="text-[9px] text-gray-500 mt-0.5">4 zones · Corn</p>
              </div>

              {/* Cards */}
              <div className="flex-1 overflow-hidden px-3 py-3 flex flex-col gap-2">
                {[
                  { zone: 'Zone D', action: 'Harvest', urgency: 'Critical', cardBg: 'bg-red-950/40', border: 'border-red-500/50', badge: 'bg-red-500', dot: 'bg-red-500', bar: '92%' },
                  { zone: 'Zone C', action: 'Inspect',  urgency: 'High',     cardBg: 'bg-amber-950/30', border: 'border-amber-500/40', badge: 'bg-amber-500', dot: 'bg-amber-400', bar: '74%' },
                  { zone: 'Zone B', action: 'Monitor',  urgency: 'Medium',   cardBg: 'bg-gray-800/40', border: 'border-white/10',  badge: 'bg-gray-500',  dot: 'bg-blue-400',  bar: '55%' },
                  { zone: 'Zone A', action: 'Irrigate', urgency: 'Low',      cardBg: 'bg-gray-800/40', border: 'border-white/10',  badge: 'bg-blue-600',  dot: 'bg-gray-500',  bar: '38%' },
                ].map((r) => (
                  <div key={r.zone} className={`rounded-lg border px-2.5 py-2 ${r.cardBg} ${r.border}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${r.dot}`} />
                      <span className="text-[9px] font-semibold text-white flex-1">{r.zone}</span>
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded text-white ${r.badge}`}>{r.action}</span>
                    </div>
                    <p className="text-[8px] text-gray-400 mb-1.5">Urgency: {r.urgency}</p>
                    <div className="h-0.5 rounded-full bg-white/10 overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full" style={{ width: r.bar }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Footer stats */}
              <div className="px-4 py-3 border-t border-white/5 flex justify-between">
                <div className="text-center">
                  <p className="text-[11px] font-bold text-green-400">72</p>
                  <p className="text-[8px] text-gray-500">Avg NDVI</p>
                </div>
                <div className="text-center">
                  <p className="text-[11px] font-bold text-red-400">1</p>
                  <p className="text-[8px] text-gray-500">Critical</p>
                </div>
                <div className="text-center">
                  <p className="text-[11px] font-bold text-white">4</p>
                  <p className="text-[8px] text-gray-500">Zones</p>
                </div>
              </div>
            </div>
          </div>
        </ContainerScroll>
      </section>

      {/* Problem */}
      <section id="problem" className="px-6 py-16 md:py-20 border-t border-gray-800/40">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-semibold uppercase tracking-widest text-green-400 mb-3">The Problem</p>
          <h2
            className="text-3xl md:text-5xl font-bold leading-tight mb-5"
            style={{
              background: 'linear-gradient(to bottom, #ffffff 50%, rgba(255,255,255,0.5))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            30–40% of food is wasted<br />before it leaves the farm.
          </h2>
          <p className="text-gray-400 text-sm md:text-base leading-relaxed max-w-2xl mb-10">
            Poor harvest timing is the leading cause. Farmers rely on gut feel and visual inspections — missing the peak window triggers crop loss from weather and contributes to billions of tonnes of avoidable food waste every year.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { stat: '30–40%', label: 'of food wasted at farm level', color: 'text-red-400' },
              { stat: '$750B', label: 'lost annually to crop mismanagement', color: 'text-amber-400' },
              { stat: '5 days', label: 'satellite revisit — enough to catch the window', color: 'text-green-400' },
            ].map(({ stat, label, color }) => (
              <div key={stat} className="rounded-xl border border-gray-800 bg-gray-900/50 px-5 py-4">
                <p className={`text-3xl font-extrabold mb-1 ${color}`}>{stat}</p>
                <p className="text-xs text-gray-400">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="relative px-6 py-16 md:py-20 border-t border-gray-800/40">

        {/* 3D Satellite background decoration */}
        <svg
          viewBox="0 0 420 360"
          className="absolute top-6 right-4 w-[280px] md:w-[380px] opacity-[0.17] pointer-events-none select-none"
          fill="none"
          stroke="#4ade80"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Orbital ring — dashed ellipse */}
          <ellipse cx="210" cy="240" rx="195" ry="62" strokeWidth="1" strokeDasharray="6 5" />

          {/* Satellite body — isometric 3D box */}
          {/* Front face */}
          <rect x="170" y="128" width="80" height="54" rx="2" strokeWidth="1.2" />
          {/* Top face (parallelogram) */}
          <polygon points="170,128 250,128 268,110 188,110" strokeWidth="1" />
          {/* Right face (parallelogram) */}
          <polygon points="250,128 268,110 268,164 250,182" strokeWidth="1" />
          {/* Body interior cross detail */}
          <line x1="170" y1="155" x2="250" y2="155" strokeWidth="0.6" />
          <line x1="210" y1="128" x2="210" y2="182" strokeWidth="0.6" />
          <line x1="188" y1="110" x2="268" y2="110" strokeWidth="0.6" opacity="0.5" />
          {/* Small circle on body */}
          <circle cx="210" cy="155" r="10" strokeWidth="0.8" />
          <circle cx="210" cy="155" r="4" strokeWidth="0.6" />

          {/* Left solar panel */}
          <rect x="18" y="143" width="148" height="36" rx="2" strokeWidth="1" />
          {/* Panel grid dividers */}
          <line x1="55"  y1="143" x2="55"  y2="179" strokeWidth="0.5" />
          <line x1="92"  y1="143" x2="92"  y2="179" strokeWidth="0.5" />
          <line x1="130" y1="143" x2="130" y2="179" strokeWidth="0.5" />
          {/* Horizontal divider */}
          <line x1="18" y1="161" x2="166" y2="161" strokeWidth="0.5" />
          {/* Boom connecting panel to body */}
          <line x1="166" y1="161" x2="170" y2="155" strokeWidth="1" />

          {/* Right solar panel */}
          <rect x="254" y="143" width="148" height="36" rx="2" strokeWidth="1" />
          <line x1="291" y1="143" x2="291" y2="179" strokeWidth="0.5" />
          <line x1="328" y1="143" x2="328" y2="179" strokeWidth="0.5" />
          <line x1="366" y1="143" x2="366" y2="179" strokeWidth="0.5" />
          <line x1="254" y1="161" x2="402" y2="161" strokeWidth="0.5" />
          <line x1="250" y1="155" x2="254" y2="161" strokeWidth="1" />

          {/* Antenna boom */}
          <line x1="210" y1="110" x2="218" y2="64" strokeWidth="1" />

          {/* Parabolic dish */}
          <path d="M 200 64 Q 218 50 236 64" strokeWidth="1.2" />
          <line x1="218" y1="57" x2="218" y2="64" strokeWidth="0.8" />

          {/* Signal arcs from dish */}
          <path d="M 196 58 Q 184 44 190 30" strokeWidth="0.7" strokeDasharray="3 2.5" opacity="0.7" />
          <path d="M 192 62 Q 176 46 183 28" strokeWidth="0.6" strokeDasharray="3 2.5" opacity="0.5" />
          <path d="M 188 66 Q 168 50 176 28" strokeWidth="0.5" strokeDasharray="3 2.5" opacity="0.3" />

          {/* Small position dots on orbital ring */}
          <circle cx="15"  cy="240" r="3" strokeWidth="1" />
          <circle cx="405" cy="240" r="3" strokeWidth="1" />
          <circle cx="210" cy="178" r="2" strokeWidth="0.8" />
        </svg>

        <div className="max-w-5xl mx-auto">
          <p className="text-xs font-semibold uppercase tracking-widest text-green-400 mb-3 text-center">How it works</p>
          <h2
            className="text-3xl md:text-5xl font-bold mb-4 text-center"
            style={{
              background: 'linear-gradient(to bottom, #ffffff 50%, rgba(255,255,255,0.5))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Three steps to zero crop loss.
          </h2>
          <p className="text-sm text-gray-400 text-center mb-12 max-w-lg mx-auto">
            Every signal flows into one AI brain. One clear action comes out.
          </p>

          <div className="flex flex-col md:flex-row items-start gap-10">
            {/* Steps column */}
            <div className="flex flex-col gap-8 md:w-72 shrink-0 md:pt-10">
              {[
                {
                  step: '01', title: 'Draw your field',
                  desc: 'Outline your farm on a satellite map. ReHarvestAI divides it into zones and starts tracking immediately.',
                  color: 'text-green-400', border: 'border-green-500/30',
                },
                {
                  step: '02', title: 'Satellite health scan',
                  desc: 'Every 5 days, Sentinel-2 imagery computes NDVI, NDWI, and NDRE crop health scores per zone.',
                  color: 'text-blue-400', border: 'border-blue-500/30',
                },
                {
                  step: '03', title: 'AI-ranked actions',
                  desc: 'A LangGraph agent fuses satellite data with weather forecasts and delivers urgent plain-English recommendations.',
                  color: 'text-amber-400', border: 'border-amber-500/30',
                },
              ].map(({ step, title, desc, color, border }) => (
                <div key={step} className={`relative pl-5 border-l-2 ${border}`}>
                  <span className={`text-[10px] font-bold uppercase tracking-widest ${color} mb-1 block`}>{step}</span>
                  <h3 className="text-sm font-bold text-white mb-1">{title}</h3>
                  <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>

            {/* Animated diagram */}
            <div className="flex-1 flex justify-center">
              <DatabaseWithRestApi
                lightColor="#4ade80"
                circleText="AI"
                title="Satellite · Weather · AI Agent → Zero Crop Loss"
                badgeTexts={{
                  first: 'Draw Field',
                  second: 'Sentinel-2',
                  third: 'Weather',
                  fourth: 'AI Agent',
                }}
                buttonTexts={{
                  first: 'Harvest ready',
                  second: 'Rain in 36h',
                }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-6 py-16 md:py-20 border-t border-gray-800/40">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs font-semibold uppercase tracking-widest text-green-400 mb-3">Features</p>
          <h2
            className="text-3xl md:text-5xl font-bold mb-10"
            style={{
              background: 'linear-gradient(to bottom, #ffffff 50%, rgba(255,255,255,0.5))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Built for the field, not the lab.
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { title: 'Per-zone health scoring', desc: 'NDVI, NDWI, and NDRE scores per zone, visualized as a color-coded heatmap on the satellite basemap.', accent: 'bg-green-400' },
              { title: 'Weather-fused recommendations', desc: 'Recommendations factor in 72-hour forecasts. Rain coming + peak ripeness = alert 36 hours early.', accent: 'bg-blue-400' },
              { title: 'AI reasoning trace', desc: "Every recommendation shows a full step-by-step breakdown of the AI agent's reasoning. No black boxes.", accent: 'bg-amber-400' },
              { title: 'Urgency-ranked action queue', desc: 'Critical zones surface first. Accept, defer, or dismiss with one tap. Nothing falls through the cracks.', accent: 'bg-red-400' },
            ].map(({ title, desc, accent }) => (
              <div key={title} className="group relative rounded-xl border border-gray-800 bg-gray-900/50 hover:bg-gray-900 p-5 transition-colors overflow-hidden">
                <div className={`absolute top-0 left-0 w-0.5 h-full ${accent} opacity-60 group-hover:opacity-100 transition-opacity`} />
                <h3 className="font-bold text-sm mb-1.5">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative px-6 py-16 md:py-20 border-t border-gray-800/40 overflow-hidden text-center">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-green-500/8 rounded-full blur-[100px] pointer-events-none" />
        <div className="relative max-w-xl mx-auto">
          <h2
            className="text-3xl md:text-5xl font-bold mb-4"
            style={{
              background: 'linear-gradient(to bottom, #ffffff 50%, rgba(255,255,255,0.5))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Your field is losing yield<br />
            <span style={{ WebkitTextFillColor: '#4ade80' }}>right now.</span>
          </h2>
          <p className="text-gray-400 text-sm mb-8">Draw it on the map. It takes 60 seconds.</p>
          <Link
            href="/fields"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-sm text-gray-950 transition-all hover:scale-105 active:scale-95 shadow-xl shadow-green-500/20"
            style={{ background: 'linear-gradient(to bottom, #ffffff, rgba(255,255,255,0.85))' }}
          >
            Start for free
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-6 border-t border-gray-800/40 flex flex-col md:flex-row items-center justify-between gap-2 text-xs text-gray-600 max-w-6xl mx-auto">
        <span>ReHarvest<span className="text-green-400">AI</span> · HackDuke 2026</span>
        <span>Sentinel-2 · Mapbox · LangGraph</span>
      </footer>
    </main>
  );
}
