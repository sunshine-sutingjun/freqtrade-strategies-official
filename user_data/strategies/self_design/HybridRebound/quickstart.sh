#!/bin/bash
# HybridRebound Strategy - Quick Start Script

echo "🚀 HybridRebound Strategy Verification"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Download data
echo -e "${YELLOW}Step 1: Downloading market data...${NC}"
freqtrade download-data \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --timerange 20240701-20241022 \
    --timeframes 15m 1h \
    --pairs BTC/USDT ETH/USDT SOL/USDT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data download completed${NC}"
else
    echo -e "${RED}✗ Data download failed${NC}"
    exit 1
fi

echo ""
echo "======================================"

# Step 2: Test strategy syntax
echo -e "${YELLOW}Step 2: Testing strategy syntax...${NC}"
freqtrade test-pairlist \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --quote USDT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Strategy syntax is valid${NC}"
else
    echo -e "${RED}✗ Strategy has syntax errors${NC}"
    exit 1
fi

echo ""
echo "======================================"

# Step 3: Quick backtest (30 days)
echo -e "${YELLOW}Step 3: Running quick backtest (30 days)...${NC}"
freqtrade backtesting \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --strategy HybridRebound \
    --timerange 20240922-20241022 \
    --breakdown day week

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Quick backtest completed${NC}"
else
    echo -e "${RED}✗ Backtest failed${NC}"
    exit 1
fi

echo ""
echo "======================================"

# Step 4: Extended backtest (3 months)
echo -e "${YELLOW}Step 4: Running extended backtest (3 months)...${NC}"
freqtrade backtesting \
    --config user_data/strategies/self_design/HybridRebound/config_hybridrebound_backtest.json \
    --strategy HybridRebound \
    --timerange 20240722-20241022 \
    --export trades \
    --export-filename user_data/backtest_results/hybridrebound_3m.json \
    --breakdown day week month

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Extended backtest completed${NC}"
else
    echo -e "${RED}✗ Extended backtest failed${NC}"
    exit 1
fi

echo ""
echo "======================================"

# Step 5: Show summary
echo -e "${GREEN}🎉 Verification Complete!${NC}"
echo ""
echo "Results saved to: user_data/backtest_results/hybridrebound_3m.json"
echo ""
echo "Next steps:"
echo "1. Review the backtest results above"
echo "2. Check enter_tag distribution (how many triggers fired)"
echo "3. Analyze trade duration and profit distribution"
echo "4. If results look good, run: ./analyze_events.sh"
echo ""
echo "To start dry-run trading:"
echo "  freqtrade trade --config user_data/strategies/self_design/HybridRebound/config_hybridrebound.json --strategy HybridRebound"
echo ""
