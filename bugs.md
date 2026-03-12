# BUGS.md - CFD Trading Bot

## 2026-03-12

### Błąd #1: ModuleNotFoundError: strategy.strategy_manager
- **Status:** ✅ NAPRAWIONO
- **Data:** 2026-03-12 23:00
- **Opis:** Kod próbował zaimportować `from strategy.strategy_manager import get_strategy_manager` ale ten moduł nie istniał
- **Rozwiązanie:** Zmieniono import na `from services.strategy_manager import get_strategy_manager`
- **Plik:** `services/trading_engine.py` linie 191, 222

### Błąd #2: ImportError: signal_history_cache
- **Status:** ✅ NAPRAWIONO  
- **Data:** 2026-03-12 23:02
- **Opis:** Kod próbował zaimportować `signal_history_cache` z `main.py` ale zmienna nie istniała
- **Rozwiązanie:** Zmieniono na `from services.state import get_signal_history_cache`
- **Plik:** `services/trading_engine.py` linia 265

### Błąd #3: Dynamic Positions nie zamykało pozycji z słabym sygnałem
- **Status:** ✅ NAPRAWIONO
- **Data:** 2026-03-13 00:15
- **Opis:** 
  1. Pozycje US100 miały sygnał -0.097 (negatywny) ale nie były zamykane
  2. Problem: neutralne sygnały były filtrowane z current_signals
  3. Problem: open_positions był pusty (nie synchronizowany z brokerem)
- **Rozwiązanie:**
  1. Zmieniono `current_signals` żeby zawierał też neutralne/negatywne sygnały
  2. Dodano `open_positions = broker.get_open_positions()` na początku pętli
  3. Dodano logikę zamykania pozycji gdy sygnał spada poniżej 0
- **Plik:** `services/trading_engine.py` linia 111, 113, broker_sim.py linia 237+

### Wynik testu HEARTBEAT:
- ✅ Dashboard - działa
- ✅ Wykresy - działają
- ✅ Trading - strategie działają
- ✅ Pozycje otwarte - wyświetlanie OK
- ✅ Historia transakcji - OK
- ✅ Logi - OK (wcześniej były błędy, teraz czyste)
- ✅ Auto-trade - działa!
- ✅ Dynamic Positions - DZIAŁA! (US100 zamknięty z +$20.90)
