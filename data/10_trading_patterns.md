# Core Trading Patterns Matrix

## 1. Inverse Head & Shoulders (Reversal / Bullish)

Success_Rate: 083.4
Trigger: price > neckline_resistance AND volume > 2_day_ma
Target: entry + (head_depth)

## 2. Head & Shoulders (Reversal / Bearish)

Success_Rate: 083.0
Trigger: price < neckline_support AND volume > 2_day_ma
Target: entry - (head_depth)

## 3. Double Bottom (Reversal / Bullish)

Success_Rate: 078.5
Trigger: price > peak_resistance AND volume > 1.5_day_ma
Target: entry + (bottom_depth)

## 4. Triple Bottom (Reversal / Bullish)

Success_Rate: 077.6
Trigger: price > resistance_ceiling AND volume > 2_day_ma
Target: entry + (bottom_depth)

## 5. Double Top (Reversal / Bearish)

Success_Rate: 075.0
Trigger: price < valley_support AND volume > 1.5_day_ma
Target: entry - (top_depth)

## 6. Triple Top (Reversal / Bearish)

Success_Rate: 074.5
Trigger: price < support_floor AND volume > 2_day_ma
Target: entry - (top_depth)

## 7. Rectangle Bottom (Continuation / Bullish)

Success_Rate: 074.2
Trigger: price > consolidation_ceiling AND volume > 2_day_ma
Target: entry + (channel_height)

## 8. Rectangle Top (Continuation / Bearish)

Success_Rate: 072.3
Trigger: price < consolidation_floor AND volume > 2_day_ma
Target: entry - (channel_height)

## 9. Ascending Triangle (Continuation / Bullish)

Success_Rate: 070.9
Trigger: price > flat_resistance AND volume > 2_day_ma
Target: entry + (triangle_base_height)

## 10. Descending Triangle (Continuation / Bearish)

Success_Rate: 069.6
Trigger: price < flat_support AND volume > 2_day_ma
Target: entry - (triangle_base_height)

## Execution Core Overrides

Volume_Filter: volume >= 2.0 \* avg_20_day_volume
Time_Gate: current_time_est >= 09:30 AND current_time_est <= 17:30
