# X3 Premier League Dashboard

An automatically updated, newspaper-style Premier League scoreboard for the
528 × 792 pixel XTEINK X3 e-reader and CrossPoint Reader.

[Download the latest PremierLeague.bmp](https://raw.githubusercontent.com/abasily1-byte/x3-premier-league/main/PremierLeague.bmp)

## What it shows

- Current Premier League season and gameweek
- Completed-match count
- Final scores with `FT` status
- Live matches when present
- Upcoming fixtures
- Kickoff and update times in `America/Los_Angeles` (Pacific Time)

The generated file is an uncompressed 24-bit RGB BMP containing only pure black
and pure white pixels. No grayscale or color pixels are used.

## Data source

Version 1 uses the no-key JSON data endpoint served by
[PremierLeague.com](https://www.premierleague.com/). It supplies season,
gameweek, fixture, score, status, kickoff, and team data. No API key or GitHub
secret is required.

## Automation

The [GitHub Actions workflow](.github/workflows/update.yml):

- runs automatically at minute 17 of every hour (UTC);
- can also be run manually with **Run workflow**;
- prevents concurrent runs on the same branch;
- validates the output before committing it; and
- commits `PremierLeague.bmp` only when the generated file changed.

GitHub Actions schedules can be delayed during periods of high service load.

## Run locally

```bash
python -m pip install -r requirements.txt
python generate_pl_bmp.py --validate
```

To validate an existing output without fetching data:

```bash
python generate_pl_bmp.py --validate-only
```

The generator prints every displayed fixture and result so its output can be
compared directly with the source response in CI logs.
