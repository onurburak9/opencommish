# Projected Stats Validation

This directory contains scripts for fetching and validating projected fantasy basketball stats.

## Scripts

### fetch_projected_stats.py (Web Scraping)
Fetches projected stats by scraping the Yahoo Fantasy UI HTML.

```bash
python cron/fetch_projected_stats.py [YYYY-MM-DD]
```

### fetch_projected_stats_api.py (API-Based)
Fetches projected stats using the official Yahoo Fantasy API via yfpy.
This is used for validating the scraping approach.

```bash
python cron/fetch_projected_stats_api.py [YYYY-MM-DD]
```

### validate_projected_stats.py (Comparison Tool)
Compares scraped data vs API data and generates a validation report.

```bash
python cron/validate_projected_stats.py [YYYY-MM-DD]
```

## Why Two Data Sources?

The scraping approach (fetch_projected_stats.py) was created because:
1. Yahoo's API doesn't have a direct "projected stats" endpoint
2. The API's future date queries don't always return projections
3. Scraping the UI gives us the exact projections shown to users

The API-based fetcher (fetch_projected_stats_api.py) exists for validation:
1. Verify scraping accuracy
2. Detect when Yahoo changes their HTML structure
3. Provide a fallback data source

## Data Flow

```
┌─────────────────────┐     ┌──────────────────────┐
│  Yahoo Fantasy UI   │────▶│ fetch_projected_     │
│  (HTML scraping)    │     │ stats.py             │
└─────────────────────┘     └──────────┬───────────┘
                                       │
                                       ▼
┌─────────────────────┐     ┌──────────────────────┐
│  Yahoo Fantasy API  │────▶│ fetch_projected_     │
│  (yfpy library)     │     │ stats_api.py         │
└─────────────────────┘     └──────────┬───────────┘
                                       │
                                       ▼
                          ┌──────────────────────┐
                          │ validate_projected_  │
                          │ stats.py             │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ Validation Report    │
                          └──────────────────────┘
```

## Running Validation

To validate today's projections:

```bash
# 1. Fetch via scraping
python cron/fetch_projected_stats.py

# 2. Fetch via API
python cron/fetch_projected_stats_api.py

# 3. Compare and validate
python cron/validate_projected_stats.py
```

## Expected Differences

Some differences between scraped and API data are expected:

1. **Opponent field**: May differ if the API doesn't provide this info
2. **Games Played**: API may return 1 by default while scraping shows actual scheduled games
3. **Player availability**: Injured players may be handled differently

## Automating Validation

Add to your CI/CD pipeline:

```yaml
- name: Validate Projected Stats
  run: |
    python cron/fetch_projected_stats_api.py
    python cron/validate_projected_stats.py
```
