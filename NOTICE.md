# Third-party notices

The Yahoo adapter uses the Python [yfinance package](https://github.com/ranaroussi/yfinance) and its `PricingData` protobuf definition to decode Yahoo's public pricing protocol. yfinance is independent of Yahoo and distributed under Apache License 2.0; a copy is retained in [server/YFINANCE-LICENSE.txt](server/YFINANCE-LICENSE.txt). The application directly manages the socket lifecycle using Python websockets so failures, retry state, and deliberate outages remain observable. yfinance does not supply an official Yahoo availability guarantee.

TradingView Lightweight Charts™ is used under Apache License 2.0. Copyright © 2026 TradingView, Inc. The [license](licenses/LIGHTWEIGHT-CHARTS-LICENSE.txt) and unmodified upstream [NOTICE](licenses/LIGHTWEIGHT-CHARTS-NOTICE.txt) are preserved. Attribution and a [TradingView](https://www.tradingview.com/) link are present in the chart, footer, and about panel.

Other Python/npm dependencies retain their respective distribution licenses. Yahoo Finance and asset names belong to their owners; this educational project is not affiliated with or endorsed by them.
