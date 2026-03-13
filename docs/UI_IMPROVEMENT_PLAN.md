# UI Improvement Plan — CFD Trading Bot Dashboard

**Data utworzenia:** 2026-03-13  
**Branch:** `feature/unified-backtest-fixes-2026-03-11`  
**Status:** Wstępny plan zmian

---

## 🎯 Cel

Poprawa UX dashboardu głównego, szczególnie w zakresie edycji pozycji (TP/SL drag), markerów transakcji oraz czytelności wskaźników technicznych.

---

## 🐛 Krytyczne Fixy TP/SL Drag

### Dlaczego TP/SL drag nadal nie działa

Po analizie kodu `CandlestickChart.tsx` zidentyfikowano **3 pozostałe błędy**:

#### Bug #1: `useCallback` deps zawiera `draggingLine` → stale closure
```ts
// ❌ BŁĄD (linia ~561)
}, [draggingLine, selectedPosition, dragLineStartY, dragLineStartValue, priceRange, priceChartH, totalH, containerRef]);
```
**Fix:** Usuń `draggingLine` i `containerRef` z deps. Ref jest mutable, nie ma wartości reaktywnej.

#### Bug #2: `useEffect` usuwa/dodaje listenery przy każdym renderze
**Problem:** `handleLineDragMove` zmienia referencję (re-render), co powoduje unmount/remount listenera `mousemove`.
**Fix:** Użyj `useRef` dla handlera i rejestruj listener tylko raz w `useEffect(() => ..., [draggingLine])`.

#### Bug #3: SVG `onMouseDown` vs TP/SL Line
**Problem:** `e.stopPropagation()` w `handleLineDragStart` może nie blokować globalnego `handleMouseDown` na poziomie SVG, jeśli zdarzenia nie są poprawnie obsłużone.
**Fix:** Upewnij się, że `pointer-events: all` jest na liniach TP/SL, a `handleMouseDown` ignoruje kliknięcia w te elementy.

---

## 📉 Fix Markerów Pozycji (Trade Markers)

**Problem:** Strzałki wejścia/wyjścia pojawiają się na lewym brzegu wykresu (X=0 lub bliskie 0).

**Przyczyna:** Błąd w mapowaniu `idxToX` przy dynamicznej liczbie świec.
- `validData` to wycinek `allValidData` po okresie warmup (np. pierwsze 20 świec).
- `effectiveEntryIdx` może odnosić się do indeksu w `allValidData`, podczas gdy `idxToX` oczekuje indeksu relatywnego do `validData`.
- Jeśli `idx < 0`, funkcja `idxToX` zwraca wartości na lewym marginesie.

**Fix:**
```ts
// W trades.map upewnij się, że index jest poprawnie obliczony względem validData:
const effectiveEntryIdx = validData.findIndex(c => ...); 
if (effectiveEntryIdx === -1) return null; // Nie rysuj, jeśli świecy nie ma w widocznym zakresie
```

---

## 📈 Fix Wskaźników (SMA, RSI, MACD)

**Problem:** Wskaźniki nie pokrywają całego wykresu, kończą się wcześniej lub są przesunięte.

**Przyczyna:** Niezgodność indeksowania polylinii.
- Wskaźniki (RSI, SMA) są liczone na pełnej tablicy `allValidData`.
- Rendering (`idxToX`) operuje na długości `n = validData.length`.
- Jeśli pętla rysująca (np. `rsiPolyline`) leci po całej długości `indicators.rsi.length`, a `idxToX` używa `n` z wycinka, to punkty są mapowane błędnie (wszystkie "stare" dane z warmupu lądują na lewym brzegu).

**Fix:** Wszystkie funkcje pomocnicze (`toPolyline`, `rsiPolyline`) muszą używać wycinków wskaźników, które odpowiadają `validData`.
```ts
// Przykład:
const displayRsi = indicators.rsi.slice(bbWarmup);
// Potem w rsiPolyline:
for (let i = 0; i < displayRsi.length; i++) {
  const x = idxToX(i); // i od 0 do n-1
  // ...
}
```

---

## 📊 Zmiany UI/UX Dashboardu
docs: add UI improvement plan with technical fixes for drag, markers and indicators
### 1. **Chart Area**
- [ ] Zwiększ `height` do **420px**.
- [ ] Zwiększ panele wskaźników: RSI (**70px**), MACD (**60px**), Volume (**50px**).
- [ ] Dodaj **Live Price Tick** na prawej osi Y (zielony/czerwony badge).

### 2. **Open Positions**
- [ ] Karty pozycji z kolorowym lewym borderem (BUY/SELL).
- [ ] **Progress Bar** wizualizujący odległość ceny od SL i TP.
- [ ] P&L z informacją o czasie trwania pozycji (np. `1h 24m`).
- [ ] Przycisk **"📈 Chart"** centrujący widok na danej pozycji.

### 3. **Sidebar & Alerts**
- [ ] **Drawdown Alert Box** (widoczny jeśli DD > 5%).
- [ ] Mini wykres kołowy (Donut) dla **Win Rate**.

---

## 🚀 Plan Implementacji

### Faza 1: Fixy techniczne (Piority 🔴)
- [ ] Naprawa `idxToX` i synchronizacja indeksów wskaźników/markerów.
- [ ] Stabilizacja TP/SL drag (useRef, listener fix).
- [ ] Usunięcie "skakania" linii przy kliknięciu.

### Faza 2: Poprawa Czytelności (Piority 🟡)
- [ ] Layout wykresu (wysokość, proporcje paneli).
- [ ] Live price label na osi Y.

### Faza 3: Nowy Dashboard UI (Piority 🟢)
- [ ] Nowe karty pozycji.
- [ ] Progress bary SL/TP.

---

**Ostatnia aktualizacja:** 2026-03-13 01:15 CET
