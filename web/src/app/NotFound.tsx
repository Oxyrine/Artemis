import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useTitle } from '@/ui/primitives'

export function NotFound() {
  useTitle('Page not found')
  return (
    <div className="mx-auto flex max-w-md flex-col items-start gap-3 py-16">
      <p className="text-sm font-medium text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">That page does not exist</h1>
      <p className="text-sm text-muted-foreground">The link may be old, or the case was cleared by a reset.</p>
      <Button render={<Link to="/" />}>Back to the dashboard</Button>
    </div>
  )
}
