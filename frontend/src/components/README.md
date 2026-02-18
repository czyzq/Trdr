# CFD Trading Bot - React Dashboard Components

A dark-themed, green-accent dashboard UI component library for the CFD trading bot. Inspired by terminal-based trading interfaces with a focus on real-time data visualization and minimal, data-focused design.

## 🎨 Design Aesthetic

- **Color Scheme**: Dark background (#0a0e27) with green accents (#00ff41)
- **Typography**: Monospace fonts (Monaco, Courier New) for a terminal feel
- **Style**: Minimal, data-focused with subtle borders and clean layouts
- **Vibe**: Professional, high-information-density dashboard inspired by Bloomberg terminals and advanced trading platforms

## 📦 Components

### Dashboard.tsx (Main Container)

The primary component that orchestrates the entire interface.

**Features:**

- Header with title, version badge, and live status
- Tab navigation (Signals, History, Console, Settings)
- Left sidebar integration
- Responsive layout with footer

**Props:**

```typescript
interface DashboardProps {
  title?: string; // Default: 'CFD Trading Bot'
  version?: string; // Default: 'v2.1.0'
}
```

**Usage:**

```tsx
import { Dashboard } from "./components";

export default function App() {
  return <Dashboard title="My Trading Dashboard" version="v1.0.0" />;
}
```

---

### Sidebar.tsx (Account Stats)

Left sidebar displaying account information and scanner configuration.

**Features:**

- Account balance and equity display
- Active positions and signals count
- Margin usage and win rate
- Scanner configuration settings
- Live scanning status indicator

**Props:**

```typescript
interface SidebarProps {
  balance?: number; // Default: 25000
  activePositions?: number; // Default: 3
  activeSignals?: number; // Default: 12
  equity?: number; // Default: 25300
  marginUsed?: number; // Default: 45 (%)
  winRate?: number; // Default: 62.5 (%)
}
```

**Usage:**

```tsx
import { Sidebar } from "./components";

<Sidebar
  balance={50000}
  activePositions={5}
  activeSignals={15}
  equity={51200}
  marginUsed={60}
  winRate={68.5}
/>;
```

---

### SignalsGrid.tsx (Signals Table)

Main trading signals display with color-coded scores and mini sparkline charts.

**Features:**

- Real-time signal table with symbol, score, direction
- Color-coded score indicator (red -1 to green +1)
- Mini sparkline charts showing trend
- Entry price, Take Profit, Stop Loss levels
- Risk/Reward ratio display
- Interactive rows (clickable for more details)

**Props:**

```typescript
interface Signal {
  id: string;
  symbol: string;
  score: number; // -1 to +1
  direction: "BUY" | "SELL";
  entryPrice: number;
  takeProfit: number;
  stopLoss: number;
  trend: number[]; // sparkline data points
  confidence: number;
  riskReward: number;
}

interface SignalsGridProps {
  signals?: Signal[];
  onSignalClick?: (signal: Signal) => void;
}
```

**Usage:**

```tsx
import { SignalsGrid } from "./components";

const signals = [
  {
    id: "1",
    symbol: "EURUSD",
    score: 0.75,
    direction: "BUY",
    entryPrice: 1.0945,
    takeProfit: 1.105,
    stopLoss: 1.085,
    trend: [0.45, 0.52, 0.61, 0.68, 0.72, 0.75],
    confidence: 0.92,
    riskReward: 2.0,
  },
];

<SignalsGrid
  signals={signals}
  onSignalClick={(signal) => console.log("Clicked:", signal)}
/>;
```

---

### ConsoleTab.tsx (Event Logs)

Console/logging display showing real-time events, connections, and system messages.

**Features:**

- Color-coded log entries (info, success, warning, error, event)
- Auto-scroll to latest message
- Timestamp display for each entry
- Log entry counter
- Clean monospace formatting

**Props:**

```typescript
interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: "info" | "success" | "warning" | "error" | "event";
}

interface ConsoleTabProps {
  logs?: LogEntry[];
  maxLogs?: number; // Default: 100
}
```

**Usage:**

```tsx
import { ConsoleTab } from "./components";

const logs = [
  {
    id: "1",
    timestamp: "13:10:45",
    message: "Initializing MCP connections...",
    type: "info",
  },
  {
    id: "2",
    timestamp: "13:10:45",
    message: "✓ Connected: Polymarket REST API",
    type: "success",
  },
];

<ConsoleTab logs={logs} maxLogs={100} />;
```

---

### ScoreGauge.tsx (Visual Score Indicator)

A circular gauge component for displaying signal scores from -1 to +1.

**Features:**

- Circular progress indicator
- Color-coded based on score (red → yellow → green)
- Smooth animations
- Three size options (sm, md, lg)
- Displays score value and label

**Props:**

```typescript
interface ScoreGaugeProps {
  score: number; // -1 to +1
  size?: "sm" | "md" | "lg"; // Default: 'md'
}
```

**Usage:**

```tsx
import { ScoreGauge } from './components';

<ScoreGauge score={0.75} size="md" />
<ScoreGauge score={-0.45} size="lg" />
<ScoreGauge score={0.25} size="sm" />
```

---

## 🎯 Color Reference

| Use Case       | Color        | Hex       |
| -------------- | ------------ | --------- |
| Background     | Dark Navy    | #0a0e27   |
| Primary Accent | Neon Green   | #00ff41   |
| Success/Buy    | Bright Green | #00ff41   |
| Error/Sell     | Bright Red   | #ff1f1f   |
| Warning        | Yellow       | #ffff00   |
| Secondary Text | Gray         | #666-#aaa |
| Borders        | Dark Green   | #1a1f2e   |

---

## 🚀 Getting Started

### Installation

Ensure your React project has Tailwind CSS configured (components use Tailwind utility classes).

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Setup

1. Copy all component files to `/src/components/`
2. Ensure `tailwind.config.js` includes the components path:

```js
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./src/components/**/*.{ts,tsx}"],
  // ... rest of config
};
```

3. Import and use in your app:

```tsx
import { Dashboard } from "./components";

export default function App() {
  return <Dashboard />;
}
```

---

## 📊 Placeholder Data

All components include sensible default placeholder data:

- **Dashboard**: Live trading session with sample signals
- **Sidebar**: Account with $25k balance, 3 active positions
- **SignalsGrid**: 6 sample signals across various markets
- **ConsoleTab**: Initialization and connection logs
- **ScoreGauge**: Demonstration of score display

---

## 🔧 Customization

### Styling

All color values are inline, making them easy to customize:

```tsx
// Change the accent color throughout
style={{ backgroundColor: '#0a0e27', color: '#00ff41' }}
// to your preferred colors
style={{ backgroundColor: '#0a0e27', color: '#ff00ff' }}
```

### Typography

Components use `font-mono` class for monospace styling. Customize in Tailwind config:

```js
theme: {
  fontFamily: {
    mono: ['IBM Plex Mono', 'monospace'],
  }
}
```

### Responsive Behavior

Components are built to work at any screen size. Adjust gap, padding, and font sizes as needed:

```tsx
className = "px-4 py-3"; // padding
className = "text-xs"; // font size
className = "gap-4"; // spacing
```

---

## 📝 Data Flow

```
Dashboard (Main)
├── Sidebar (Account Stats)
├── SignalsGrid (Current Signals)
│   └── ScoreGauge (Score Display)
├── ConsoleTab (Event Logs)
└── Settings/History (Placeholder)
```

---

## ✨ Features Demonstrated

✅ Dark terminal-inspired UI  
✅ Real-time signal visualization  
✅ Color-coded data values  
✅ Responsive grid layout  
✅ Mini chart sparklines  
✅ Interactive components (clickable rows, tabs)  
✅ Monospace typography  
✅ Minimal, data-focused design  
✅ Placeholder data system  
✅ Type-safe TypeScript interfaces

---

## 🛠️ Future Enhancements

- [ ] WebSocket integration for live updates
- [ ] Advanced charting library (Lightweight Charts, TradingView)
- [ ] Drag-and-drop signal management
- [ ] Settings panel implementation
- [ ] Trade history with advanced filters
- [ ] Alert notifications system
- [ ] Dark/Light theme toggle
- [ ] Export functionality (CSV, PDF)
- [ ] Mobile responsive design refinement
- [ ] Keyboard shortcuts

---

## 📄 License

Part of the CFD Trading Bot project. All components included for frontend development.
