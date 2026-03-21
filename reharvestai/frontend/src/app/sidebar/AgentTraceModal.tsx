'use client';

import { useEffect, useState } from 'react';
import { useAgentTrace } from '@/hooks/useAgentTrace';
import type { AgentNode } from '@/types/api';

const NODE_LABELS: Record<string, string> = {
  context_builder: 'Context Builder',
  zone_classifier: 'Zone Classifier',
  risk_evaluator: 'Risk Evaluator',
  action_generator: 'Action Generator',
  output_formatter: 'Output Formatter',
};

const NODE_DESC: Record<string, string> = {
  context_builder: 'Gathered field data, weather forecast, and zone imagery.',
  zone_classifier: 'Assessed the health status of each zone.',
  risk_evaluator: 'Calculated risk levels based on health and weather.',
  action_generator: 'Decided on actions ranked by urgency.',
  output_formatter: 'Translated decisions into plain-English recommendations.',
};

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}

function NodeSection({ node }: { node: AgentNode }) {
  const [open, setOpen] = useState(false);
  const label = NODE_LABELS[node.name] ?? node.name;
  const desc = NODE_DESC[node.name] ?? '';

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750 text-left transition-colors"
      >
        <div>
          <p className="text-sm font-semibold text-white">{label}</p>
          <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
        </div>
        <span className="text-gray-400 text-lg ml-4">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 py-3 bg-gray-900 flex flex-col gap-3">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Inputs</p>
            <div className="flex flex-col gap-1">
              {Object.entries(node.inputs).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs">
                  <span className="text-gray-400 shrink-0 min-w-[120px]">{k}</span>
                  <span className="text-gray-200 break-all font-mono">{formatValue(v)}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Outputs</p>
            <div className="flex flex-col gap-1">
              {Object.entries(node.outputs).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs">
                  <span className="text-gray-400 shrink-0 min-w-[120px]">{k}</span>
                  <span className="text-gray-200 break-all font-mono">{formatValue(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface AgentTraceModalProps {
  fieldId: string;
  onClose: () => void;
}

export default function AgentTraceModal({ fieldId, onClose }: AgentTraceModalProps) {
  const { data: trace, isLoading, isError, fetch } = useAgentTrace(fieldId);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return (
    <div
      className="fixed inset-0 z-40 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 rounded-2xl w-full max-w-lg max-h-[80vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-white">Why this recommendation?</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Step-by-step reasoning from the AI agent
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none transition-colors"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-3">
          {isLoading && (
            <p className="text-xs text-gray-400 text-center py-8">Loading agent reasoning…</p>
          )}
          {isError && (
            <p className="text-xs text-red-400 text-center py-8">Failed to load trace.</p>
          )}
          {trace && (
            <>
              <p className="text-xs text-gray-500">
                Run at{' '}
                {new Date(trace.run_at).toLocaleString('en-US', {
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                })}
              </p>
              {trace.nodes.map((node) => (
                <NodeSection key={node.name} node={node} />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
