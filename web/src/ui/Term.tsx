import type { ReactNode } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { GLOSSARY, type TermKey } from '@/lib/guide'

/** A word a newcomer may not know, with its plain-language definition on hover or keyboard focus. */
export function Term({ k, children }: { k: TermKey; children?: ReactNode }) {
  const [name, definition] = GLOSSARY[k]
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="term" tabIndex={0} />}>{children ?? name}</TooltipTrigger>
      <TooltipContent className="term-tip"><strong>{name}</strong><span>{definition}</span></TooltipContent>
    </Tooltip>
  )
}
