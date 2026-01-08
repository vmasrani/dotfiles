# Professional Frontend Dashboard Builder

## Objective

Build a **professional, enterprise-grade frontend dashboard** that displays data from a Python backend. Create a modern, responsive web application that follows industry best practices for data visualization, user experience, and performance.

## Technical Stack

### Core Technologies
- **React 18+** with hooks and concurrent features
- **Next.js 14+** with App Router for routing, SSR, and optimization
- **TypeScript** for type safety and developer experience
- **Tailwind CSS** for utility-first styling and responsive design
- **shadcn/ui** for consistent, accessible UI components

### Data Visualization & Charts
- **Recharts** for lightweight React charts (line, bar, pie, area)
- **Observable Plot** for advanced statistical visualizations
- **React Flow** for network diagrams and flowcharts
- **Tremor** for pre-built dashboard components

### State Management & Data Fetching
- **TanStack Query (React Query)** for server state management
- **Zustand** for client state management
- **SWR** as fallback for real-time data updates

### Development & Performance
- **Framer Motion** for smooth animations and transitions
- **React Hook Form** with Zod validation for forms
- **React Virtual** for large dataset rendering
- **next/image** for optimized image loading

## Professional Dashboard Requirements

### Visual Design Standards
- **Clean, minimal interface** following modern design principles
- **Consistent color palette** with primary, secondary, and accent colors
- **Professional typography** using system fonts or Google Fonts
- **Proper spacing and hierarchy** using 8px grid system
- **Dark/light theme support** with system preference detection
- **Responsive breakpoints**: Mobile (320px+), Tablet (768px+), Desktop (1024px+)

### User Experience Features
- **Loading states** with skeleton screens and progress indicators
- **Error boundaries** with graceful error handling and retry mechanisms
- **Toast notifications** for user feedback
- **Keyboard navigation** support for accessibility
- **Search and filtering** with debounced inputs
- **Data export** capabilities (CSV, PDF, Excel)
- **Real-time updates** with WebSocket support when applicable

### Dashboard Components
- **Executive summary cards** with key metrics and trends
- **Interactive charts** with zoom, pan, and drill-down capabilities
- **Data tables** with sorting, filtering, and pagination
- **Navigation sidebar** with collapsible sections
- **Header toolbar** with user profile, notifications, and settings
- **Breadcrumb navigation** for deep dashboard sections
- **Widget layout system** with drag-and-drop rearrangement

## Implementation Steps

### 1. Project Setup & Dependencies

```bash
npx create-next-app@latest frontend --typescript --app --tailwind --eslint
cd frontend

# UI Framework & Components
npm install @radix-ui/react-icons @radix-ui/react-slot class-variance-authority clsx tailwind-merge
npx shadcn-ui@latest init

# Data Fetching & State Management
npm install @tanstack/react-query @tanstack/react-query-devtools zustand
npm install axios swr

# Charts & Visualization
npm install recharts @observablehq/plot d3 react-flow-renderer
npm install @tremor/react

# Forms & Validation
npm install react-hook-form @hookform/resolvers zod

# UI Enhancements
npm install framer-motion react-virtual
npm install sonner # for toast notifications

# Development Tools
npm install -D @types/d3 eslint-config-prettier prettier
```

### 2. Project Structure

```
frontend/
├── app/
│   ├── layout.tsx                 # Root layout with providers
│   ├── page.tsx                   # Main dashboard page
│   ├── dashboard/
│   │   ├── analytics/page.tsx     # Analytics sub-dashboard
│   │   ├── reports/page.tsx       # Reports section
│   │   └── settings/page.tsx      # Dashboard settings
│   └── api/                       # API route handlers (if needed)
├── components/
│   ├── ui/                        # shadcn/ui components
│   ├── layout/
│   │   ├── DashboardLayout.tsx    # Main dashboard wrapper
│   │   ├── Sidebar.tsx            # Navigation sidebar
│   │   ├── Header.tsx             # Top navigation bar
│   │   └── Breadcrumbs.tsx        # Navigation breadcrumbs
│   ├── charts/
│   │   ├── LineChart.tsx          # Reusable line chart
│   │   ├── BarChart.tsx           # Reusable bar chart
│   │   ├── PieChart.tsx           # Reusable pie chart
│   │   └── MetricCard.tsx         # KPI display cards
│   ├── tables/
│   │   ├── DataTable.tsx          # Advanced data table
│   │   └── TableFilters.tsx       # Table filtering controls
│   └── forms/
│       ├── FilterForm.tsx         # Dashboard filters
│       └── ExportForm.tsx         # Data export controls
├── lib/
│   ├── api.ts                     # API client configuration
│   ├── utils.ts                   # Utility functions
│   ├── validations.ts             # Zod schemas
│   └── constants.ts               # App constants
├── hooks/
│   ├── useApi.ts                  # Custom API hooks
│   ├── useFilters.ts              # Filter state management
│   └── useExport.ts               # Data export functionality
├── types/
│   ├── api.ts                     # API response types
│   ├── dashboard.ts               # Dashboard-specific types
│   └── global.ts                  # Global type definitions
└── styles/
    └── globals.css                # Global styles and CSS variables
```

### 3. Advanced Data Management

```typescript
// lib/api.ts
import axios from 'axios'
import { QueryClient } from '@tanstack/react-query'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request/Response interceptors for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// hooks/useApi.ts
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'

export const useDashboardData = (filters?: Record<string, any>) => {
  return useQuery({
    queryKey: ['dashboard-data', filters],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/dashboard', { params: filters })
      return data
    },
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 5 * 60 * 1000, // Consider data stale after 5 minutes
  })
}

export const useExportData = () => {
  return useMutation({
    mutationFn: async (params: { format: string; filters?: any }) => {
      const { data } = await apiClient.post('/api/export', params)
      return data
    },
  })
}
```

### 4. Professional Dashboard Layout

```tsx
// app/layout.tsx
import { Inter } from 'next/font/google'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/sonner'

const inter = Inter({ subsets: ['latin'] })
const queryClient = new QueryClient()

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            {children}
            <Toaster />
          </ThemeProvider>
          <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
      </body>
    </html>
  )
}

// components/layout/DashboardLayout.tsx
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { Breadcrumbs } from './Breadcrumbs'

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-x-hidden overflow-y-auto">
          <div className="container mx-auto px-6 py-8">
            <Breadcrumbs />
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
```

### 5. Advanced Chart Components

```tsx
// components/charts/MetricCard.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { motion } from 'framer-motion'

interface MetricCardProps {
  title: string
  value: string | number
  change?: number
  format?: 'currency' | 'percentage' | 'number'
  loading?: boolean
}

export function MetricCard({ title, value, change, format = 'number', loading }: MetricCardProps) {
  if (loading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-8 bg-muted animate-pulse rounded" />
        </CardContent>
      </Card>
    )
  }

  const getTrendIcon = () => {
    if (!change) return <Minus className="h-4 w-4" />
    if (change > 0) return <TrendingUp className="h-4 w-4 text-green-600" />
    return <TrendingDown className="h-4 w-4 text-red-600" />
  }

  const formatValue = (val: string | number) => {
    if (format === 'currency') return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(val))
    if (format === 'percentage') return `${val}%`
    return val.toLocaleString()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          {getTrendIcon()}
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatValue(value)}</div>
          {change && (
            <p className="text-xs text-muted-foreground">
              {change > 0 ? '+' : ''}{change}% from last period
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
```

### 6. Data Table with Advanced Features

```tsx
// components/tables/DataTable.tsx
import { useState } from 'react'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  searchPlaceholder?: string
  onExport?: () => void
}

export function DataTable<TData, TValue>({
  columns,
  data,
  searchPlaceholder = "Search...",
  onExport,
}: DataTableProps<TData, TValue>) {
  const [globalFilter, setGlobalFilter] = useState('')

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      globalFilter,
    },
    onGlobalFilterChange: setGlobalFilter,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Input
          placeholder={searchPlaceholder}
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="max-w-sm"
        />
        {onExport && (
          <Button onClick={onExport} variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        )}
      </div>
      
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      
      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} of{' '}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <div className="flex items-center space-x-6 lg:space-x-8">
          <div className="flex items-center space-x-2">
            <p className="text-sm font-medium">Rows per page</p>
            <select
              value={table.getState().pagination.pageSize}
              onChange={(e) => table.setPageSize(Number(e.target.value))}
              className="h-8 w-[70px] rounded border border-input"
            >
              {[10, 20, 30, 40, 50].map((pageSize) => (
                <option key={pageSize} value={pageSize}>
                  {pageSize}
                </option>
              ))}
            </select>
          </div>
          <div className="flex w-[100px] items-center justify-center text-sm font-medium">
            Page {table.getState().pagination.pageIndex + 1} of{' '}
            {table.getPageCount()}
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              className="h-8 w-8 p-0"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="h-8 w-8 p-0"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

## Performance & Accessibility Standards

### Performance Optimizations
- **Code splitting** with dynamic imports for large components
- **Image optimization** using next/image with proper sizing
- **Bundle analysis** with @next/bundle-analyzer
- **Lazy loading** for charts and heavy components
- **Memoization** with React.memo and useMemo for expensive calculations
- **Virtual scrolling** for large datasets using react-virtual

### Accessibility Requirements
- **WCAG 2.1 AA compliance** for color contrast and navigation
- **Keyboard navigation** support for all interactive elements
- **Screen reader compatibility** with proper ARIA labels
- **Focus management** with visible focus indicators
- **Semantic HTML** structure with proper heading hierarchy
- **Alt text** for all images and charts

### Deployment & Production

```bash
# Build optimization
npm run build
npm run start

# Performance analysis
npm install -D @next/bundle-analyzer
ANALYZE=true npm run build

# Environment configuration
# .env.local
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_ENV=production
```

### Development Best Practices
- **Error boundaries** for graceful error handling
- **Loading states** for all async operations
- **Empty states** with clear messaging and actions
- **Form validation** with real-time feedback
- **API error handling** with retry mechanisms
- **Type safety** with comprehensive TypeScript coverage

## Deliverables

### Core Features
✅ **Responsive dashboard layout** with sidebar and header navigation  
✅ **Interactive data visualizations** with multiple chart types  
✅ **Advanced data tables** with filtering, sorting, and pagination  
✅ **Real-time data updates** with optimistic updates  
✅ **Professional UI/UX** following modern design principles  
✅ **Export functionality** for charts and data tables  
✅ **Theme support** with dark/light mode toggle  
✅ **Performance optimization** with lazy loading and code splitting  

### Quality Assurance
- **TypeScript coverage** at 95%+ with strict mode enabled
- **Accessibility testing** with axe-core and manual testing
- **Performance testing** with Lighthouse scores 90+
- **Cross-browser compatibility** tested on Chrome, Firefox, Safari, Edge
- **Mobile responsiveness** tested on various device sizes
