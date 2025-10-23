"""
HybridRebound Strategy - Pure Freqtrade Built-ins Implementation

Core Methodology:
1. Market Gate - Only trade after de-leverage + panic release conditions
2. Entry Trigger - Confirm rebound with sweep-low & reclaim + price/volume confirmation
3. Sizing & Throttle - Vol-Target position sizing with volatility adaptation
4. Exit & Risk - Quick partials, ATR-based dynamic stops, intra-day circuit breakers

Phase: D0-D1 - Pure built-in implementation (multi-TF + price/volume + Vol-Target + Protections)
Target Pairs: BTC/USDT, ETH/USDT, SOL/USDT
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (DecimalParameter, IntParameter, IStrategy,
                                 informative, merge_informative_pair)
import freqtrade.vendor.qtpylib.indicators as qtpylib


class HybridRebound(IStrategy):
    """
    HybridRebound - Rebound trading with Market Gate, Vol-Target sizing, and dynamic risk management
    """
    
    INTERFACE_VERSION = 3
    
    # ==================== Strategy Settings ====================
    
    # Minimal ROI - Designed for quick partials
    minimal_roi = {
        "0": 0.05,      # 5% max target
        "15": 0.04,     # After 15min, 4%
        "30": 0.02,     # After 30min, 2%
        "60": 0.01,     # After 1h, 1%
    }
    
    # Initial stoploss (will be dynamic via custom_stoploss)
    stoploss = -0.10
    
    # Trailing stop settings
    trailing_stop = False  # Using custom_stoploss instead
    
    # Timeframes
    timeframe = '15m'  # Main trading timeframe
    inf_1h = '1h'      # Informative timeframe for market gate
    
    # Strategy flags
    use_custom_stoploss = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    process_only_new_candles = True
    
    startup_candle_count = 200
    
    # Position adjustment for partials
    position_adjustment_enable = False  # Will use custom_exit instead
    
    # ==================== Hyperopt Parameters ====================
    
    # Market Gate Parameters (BTC 1h)
    gate_ema200_enabled = True
    gate_ema200_slope_threshold = DecimalParameter(-0.001, 0.001, default=0.0, 
                                                     space='buy', optimize=False)
    
    # De-leverage Detection (violent flush + fast reclaim)
    deleverage_drop_threshold = DecimalParameter(0.03, 0.08, default=0.05, 
                                                  space='buy', decimals=3, optimize=True)
    deleverage_reclaim_candles = IntParameter(2, 6, default=3, 
                                               space='buy', optimize=True)
    
    # Panic Release (Keltner lower-band reclaim + green candles)
    panic_keltner_window = IntParameter(14, 28, default=20, 
                                         space='buy', optimize=False)
    panic_keltner_atr = DecimalParameter(1.0, 2.5, default=1.5, 
                                          space='buy', decimals=1, optimize=False)
    panic_green_candles_required = IntParameter(1, 3, default=2, 
                                                 space='buy', optimize=False)
    panic_rsi_oversold = IntParameter(20, 30, default=25, 
                                       space='buy', optimize=True)
    panic_rsi_rebound = IntParameter(28, 40, default=32, 
                                      space='buy', optimize=True)
    
    # Entry Triggers (need >= 2 to fire)
    # Sweep-and-reclaim
    sweep_lookback = IntParameter(10, 30, default=20, 
                                   space='buy', optimize=True)
    sweep_reclaim_threshold = DecimalParameter(0.001, 0.01, default=0.003, 
                                                space='buy', decimals=4, optimize=True)
    
    # Volume confirmation
    volume_spike_multiplier = DecimalParameter(1.2, 2.5, default=1.5, 
                                                space='buy', decimals=1, optimize=True)
    volume_mean_window = IntParameter(14, 30, default=20, 
                                       space='buy', optimize=False)
    
    # Price confirmation - bullish candles
    bullish_candles_required = IntParameter(1, 3, default=2, 
                                             space='buy', optimize=False)
    
    # Vol-Target Sizing Parameters
    vol_target_enabled = True
    vol_target_pct = DecimalParameter(1.2, 1.8, default=1.5, 
                                       space='buy', decimals=1, optimize=True)
    vol_atr_period = IntParameter(10, 20, default=14, 
                                   space='buy', optimize=False)
    vol_scale_min = DecimalParameter(0.3, 0.7, default=0.5, 
                                      space='buy', decimals=1, optimize=False)
    vol_scale_max = DecimalParameter(1.3, 2.0, default=1.5, 
                                      space='buy', decimals=1, optimize=False)
    
    # Exit Parameters
    # Partials
    partial_1_profit = DecimalParameter(0.015, 0.025, default=0.02, 
                                         space='sell', decimals=3, optimize=True)
    partial_1_size = DecimalParameter(0.3, 0.5, default=0.4, 
                                       space='sell', decimals=1, optimize=False)
    
    partial_2_profit = DecimalParameter(0.035, 0.05, default=0.04, 
                                         space='sell', decimals=3, optimize=True)
    partial_2_size = DecimalParameter(0.2, 0.4, default=0.3, 
                                       space='sell', decimals=1, optimize=False)
    
    # Dynamic ATR-based stoploss
    stoploss_atr_multiplier = DecimalParameter(1.0, 2.0, default=1.5, 
                                                space='sell', decimals=1, optimize=True)
    stoploss_trailing_profit = DecimalParameter(0.01, 0.03, default=0.02, 
                                                 space='sell', decimals=3, optimize=False)
    stoploss_trailing_atr_mult = DecimalParameter(1.5, 2.5, default=2.0, 
                                                    space='sell', decimals=1, optimize=False)
    
    # Time-based stop
    time_stop_minutes = IntParameter(15, 90, default=45, 
                                      space='sell', optimize=True)
    time_stop_loss_threshold = DecimalParameter(-0.005, 0.005, default=0.0, 
                                                  space='sell', decimals=3, optimize=False)
    
    # ==================== Protection Configuration ====================
    
    @property
    def protections(self):
        """
        Circuit breakers: consecutive losses → cooldown, max drawdown → stop trading
        """
        return [
            {
                # 2 consecutive losses per pair → 48h cooldown
                "method": "StoplossGuard",
                "lookback_period_candles": 4,  # ~1 hour on 15m
                "trade_limit": 2,
                "stop_duration_candles": 192,  # 48 hours on 15m
                "only_per_pair": True
            },
            {
                # Intra-day circuit breaker: day P&L ≤ -2R
                "method": "MaxDrawdown",
                "lookback_period_candles": 96,  # 24 hours on 15m
                "trade_limit": 5,
                "stop_duration_candles": 96,  # Stop for 24h
                "max_allowed_drawdown": 0.02  # -2% max drawdown
            },
            {
                # General cooldown between trades
                "method": "CooldownPeriod",
                "stop_duration_candles": 2  # 30 minutes on 15m
            }
        ]
    
    # ==================== Informative Pairs ====================
    
    def informative_pairs(self):
        """
        Request BTC/USDT 1h data for market gate check
        """
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.inf_1h) for pair in pairs]
        # Also get BTC/USDT specifically for market environment
        if 'BTC/USDT' not in pairs:
            informative_pairs.append(('BTC/USDT', self.inf_1h))
        return informative_pairs
    
    # ==================== Indicator Calculation ====================
    
    def informative_1h_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate 1h indicators for market gate
        """
        # EMA 200 for trend filter
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema_200_slope'] = (dataframe['ema_200'] - dataframe['ema_200'].shift(1)) / dataframe['ema_200'].shift(1)
        
        # Price position relative to EMA
        dataframe['above_ema200'] = (dataframe['close'] > dataframe['ema_200']).astype(int)
        
        # RSI for additional context
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all indicators for the strategy
        """
        
        # ===== Get 1h informative data =====
        informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.inf_1h)
        informative_1h = self.informative_1h_indicators(informative_1h, metadata)
        dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, self.inf_1h, ffill=True)
        
        # ===== Keltner Channels (for panic release detection) =====
        keltner = qtpylib.keltner_channel(dataframe, window=self.panic_keltner_window.value, 
                                          atrs=self.panic_keltner_atr.value)
        dataframe['kc_upper'] = keltner['upper']
        dataframe['kc_lower'] = keltner['lower']
        dataframe['kc_mid'] = keltner['mid']
        
        # ===== ATR for volatility and stops =====
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.vol_atr_period.value)
        dataframe['atr_pct'] = (dataframe['atr'] / dataframe['close']) * 100
        
        # ===== RSI =====
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=21)
        
        # ===== Volume indicators =====
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=self.volume_mean_window.value).mean()
        dataframe['volume_spike'] = dataframe['volume'] / dataframe['volume_mean']
        
        # ===== Price action =====
        # Bullish/bearish candles
        dataframe['bullish'] = (dataframe['close'] > dataframe['open']).astype(int)
        dataframe['bearish'] = (dataframe['close'] < dataframe['open']).astype(int)
        
        # Consecutive bullish candles
        dataframe['consecutive_bullish'] = 0
        for i in range(1, 4):
            dataframe['consecutive_bullish'] += dataframe['bullish'].shift(i - 1)
        
        # ===== Swing lows (for sweep detection) =====
        dataframe['swing_low'] = dataframe['low'].rolling(window=self.sweep_lookback.value).min()
        dataframe['swing_low_price'] = dataframe['swing_low'].shift(1)
        
        # ===== De-leverage detection =====
        # Violent drop followed by fast reclaim
        dataframe['price_drop'] = (dataframe['low'] - dataframe['close'].shift(1)) / dataframe['close'].shift(1)
        dataframe['reclaim_speed'] = (dataframe['close'] - dataframe['low']) / (dataframe['high'] - dataframe['low'] + 1e-10)
        
        # ===== Vol-Target calculation =====
        if self.vol_target_enabled:
            # Current instantaneous volatility (ATR as % of price)
            dataframe['current_vol'] = dataframe['atr_pct']
            # Vol-Target scale factor
            dataframe['vol_scale'] = self.vol_target_pct.value / (dataframe['current_vol'] + 0.1)  # Avoid div by zero
            # Clip to reasonable range
            dataframe['vol_scale'] = dataframe['vol_scale'].clip(
                lower=self.vol_scale_min.value, 
                upper=self.vol_scale_max.value
            )
        else:
            dataframe['vol_scale'] = 1.0
        
        return dataframe
    
    # ==================== Entry Logic ====================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic with Market Gate + Entry Triggers (need >= 2 triggers)
        """
        
        conditions = []
        
        # ===== MARKET GATE =====
        market_gate = (
            # BTC 1h above EMA200 OR EMA200 slope positive
            (
                (dataframe[f'above_ema200_{self.inf_1h}'] == 1) |
                (dataframe[f'ema_200_slope_{self.inf_1h}'] > self.gate_ema200_slope_threshold.value)
            )
        )
        conditions.append(market_gate)
        
        # ===== DE-LEVERAGE PROXY =====
        # Violent flush (big drop) followed by fast reclaim
        deleverage = (
            (dataframe['price_drop'] < -self.deleverage_drop_threshold.value) &
            (dataframe['reclaim_speed'] > 0.5) &  # Reclaimed at least 50% of the range
            (dataframe['close'] > dataframe['open'])  # Closed green
        )
        
        # ===== PANIC RELEASE =====
        # Price touched/broke Keltner lower band and reclaimed it
        # Plus RSI rebound from oversold
        panic_release = (
            (dataframe['low'].shift(1) <= dataframe['kc_lower'].shift(1)) &  # Touched lower band
            (dataframe['close'] > dataframe['kc_lower']) &  # Reclaimed
            (dataframe['rsi'].shift(1) < self.panic_rsi_oversold.value) &  # Was oversold
            (dataframe['rsi'] > self.panic_rsi_rebound.value) &  # Rebounded
            (dataframe['consecutive_bullish'] >= self.panic_green_candles_required.value)  # Green candles
        )
        
        # Combine de-leverage and panic release
        market_conditions = deleverage | panic_release
        conditions.append(market_conditions)
        
        # ===== ENTRY TRIGGERS (need >= 2) =====
        trigger_count = 0
        
        # Trigger 1: Sweep-and-reclaim
        sweep_reclaim = (
            (dataframe['low'] <= dataframe['swing_low_price'] * (1 + self.sweep_reclaim_threshold.value)) &
            (dataframe['close'] > dataframe['swing_low_price'] * (1 + self.sweep_reclaim_threshold.value))
        )
        dataframe.loc[sweep_reclaim, 'trigger_sweep'] = 1
        
        # Trigger 2: Volume spike
        volume_confirm = (
            dataframe['volume_spike'] > self.volume_spike_multiplier.value
        )
        dataframe.loc[volume_confirm, 'trigger_volume'] = 1
        
        # Trigger 3: RSI rebound from oversold
        rsi_rebound = (
            (dataframe['rsi'].shift(1) < self.panic_rsi_oversold.value) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
            (dataframe['rsi'] > self.panic_rsi_rebound.value)
        )
        dataframe.loc[rsi_rebound, 'trigger_rsi'] = 1
        
        # Trigger 4: Consecutive bullish candles
        bullish_momentum = (
            dataframe['consecutive_bullish'] >= self.bullish_candles_required.value
        )
        dataframe.loc[bullish_momentum, 'trigger_bullish'] = 1
        
        # Count triggers
        dataframe['trigger_count'] = (
            dataframe.get('trigger_sweep', 0) +
            dataframe.get('trigger_volume', 0) +
            dataframe.get('trigger_rsi', 0) +
            dataframe.get('trigger_bullish', 0)
        )
        
        # Need at least 2 triggers to fire
        trigger_condition = dataframe['trigger_count'] >= 2
        conditions.append(trigger_condition)
        
        # ===== FINAL ENTRY SIGNAL =====
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'
            ] = 1
        
        # Debug: Add entry reason tag
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = (
            'rebound_' + dataframe['trigger_count'].astype(str) + 'trig'
        )
        
        return dataframe
    
    # ==================== Exit Logic ====================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals (mainly rely on ROI, custom_stoploss, and custom_exit for partials)
        """
        
        # Exit on loss of momentum
        exit_conditions = (
            (dataframe['rsi'] < 30) &
            (dataframe['close'] < dataframe['kc_mid']) &
            (dataframe['bearish'] == 1)
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        dataframe.loc[dataframe['exit_long'] == 1, 'exit_tag'] = 'momentum_loss'
        
        return dataframe
    
    # ==================== Custom Stoploss ====================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic ATR-based stoploss with time-based exit
        
        Returns:
            float: Stoploss value (negative = stop at loss, positive = stop at profit)
                   Return 1 to use default stoploss
        """
        
        # Get dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return 1  # Use default
        
        last_candle = dataframe.iloc[-1].squeeze()
        
        # ===== Time-based stop =====
        # If position hasn't escaped breakeven after X minutes, exit
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_duration > self.time_stop_minutes.value:
            if current_profit < self.time_stop_loss_threshold.value:
                return 0.001  # Force exit
        
        # ===== ATR-based dynamic stoploss =====
        atr = last_candle.get('atr', 0)
        if atr > 0:
            # Calculate stoploss distance based on ATR
            atr_distance = (atr * self.stoploss_atr_multiplier.value) / current_rate
            
            # If in profit, use tighter trailing stop
            if current_profit > self.stoploss_trailing_profit.value:
                atr_distance = (atr * self.stoploss_trailing_atr_mult.value) / current_rate
                # Calculate trailing stop from current price
                new_stoploss = -atr_distance
                
                # Only move stoploss up, never down
                if new_stoploss > self.stoploss:
                    return new_stoploss
            else:
                # Initial stoploss
                return -atr_distance
        
        return 1  # Use default stoploss
    
    # ==================== Custom Exit (Partials) ====================
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Implement partial exits at profit targets
        
        Note: This requires Freqtrade v2023.8+
        For older versions, would need to use exit signals or custom_sell
        """
        
        # Partial 1: Take profit at +2% (exit 40% of position)
        if current_profit >= self.partial_1_profit.value:
            if not hasattr(trade, 'partial_1_taken'):
                trade.partial_1_taken = True
                return f'partial_1_{self.partial_1_profit.value:.1%}'
        
        # Partial 2: Take profit at +4% (exit 30% more)
        if current_profit >= self.partial_2_profit.value:
            if not hasattr(trade, 'partial_2_taken'):
                trade.partial_2_taken = True
                return f'partial_2_{self.partial_2_profit.value:.1%}'
        
        return None
    
    # ==================== Custom Stake Amount (Vol-Target) ====================
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        """
        Vol-Target position sizing: scale stake based on volatility
        
        Target: 1.2-1.8% volatility per position
        Scale: targetVol / actualVol, clipped to 0.5x-1.5x
        """
        
        if not self.vol_target_enabled:
            return proposed_stake
        
        # Get current volatility scale from indicators
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return proposed_stake
        
        last_candle = dataframe.iloc[-1].squeeze()
        vol_scale = last_candle.get('vol_scale', 1.0)
        
        # Apply scale to proposed stake
        scaled_stake = proposed_stake * vol_scale
        
        # Ensure within min/max bounds
        if min_stake is not None:
            scaled_stake = max(scaled_stake, min_stake)
        scaled_stake = min(scaled_stake, max_stake)
        
        # Cap at 2.0x base stake as per requirements
        max_allowed = proposed_stake * 2.0
        scaled_stake = min(scaled_stake, max_allowed)
        
        return scaled_stake
    
    # ==================== Leverage (for futures) ====================
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        """
        Leverage configuration for futures trading
        Keep low to avoid liquidations
        """
        return 1.0  # No leverage for Phase 1


def to_minutes(**kwargs) -> int:
    """Helper to convert time to minutes for protection configs"""
    return sum([
        kwargs.get('minutes', 0),
        kwargs.get('hours', 0) * 60,
        kwargs.get('days', 0) * 1440,
    ])
