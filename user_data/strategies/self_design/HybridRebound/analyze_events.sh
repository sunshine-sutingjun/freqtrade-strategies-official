#!/bin/bash
# HybridRebound - Event Study Analysis

echo "📊 HybridRebound Event Study Analysis"
echo "======================================"
echo ""

# Run backtesting analysis
echo "Analyzing trade performance by entry reason..."
echo ""

freqtrade backtesting-analysis \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --analysis-groups 0 1 2 3 4 \
    --enter-reason-list rebound_2trig rebound_3trig rebound_4trig \
    --exit-reason-list roi stop_loss trailing_stop_loss exit_signal partial_1 partial_2

echo ""
echo "======================================"
echo ""
echo "Trade distribution by trigger count:"
echo ""

# Show detailed analysis
freqtrade backtesting-analysis \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --analysis-groups 0 1 2 \
    --enter-reason-list rebound_2trig rebound_3trig rebound_4trig

echo ""
echo "======================================"
echo ""
echo "Key Questions to Answer:"
echo "1. Are 4-trigger entries more profitable than 2-trigger?"
echo "2. What's the median/mean profit per entry type?"
echo "3. What's the 5th percentile return (left-tail)?"
echo "4. How often do partials get hit vs full exits?"
echo ""
echo "For detailed event-by-event analysis, check:"
echo "  user_data/backtest_results/hybridrebound_3m.json"
echo ""
