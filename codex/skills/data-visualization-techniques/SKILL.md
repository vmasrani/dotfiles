---
name: data-visualization-techniques
description: This skill should be used when creating charts, graphs, dashboards, or data visualizations - covers chart type selection, D3.js patterns, Recharts usage, dashboard design principles, and data storytelling techniques for analytics-reporter and finance-tracker agents.
---

# Data Visualization Techniques

## Overview

Transform data into clear, actionable visualizations. Choose the right chart types, design effective dashboards, and tell compelling data stories.
**Core principle:** Visualizations exist to answer questions, not just display data.

## When to Use

**Use when:**

- Building dashboards or analytics
- Presenting data to users
- Creating reports
- Visualizing trends or patterns
- Comparing metrics
- Showing relationships in data

## Chart Type Selection

| Data Question | Chart Type | Use For |
|---------------|------------|---------|
| **How does X change over time?** | Line chart | Trends, time series |
| **How do categories compare?** | Bar chart | Comparing quantities |
| **What's the composition?** | Pie/Donut | Parts of whole (<6 categories) |
| **What's the relationship?** | Scatter plot | Correlation between variables |
| **What's the distribution?** | Histogram | Data spread and frequency |
| **How does X compare to goal?** | Progress bar | Goals and achievements |
| **What's the trend + detail?** | Area chart | Cumulative trends |

### Quick Selection Guide

```
Time series data → Line chart
Comparing categories → Bar chart
Parts of whole → Donut chart (not pie)
2 variables correlation → Scatter plot
Distribution → Histogram
Progress to goal → Progress bar
Multiple series over time → Multi-line or stacked area
```

## React Charting Libraries

### Recharts (Recommended for Most Cases)

**Why:** Simple API, responsive, good defaults, TypeScript support

```typescript
import {LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer} from 'recharts'
const data = [
  {date: 'Jan', users: 400},
  {date: 'Feb', users: 600},
  {date: 'Mar', users: 800},
]
function GrowthChart() {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="users" stroke="#3B82F6" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### Chart.js (Alternative)

**Why:** More chart types, extensive documentation

### D3.js (For Custom Visualizations)

**Why:** Maximum flexibility, complex visualizations
**When:** Custom charts, advanced interactions
**Trade-off:** Steeper learning curve

## Dashboard Design Principles

### Layout Hierarchy

```
┌─────────────────────────────────┐
│  KPI Cards (Big Numbers)        │ ← Most important
├─────────────────────────────────┤
│  Primary Chart (Trend)          │ ← Main insight
├─────────────────────────────────┤
│  Supporting Charts (Grid)       │ ← Details
│  ┌──────┐ ┌──────┐ ┌──────┐   │
│  │Chart1│ │Chart2│ │Chart3│   │
│  └──────┘ └──────┘ └──────┘   │
└─────────────────────────────────┘
```

### KPI Cards

```typescript
function KPICard({title, value, change, trend}: KPIProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        <div className={trend === 'up' ? 'text-green-600' : 'text-red-600'}>
          {change} from last period
        </div>
      </CardContent>
    </Card>
  )
}
<KPICard
  title="Total Users"
  value="12,547"
  change="+2,341 (23%)"
  trend="up"
/>
```

### Color Palette for Data

**Qualitative (categories):**

```
#3B82F6 (blue)
#10B981 (green)
#F59E0B (amber)
#EF4444 (red)
#8B5CF6 (purple)
#EC4899 (pink)
```

**Sequential (low to high):**

```
#EFF6FF → #3B82F6 → #1E40AF (light blue to dark blue)
```

**Diverging (negative to positive):**

```
#EF4444 (red) → #F3F4F6 (gray) → #10B981 (green)
```

### Accessibility

- Don't rely on color alone (use patterns, labels)
- Ensure sufficient contrast
- Provide text alternatives
- Support keyboard navigation
- Screen reader friendly alt text

## Common Patterns

### Time Series

```typescript
const data = [
  {month: 'Jan', revenue: 5000, expenses: 3000},
  {month: 'Feb', revenue: 7000, expenses: 3500},
  // ...
]
<ResponsiveContainer width="100%" height={300}>
  <LineChart data={data}>
    <XAxis dataKey="month" />
    <YAxis />
    <Tooltip />
    <Line dataKey="revenue" stroke="#10B981" name="Revenue" />
    <Line dataKey="expenses" stroke="#EF4444" name="Expenses" />
  </LineChart>
</ResponsiveContainer>
```

### Comparison Bar Chart

```typescript
<BarChart data={data}>
  <XAxis dataKey="category" />
  <YAxis />
  <Tooltip />
  <Bar dataKey="value" fill="#3B82F6" />
</BarChart>
```

### Progress Indicators

```typescript
function ProgressBar({value, max, label}: ProgressProps) {
  const percentage = (value / max) * 100
  return (
    <div>
      <div className="flex justify-between mb-2">
        <span>{label}</span>
        <span>{value} / {max}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all"
          style={{width: `${percentage}%`}}
        />
      </div>
    </div>
  )
}
```

## Data Storyt[Ielling

**Good visualizations:**

- Answer a specific question
- Show comparison (vs last period, vs goal)
- Highlight insights (annotations, color)
- Provide context (What's normal? What's good?)
**Example:**

```
❌ Just showing numbers:
"Revenue: $50,000"
✅ With context and insight:
"Revenue: $50,000 (+23% vs last month)
🎯 Hit Q4 goal 2 weeks early"
```

## Resources

- Recharts: recharts.org
- shadcn/ui Chart components: ui.shadcn.com
- D3.js: d3js.org
- Color palette: tailwindcss.com/docs/customizing-colors
Visualizations should clarify, not confuse. Choose the right chart, design for clarity, tell the story in the data.
