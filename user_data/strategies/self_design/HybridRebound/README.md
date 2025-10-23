# HybridRebound Strategy

> **Methodology-First Rebound Trading with Pure Freqtrade Built-ins**

## 🎯 Strategy Overview

HybridRebound is a rebound-focused trading strategy that only enters positions after market de-leverage and panic release conditions are met. It combines:

- **Market Gate**: Environment filter (BTC 1h EMA200 trend)
- **Entry Triggers**: Multi-signal confirmation (≥2 of 4 triggers required)
- **Vol-Target Sizing**: Dynamic position sizing based on volatility (1.2-1.8% target)
- **Dynamic Risk Management**: ATR-based stops + time stops + partials + circuit breakers

---

## 📋 Core Components

### 1. Market Gate (When System is Allowed to Open)

**Environment Check** (BTC/USDT 1h):
- Price above EMA200 **OR** EMA200 slope > 0
- Ensures we're not fighting major downtrend

**De-leverage Detection** (proxy using OHLCV):
- Violent flush: price drop > 5% threshold
- Fast reclaim: recovery of ≥50% of candle range
- Closes green after the flush

**Panic Release** (proxy using indicators):
- Price touches/breaks Keltner lower band, then reclaims
- RSI rebounds from oversold (<25) to >32
- 2+ consecutive green candles

---

### 2. Entry Triggers (Require ≥2 to Fire)

| Trigger | Description | Default |
|---------|-------------|---------|
| **Sweep-and-Reclaim** | Price pierces prior swing low, closes above it | 20-candle lookback |
| **Volume Spike** | Volume > 1.5x mean | 20-period mean |
| **RSI Rebound** | RSI crosses from <25 → >32 | Standard settings |
| **Bullish Momentum** | 2+ consecutive bullish candles | Configurable |

**Logic**: At least 2 of these 4 triggers must be active for entry signal.

---

### 3. Vol-Target Position Sizing

**Formula**:
```python
vol_scale = target_vol / current_vol
vol_scale = clip(vol_scale, 0.5, 1.5)  # Safety bounds
stake = proposed_stake * vol_scale
stake = min(stake, proposed_stake * 2.0)  # Hard cap
```

**Parameters**:
- `vol_target_pct`: 1.2-1.8% (default 1.5%)
- Uses ATR/close as volatility proxy
- Higher volatility → smaller position
- Lower volatility → larger position

---

### 4. Exit & Risk Management

#### Partial Exits (Quick Profit Taking)
- **Partial 1**: 40% at +2% profit
- **Partial 2**: 30% at +4% profit  
- **Remainder**: Trails with 2.0x ATR distance

#### Dynamic ATR-Based Stoploss
- **Initial stop**: 1.5x ATR distance (typically 1.0-1.8% for volatile coins)
- **Trailing stop**: Activates at +2% profit, trails at 2.0x ATR
- Never moves down, only up

#### Time-Based Stop
- If P&L doesn't escape breakeven in 45 minutes → force exit
- Prevents capital being stuck in stagnant positions

#### Circuit Breakers (Protections)
| Protection | Trigger | Cooldown |
|------------|---------|----------|
| **Per-Pair Stoploss Guard** | 2 consecutive losses | 48 hours |
| **Max Drawdown** | -2% daily drawdown | 24 hours |
| **Cooldown Period** | After each trade | 30 minutes |

---

## 🚀 Getting Started

### Prerequisites
```bash
# Freqtrade version
freqtrade >= 2023.8  # For custom_exit support

# Python packages (if not already installed)
pip install -r requirements.txt
```

---

## � Recommended Workflow

**IMPORTANT: Follow this sequence to avoid overfitting!**

```
1. Backtest First (quickstart.sh)
   ↓
2. Analyze Results (analyze_events.sh)
   ↓
3. Understand Baseline Behavior
   - Check trigger distribution
   - Review entry frequency
   - Validate methodology assumptions
   ↓
4. Optional: Dry-Run Event Study (Phase 1)
   - Observe 10 real entry signals
   - Document actual behavior
   - Verify logic in live conditions
   ↓
5. Hyperopt (Only After Understanding!)
   - Tune parameters based on insights
   - Validate improvements make logical sense
   - Re-test on different time periods
   ↓
6. Final Validation
   - Walk-forward testing
   - Out-of-sample verification
```

### ⚠️ Common Mistakes to Avoid

| ❌ Wrong Approach | ✅ Correct Approach |
|------------------|---------------------|
| Run hyperopt immediately | Backtest first to establish baseline |
| Optimize on one time period | Test across multiple market regimes |
| Accept all hyperopt results | Validate changes make logical sense |
| Skip event analysis | Understand why trades win/lose |
| Ignore left-tail events | Analyze worst-case scenarios |

### 🎯 Decision Tree

**"Should I backtest or hyperopt first?"**
```
Q: Do you understand the strategy's baseline behavior?
│
├─ NO  → Run quickstart.sh → Analyze results → Learn patterns → THEN hyperopt
│
└─ YES → Do optimization results make logical sense?
          │
          ├─ NO  → Parameters may be overfit → Extend test period
          │
          └─ YES → Validate on out-of-sample data → Deploy if stable
```

**Key Principle**: *Methodology first, optimization second.*

---

## �📖 Usage Guide

### Quick Start (Automated)

The easiest way to verify the strategy is using the provided script:

```bash
cd user_data/strategies/self_design/HybridRebound
./quickstart.sh
```

This will automatically:
1. ✅ Download market data (BTC/ETH/SOL, 15m & 1h)
2. ✅ Test strategy syntax
3. ✅ Run quick backtest (30 days)
4. ✅ Run extended backtest (3 months)
5. ✅ Export results for analysis

---

### Manual Usage

#### Step 1: Download Data

```bash
freqtrade download-data \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
  --timerange 20240701-20241022 \
  --timeframes 15m 1h \
  --pairs BTC/USDT ETH/USDT SOL/USDT
```

#### Step 2: Test Strategy Syntax

```bash
freqtrade test-pairlist \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
  --quote USDT
```

#### Step 3: Run Backtest

**Quick test (30 days)**:
```bash
freqtrade backtesting \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
  --strategy HybridRebound \
  --timerange 20240922-20241022 \
  --breakdown day week
```

**Full test (3 months)**:
```bash
freqtrade backtesting \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
  --strategy HybridRebound \
  --timerange 20240722-20241022 \
  --export trades \
  --export-filename user_data/backtest_results/hybridrebound_3m.json \
  --breakdown day week month
```

#### Step 4: Analyze Results

```bash
cd user_data/strategies/self_design/HybridRebound
./analyze_events.sh
```

Or manually:
```bash
freqtrade backtesting-analysis \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
  --analysis-groups 0 1 2 3 \
  --enter-reason-list rebound_2trig rebound_3trig rebound_4trig
```

#### Step 5: Start Dry-Run (Paper Trading)

```bash
freqtrade trade \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound.json \
  --strategy HybridRebound
```

**Monitor in another terminal**:
```bash
tail -f user_data/logs/freqtrade_hybridrebound.log
```

---

### Configuration Files

Two config files are provided in the HybridRebound folder:

1. **`config_hybridrebound.json`** - For live/dry-run trading
   - Dry-run mode enabled by default
   - Full protection settings active
   - Logging to dedicated file

2. **`config_hybridrebound_backtest.json`** - For backtesting
   - Optimized for backtest performance
   - Export settings pre-configured
   - Hyperopt ready

---

---

## 📊 Backtesting Guide

### Basic Backtest
```bash
freqtrade backtesting \
  --strategy HybridRebound \
  --timeframe 15m \
  --timerange 20240101-20241022 \
  --stake-amount unlimited \
  --max-open-trades 3
```

### Event Study Analysis
To analyze individual entry events:

```bash
freqtrade backtesting \
  --strategy HybridRebound \
  --timeframe 15m \
  --timerange 20240101-20241022 \
  --export trades \
  --export-filename user_data/backtest_results/hybridrebound_events.json
```

Then analyze forward returns around each entry:
```python
# See event_study_analysis.py for detailed implementation
python user_data/strategies/self_design/event_study_analysis.py
```

---

## 🔧 Hyperopt Optimization

### Optimize Entry Triggers
```bash
freqtrade hyperopt \
  --strategy HybridRebound \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy \
  --epochs 500 \
  --timerange 20240101-20240630
```

### Optimize Exit/Risk Management
```bash
freqtrade hyperopt \
  --strategy HybridRebound \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces sell \
  --epochs 500 \
  --timerange 20240101-20240630
```

### Key Parameters to Tune

**Buy Space**:
- `deleverage_drop_threshold`: Flush sensitivity
- `panic_rsi_oversold`/`panic_rsi_rebound`: Panic release levels
- `sweep_lookback`: Sweep-low detection window
- `volume_spike_multiplier`: Volume confirmation threshold
- `vol_target_pct`: Position size target volatility

**Sell Space**:
- `partial_1_profit`, `partial_2_profit`: Partial exit levels
- `stoploss_atr_multiplier`: Initial stop distance
- `time_stop_minutes`: Timeout threshold

---

## 📈 Performance Metrics

### Expected Characteristics

| Metric | Target Range |
|--------|--------------|
| **Win Rate** | 45-55% |
| **Avg Win/Loss Ratio** | 2.0-3.0 |
| **Monthly Trigger Count** | 20-40 (per pair) |
| **Avg Trade Duration** | 1-6 hours |
| **Max Drawdown** | <15% |
| **Sharpe Ratio** | >1.5 |

### Key Performance Indicators (KPIs)

Monitor these in backtests:
1. **Entry Event Analysis**: ±10-candle forward returns (mean, median, quantiles)
2. **Gate Open Rate**: % of time market gate is open
3. **Trigger Distribution**: Which triggers fire most often
4. **Left-Tail Risk**: 5th percentile return per event
5. **Cooldown Hit Rate**: How often protections activate
6. **Intra-Day P&L**: 95th percentile daily drawdown

---

## 🔍 Debugging & Monitoring

### Enable Debug Logging
```bash
freqtrade trade \
  --strategy HybridRebound \
  --config config.json \
  --logfile user_data/logs/hybridrebound.log \
  --verbosity 3
```

### Check Entry Tags
Entry signals include debug tags:
- `rebound_2trig`, `rebound_3trig`, `rebound_4trig`

Shows how many triggers fired on entry.

### Monitor Vol-Target Sizing
Add to custom info logs:
```python
# In populate_indicators()
dataframe['vol_scale']  # Current size multiplier
dataframe['atr_pct']    # Current volatility %
```

---

## 🧪 Testing Regimes

Test across different market conditions:

### High Volatility (Optimal)
```bash
--timerange 20240315-20240415  # Crypto high-vol period
```

### Quiet Market (Challenging)
```bash
--timerange 20240801-20240901  # Summer doldrums
```

### Trending Market
```bash
--timerange 20231001-20231101  # Strong uptrend
```

### Compare Performance
Look for:
- ✅ Positive expectancy in high-vol regimes
- ⚠️ Low trade count but acceptable returns in quiet markets
- ✅ Reduced drawdown in downtrends (gate should block trades)

---

## 📝 Iteration Roadmap

### Phase 1: D0-D1 (Current)
- [x] Pure built-in implementation
- [x] Multi-TF market gate
- [x] Vol-Target sizing
- [x] Dynamic stops & partials
- [x] Circuit breakers
- [ ] Dry-run 10 typical events (see "Dry-Run Event Study" below)
- [ ] Screenshot & document behavior (see "Dry-Run Event Study" below)

### Phase 2: D2-D4 
- [ ] Tune trigger thresholds (start with ≥2, test ≥3)
- [ ] Optimize vol-target range (1.2-1.8%)
- [ ] Adjust time stop window
- [ ] Compare results across regimes

### Week 1 Report
- [ ] Event-study curves (forward returns)
- [ ] Left-tail analysis (5th percentile)
- [ ] Entry frequency assessment
- [ ] If too few entries → relax triggers
- [ ] If left-tail heavy → tighten triggers/reduce size

### Week 2+ (Enhancement Caps)
- [ ] Add stable-coin net inflow data (position cap switch)
- [ ] Add BTC spot-ETF 3-day net inflow (position cap switch)
- [ ] Implement carry-tilt (funding rate adjustment)
- [ ] Dynamic pair selection (top-10 volume, vol ≥2%)
- [ ] Correlation control (avoid >0.9 corr pairs)

---

## 📸 Dry-Run Event Study (Phase 1 Completion)

To complete Phase 1, you need to observe ~10 actual entry events in dry-run mode and document their behavior.

### Step 1: Start Dry-Run Mode

```bash
# Start the bot
freqtrade trade \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound.json \
  --strategy HybridRebound \
  --verbosity 3
```

### Step 2: Monitor for Entry Signals

Watch the log file for entries:
```bash
tail -f user_data/logs/freqtrade_hybridrebound.log | grep "enter_long"
```

### Step 3: Document Each Entry Event

For each entry, capture:

**A. Entry Context** (when signal fires):
```bash
# Check current market conditions
freqtrade show_trades --db-url sqlite:///user_data/tradesv3_hybridrebound.sqlite

# Take note of:
# - Which triggers fired (check enter_tag: rebound_2trig, 3trig, or 4trig)
# - BTC 1h EMA200 status (above/below)
# - Current volatility (atr_pct value)
# - Vol-scale applied (check log for custom_stake_amount)
```

**B. Trade Evolution** (±10 candles / ~2.5 hours):
- Screenshot the FreqUI chart (if enabled) or use plot-dataframe
- Note price action around entry
- Track when/if partials hit (+2%, +4%)
- Record final exit reason (ROI, stoploss, time-stop, etc.)

**C. Event Metrics**:
```python
# For each trade, calculate:
# - Entry price
# - Max profit reached
# - Max drawdown from entry
# - Time to first partial (if any)
# - Time to final exit
# - Trigger combination that fired
# - Final P&L %
```

### Step 4: Generate Visual Documentation

**Option A: Using FreqUI** (if enabled):
1. Open `http://localhost:8080`
2. Navigate to each trade
3. Screenshot the chart showing entry/exit
4. Save to `docs/events/` folder

**Option B: Using plot-dataframe**:
```bash
# For each trade, generate chart
freqtrade plot-dataframe \
  --config user_data/strategies/self_design/HybridRebound/config_hybridrebound.json \
  --strategy HybridRebound \
  --pairs BTC/USDT \
  --timerange 20241020-20241022 \
  --indicators1 ema_200_1h kc_upper kc_lower rsi \
  --indicators2 volume_spike atr_pct vol_scale
```

Charts saved to `user_data/plot/`

### Step 5: Create Event Summary

Create a markdown file documenting all events:

```markdown
# HybridRebound Phase 1 Event Study

## Summary Statistics (10 Events)
- Total trades: 10
- Winners: X (X%)
- Avg P&L: X%
- Avg duration: X hours
- Trigger distribution:
  - 2-trig: X
  - 3-trig: X
  - 4-trig: X

## Event Details

### Event 1: BTC/USDT 2024-10-20 14:30
- **Entry tag**: rebound_3trig
- **Triggers**: Sweep-reclaim + Volume + RSI
- **Entry price**: $67,450
- **Vol-scale**: 1.2x (low volatility)
- **Outcome**: +2.5% in 90min
- **Exit**: Partial 1 hit, remainder trailing stop
- **Notes**: Clean rebound after BTC flush

[Screenshot/Chart]

### Event 2: ETH/USDT 2024-10-21 09:15
...
```

### Step 6: Analyze Patterns

After documenting 10 events, look for:

**✅ What's Working:**
- Which trigger combinations have best outcomes?
- Is vol-target sizing behaving correctly?
- Are partials getting hit or full exits more common?
- Time-stop effectiveness

**⚠️ What Needs Adjustment:**
- Too many false signals?
- Left-tail events (big losses)?
- Time-stops firing too early/late?
- Protections activating unexpectedly?

### Step 7: Phase 1 Completion Checklist

- [ ] Captured 10+ entry events
- [ ] Screenshots/charts for each event
- [ ] Event summary document created
- [ ] Trigger distribution analyzed
- [ ] Vol-sizing validation (check logs)
- [ ] Partial exit behavior documented
- [ ] Protection system tested (if any triggered)
- [ ] Key observations documented
- [ ] Identified 2-3 areas for Phase 2 tuning

Once complete, you're ready for Phase 2 optimization! 🎉

---

## ⚠️ Failure & Roll-back Plan

### Automatic Reversion Triggers

1. **Missing Enhancement Data**
   - Strategy auto-disables funding/ETF features
   - Falls back to pure built-in mode
   - Logs warning but continues trading

2. **Extreme Anomalies**
   - Exchange outage detected → force flat
   - Abnormal basis/spread → pause 1 hour
   - Resume after sanity checks pass

3. **Overfit Detection**
   - If small parameter change = large performance swing
   - Revert to conservative defaults
   - Extend observation period ≥4 weeks before re-tuning

---

## 🤝 Contributing

When modifying the strategy:

1. **Keep methodology first** - Don't optimize away the core logic
2. **Test across regimes** - Not just one backtest curve
3. **Document reasoning** - Why this change improves the playbook
4. **Event-study validation** - Does this improve individual event outcomes?

---

## 📚 References

### Foundation Strategies Used
- `VolatilitySystem.py` - Vol-Target sizing pattern
- `BigZ04_TSL3.py` - Multi-TF + ATR trailing stops
- `MiniLambo.py` - Protection configurations
- `keltnerchannel.py` - Keltner band calculations
- `CustomStoplossWithPSAR.py` - Dynamic stoploss template

### Key Concepts
- **Vol-Target Sizing**: Risk parity approach to position sizing
- **Sweep-and-Reclaim**: Liquidity sweep entry pattern
- **ATR-Based Stops**: Volatility-adjusted risk management
- **Circuit Breakers**: Freqtrade protection system

---

## 📞 Support

For questions or issues:
1. Check Freqtrade docs: https://www.freqtrade.io/
2. Review strategy comments and debug tags
3. Test in dry-run mode first
4. Analyze backtest trades JSON for insights

---

## ⚖️ Disclaimer

**This strategy is for educational purposes only.**

- Past performance does not guarantee future results
- Crypto trading involves substantial risk of loss
- Test thoroughly in dry-run mode before live trading
- Use appropriate position sizing and risk management
- No guarantee of profitability

**Trade at your own risk.**

---

## 📄 License

MIT License - See repository root for details

---

**Version**: 1.0.0 (Phase 1 - Pure Built-ins)  
**Last Updated**: 2025-10-22  
**Status**: Development / Testing
