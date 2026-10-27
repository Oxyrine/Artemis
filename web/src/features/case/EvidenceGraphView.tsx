import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo } from 'react'
import { useGraph } from '@/api/hooks'
import { useTheme } from '@/app/providers'
import type { EvidenceGraph, GraphNode } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { amount, humanize } from '@/lib/format'
import { Section } from '@/ui/primitives'
import { layoutGraph, NODE_H, NODE_W } from './graphLayout'

const EDGE_COLOR: Record<string, string> = { supports: 'var(--edge-supports)', contradicts: 'var(--edge-contradicts)' }

function nodeStyle(n: GraphNode): React.CSSProperties {
  // primary evidence: solid border; supporting: dashed; derived: dotted (the same convention as the TierBadge)
  const border = n.tier === 'supporting' ? 'dashed' : n.tier === 'derived' ? 'dotted' : 'solid'
  return {
    width: NODE_W, height: NODE_H, background: `var(--node-${n.kind})`, color: 'var(--foreground)', fontSize: 12,
    border: `${n.tier ? 2 : 1}px ${border} var(--border)`, borderRadius: 8, padding: 6,
    ...(n.kind === 'adjustment' && n.validated === false ? { opacity: 0.6 } : {}),
  }
}

function toFlow(g: EvidenceGraph): { nodes: Node[]; edges: Edge[] } {
  const pos = layoutGraph(g)
  const nodes: Node[] = g.nodes.map((n) => ({
    id: n.id, position: pos[n.id], style: nodeStyle(n), draggable: false, connectable: false,
    data: {
      label: (
        <div className="flex h-full flex-col justify-center text-left leading-tight">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{humanize(n.kind)}{n.tier ? ` · ${n.tier}` : ''}</span>
          <span className="truncate font-medium">{n.kind === 'adjustment' || n.kind === 'evidence' ? humanize(n.label) : n.label}</span>
          {n.amount_paise != null && <span className="tabular-nums">₹{amount(n.amount_paise)}</span>}
        </div>
      ),
    },
  }))
  const edges: Edge[] = g.edges.map((e) => ({
    id: e.id, source: e.source, target: e.target, type: 'smoothstep',
    label: e.amount_paise != null ? `₹${amount(e.amount_paise)}` : e.label ?? (e.kind === 'supports' ? 'supports' : undefined),
    labelStyle: { fontSize: 11 }, labelBgStyle: { fill: 'var(--background)' },
    style: { stroke: EDGE_COLOR[e.kind] ?? 'var(--edge-neutral)', strokeWidth: 1.6, strokeDasharray: e.kind === 'contradicts' ? '6 4' : undefined },
    markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLOR[e.kind] ?? 'var(--edge-neutral)' },
  }))
  return { nodes, edges }
}

export function EvidenceGraphView({ caseId }: { caseId: string }) {
  const q = useGraph(caseId)
  const { theme } = useTheme()
  const flow = useMemo(() => (q.data ? toFlow(q.data) : null), [q.data])
  return (
    <Section title="Evidence graph" aside={<span className="text-xs text-muted-foreground">solid border = primary · dashed = supporting · dashed red edge = contradicts</span>}>
      {q.isLoading || !flow ? <Skeleton className="h-72 w-full" /> : (
        <>
          <div className="h-[440px] rounded-md border" role="img" aria-label={`Evidence graph with ${q.data!.nodes.length} nodes and ${q.data!.edges.length} edges. A text version follows.`}>
            <ReactFlow colorMode={theme} nodes={flow.nodes} edges={flow.edges} fitView fitViewOptions={{ padding: 0.15 }} nodesDraggable={false}
              nodesConnectable={false} elementsSelectable={false} minZoom={0.3}>
              <Background /><Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-muted-foreground">Graph as text</summary>
            <ul className="mt-1 list-disc pl-5">
              {q.data!.edges.map((e) => <li key={e.id}>{e.source} → {e.target}: {e.kind}{e.amount_paise != null ? ` ₹${amount(e.amount_paise)}` : e.label ? ` (${e.label})` : ''}</li>)}
            </ul>
          </details>
        </>
      )}
    </Section>
  )
}
