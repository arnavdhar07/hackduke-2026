'use client';

import { useEffect } from 'react';
import { useAgentTrace } from '@/hooks/useAgentTrace';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import type { AgentNode } from '@/types/api';

const NODE_LABELS: Record<string, string> = {
  context_builder:  'Context Builder',
  zone_classifier:  'Zone Classifier',
  risk_evaluator:   'Risk Evaluator',
  action_generator: 'Action Generator',
  output_formatter: 'Output Formatter',
};

const NODE_DESC: Record<string, string> = {
  context_builder:  'Gathered field data, weather forecast, and zone imagery.',
  zone_classifier:  'Assessed the health status of each zone.',
  risk_evaluator:   'Calculated risk levels based on health and weather.',
  action_generator: 'Decided on actions ranked by urgency.',
  output_formatter: 'Translated decisions into plain-English recommendations.',
};

const NODE_INDEX: Record<string, number> = {
  context_builder: 0, zone_classifier: 1, risk_evaluator: 2,
  action_generator: 3, output_formatter: 4,
};

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}

function NodeSection({ node }: { node: AgentNode }) {
  const label = NODE_LABELS[node.name] ?? node.name;
  const desc  = NODE_DESC[node.name] ?? '';
  const idx   = NODE_INDEX[node.name] ?? 0;

  return (
    <Collapsible className="border border-gray-700/60 rounded-xl overflow-hidden">
      <CollapsibleTrigger className="w-full flex items-center gap-3 px-4 py-3 bg-gray-800/60 hover:bg-gray-800 text-left transition-colors group">
        {/* Step number */}
        <span className="shrink-0 w-5 h-5 rounded-full border border-gray-600 text-[10px] font-bold text-gray-400 flex items-center justify-center">
          {idx + 1}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white">{label}</p>
          <p className="text-xs text-gray-400 mt-0.5 truncate">{desc}</p>
        </div>
        <svg
          viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"
          className="w-3.5 h-3.5 text-gray-500 shrink-0 transition-transform duration-200 group-data-[panel-open]:rotate-180"
        >
          <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </CollapsibleTrigger>

      <CollapsibleContent className="px-4 py-3 bg-gray-900/80 flex flex-col gap-3">
        {(['inputs', 'outputs'] as const).map((section) => (
          <div key={section}>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5">{section}</p>
            <div className="flex flex-col gap-1">
              {Object.entries(node[section] as object).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs">
                  <span className="text-gray-400 shrink-0 min-w-[110px]">{k}</span>
                  <span className="text-gray-200 break-all font-mono leading-relaxed">{formatValue(v)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

interface AgentTraceModalProps {
  fieldId: string;
  onClose: () => void;
}

export default function AgentTraceModal({ fieldId, onClose }: AgentTraceModalProps) {
  const { data: trace, isLoading, isError, fetch } = useAgentTrace(fieldId);

  useEffect(() => { fetch(); }, [fetch]);

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
            <p className="text-xs text-gray-400 mt-0.5">Step-by-step reasoning from the AI agent</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none transition-colors">×</button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-2">
          {isLoading && <p className="text-xs text-gray-400 text-center py-8">Loading agent reasoning…</p>}
          {isError   && <p className="text-xs text-red-400 text-center py-8">Failed to load trace.</p>}
          {trace && (
            <>
              <p className="text-xs text-gray-500 mb-1">
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
