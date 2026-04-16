'use client';

interface StatCardProps {
  label: string;
  value: number;
  tooltip?: string;
}

export default function StatCard({ label, value, tooltip }: StatCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1" title={tooltip}>
      <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-white">{value}</span>
    </div>
  );
}
