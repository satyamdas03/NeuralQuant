FROM python:3.11-slim

RUN pip install --no-cache-dir openbb-platform-api

# Core equity providers (yfinance is free, no API key)
RUN pip install --no-cache-dir \
    openbb-equity-price-historical \
    openbb-equity-fundamental \
    openbb-equity-profile \
    openbb-equity-ownership \
    openbb-equity-discovery \
    openbb-equity-price-quote \
    openbb-equity-price-performance

# Derivatives (options chains, IV)
RUN pip install --no-cache-dir \
    openbb-derivatives-options

# Macro / Fixed Income (yield curve, treasury rates)
RUN pip install --no-cache-dir \
    openbb-economy-fred \
    openbb-fixedincome-federal-reserve

EXPOSE 6900

CMD ["openbb-api", "--host", "0.0.0.0", "--port", "6900"]