import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Layout } from '@/app/layout'
import { NotFound } from '@/app/NotFound'
import { ReviewerProvider, ThemeProvider } from '@/app/providers'
import { AuditPage } from '@/features/audit/AuditPage'
import { CasePage } from '@/features/case/CasePage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 2000, retry: 1, refetchOnWindowFocus: false } } })

const router = createBrowserRouter([
  { element: <Layout />, children: [
    { path: '/', element: <DashboardPage /> },
    { path: '/cases/:caseId', element: <CasePage /> },
    { path: '/audit', element: <AuditPage /> },
    { path: '*', element: <NotFound /> },
  ] },
])

export default function App() {
  return (
    <ThemeProvider><ReviewerProvider><QueryClientProvider client={queryClient}><TooltipProvider>
      <RouterProvider router={router} />
    </TooltipProvider></QueryClientProvider></ReviewerProvider></ThemeProvider>
  )
}
