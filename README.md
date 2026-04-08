# Binance EMA Scanner

自动扫描币安USDT永续合约中EMA多头排列的币种，适合日内交易。

## 功能

- 扫描1H/4H时间框架
- EMA多头排列检测（EMA5>EMA20>EMA30>EMA99）
- 过滤24h成交额小于3000万USDT的币种
- 智能评分系统
- 识别刚突破震荡的币种
- 每天北京时间8点自动运行

## 使用方法

1. Fork 本仓库
2. 在仓库 Settings > Secrets 中添加：
   - BINANCE_API_KEY: 你的币安API Key
   - BINANCE_API_SECRET: 你的币安API Secret
3. 每天8点自动运行，或手动触发 workflow

## 结果

扫描结果保存在 \esults.json\ 中。