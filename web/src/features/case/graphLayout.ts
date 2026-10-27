// Pure layout: the server sends topology only (nodes and edges, no positions); the browser lays it out left to right.
import dagre from '@dagrejs/dagre'
import type { EvidenceGraph } from '@/api/types'

export const NODE_W = 190
export const NODE_H = 64

export function layoutGraph(g: EvidenceGraph): Record<string, { x: number; y: number }> {
  const dg = new dagre.graphlib.Graph()
  dg.setGraph({ rankdir: 'LR', nodesep: 28, ranksep: 90 })
  dg.setDefaultEdgeLabel(() => ({}))
  g.nodes.forEach((n) => dg.setNode(n.id, { width: NODE_W, height: NODE_H }))
  g.edges.forEach((e) => dg.setEdge(e.source, e.target))
  dagre.layout(dg)
  return Object.fromEntries(g.nodes.map((n) => {
    const p = dg.node(n.id)
    return [n.id, { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 }]
  }))
}
