#!/usr/bin/env python3
"""Generate a monochrome-compatible Premier League dashboard BMP."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont


WIDTH = 528
HEIGHT = 792
PACIFIC = ZoneInfo("America/Los_Angeles")
API_ROOT = "https://footballapi.pulselive.com/football"
API_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.premierleague.com",
    "User-Agent": "x3-premier-league/1.0 (+GitHub Actions)",
}


def api_get(path: str, **params: Any) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"{API_ROOT}/{path}"
    if query:
        url += f"?{query}"
    request = urllib.request.Request(url, headers=API_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not fetch Premier League data from {url}: {exc}") from exc


def fetch_dashboard_data(now: datetime) -> dict[str, Any]:
    seasons = api_get("competitions/1/compseasons", page=0, pageSize=10)
    season_items = seasons.get("content", [])
    if not season_items:
        raise RuntimeError("The Premier League data source returned no seasons")

    season = season_items[0]
    season_id = int(season["id"])
    gameweeks_payload = api_get(f"compseasons/{season_id}/gameweeks", page=0, pageSize=100)
    gameweeks = gameweeks_payload.get("gameweeks", [])
    if not gameweeks:
        raise RuntimeError("The Premier League data source returned no gameweeks")

    active = [gw for gw in gameweeks if gw.get("status") == "I"]
    upcoming = [gw for gw in gameweeks if gw.get("status") == "U"]
    completed = [gw for gw in gameweeks if gw.get("status") == "C"]
    if active:
        gameweek = active[0]
    elif upcoming:
        gameweek = min(upcoming, key=lambda gw: gw["gameweek"])
    else:
        gameweek = max(completed or gameweeks, key=lambda gw: gw["gameweek"])

    fixtures_payload = api_get(
        "fixtures",
        comp=1,
        compSeasons=season_id,
        page=0,
        pageSize=500,
        sort="asc",
    )
    gameweek_number = int(gameweek["gameweek"])
    fixtures = [
        fixture
        for fixture in fixtures_payload.get("content", [])
        if int(fixture.get("gameweek", {}).get("gameweek", -1)) == gameweek_number
    ]
    fixtures.sort(key=lambda fixture: float(fixture["kickoff"]["millis"]))
    if not fixtures:
        raise RuntimeError(f"No fixtures found for gameweek {gameweek_number}")

    matches = [parse_fixture(fixture) for fixture in fixtures]
    season_text = normalize_season_label(season.get("label", str(now.year)))
    return {
        "season": season_text,
        "gameweek": gameweek_number,
        "matches": matches,
        "updated": now.astimezone(PACIFIC),
    }


def normalize_season_label(label: str) -> str:
    # API labels are either "2025/26" or "English Premier League Season 2026/2027".
    years = [part for part in label.replace("/", " ").split() if part.isdigit()]
    if len(years) >= 2 and len(years[-1]) == 4:
        return f"{years[-2]}/{years[-1][-2:]}"
    if "/" in label:
        return label.rsplit(" ", 1)[-1]
    return label


def parse_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    teams = fixture.get("teams", [])
    if len(teams) != 2:
        raise RuntimeError(f"Fixture {fixture.get('id')} did not contain exactly two teams")

    def team_info(entry: dict[str, Any]) -> dict[str, str]:
        team = entry["team"]
        club = team.get("club", {})
        return {
            "name": team.get("name") or club.get("name") or "Unknown",
            "short": team.get("shortName") or club.get("shortName") or club.get("abbr") or "UNK",
            "abbr": club.get("abbr") or team.get("shortName") or "UNK",
        }

    kickoff = datetime.fromtimestamp(float(fixture["kickoff"]["millis"]) / 1000, timezone.utc)
    status = fixture.get("status", "U")
    return {
        "id": int(fixture["id"]),
        "kickoff": kickoff.astimezone(PACIFIC),
        "status": status,
        "home": team_info(teams[0]),
        "away": team_info(teams[1]),
        "home_score": int(teams[0]["score"]) if teams[0].get("score") is not None else None,
        "away_score": int(teams[1]["score"]) if teams[1].get("score") is not None else None,
    }


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        [
            "DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        if bold
        else [
            "DejaVuSansCondensed.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor="mm")


def fitting_team_name(
    draw: ImageDraw.ImageDraw,
    team: dict[str, str],
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    for candidate in (team["name"], team["short"], team["abbr"]):
        if text_width(draw, candidate.upper(), font) <= max_width:
            return candidate.upper()
    return team["abbr"].upper()


def render_dashboard(data: dict[str, Any], output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    title_font = find_font(37, bold=True)
    subtitle_font = find_font(17, bold=True)
    stat_font = find_font(19, bold=True)
    section_font = find_font(17, bold=True)
    team_font = find_font(18, bold=True)
    score_font = find_font(18, bold=True)
    meta_font = find_font(12, bold=False)
    footer_font = find_font(12, bold=True)

    draw.rectangle((6, 6, WIDTH - 7, HEIGHT - 7), outline="black", width=3)
    draw.rectangle((17, 17, WIDTH - 18, 94), fill="black")
    center_text(draw, (WIDTH // 2, 48), "PREMIER LEAGUE", title_font, "white")
    center_text(
        draw,
        (WIDTH // 2, 78),
        f"{data['season']}  •  PACIFIC TIME",
        subtitle_font,
        "white",
    )

    matches = data["matches"]
    completed = [match for match in matches if match["status"] == "C"]
    live = [match for match in matches if match["status"] not in {"C", "U"}]
    upcoming = [match for match in matches if match["status"] == "U"]
    draw.line((17, 105, WIDTH - 18, 105), fill="black", width=2)
    center_text(draw, (WIDTH // 4, 127), f"GAMEWEEK {data['gameweek']}", stat_font, "black")
    center_text(
        draw,
        (WIDTH * 3 // 4, 127),
        f"{len(completed)} OF {len(matches)} FINAL",
        stat_font,
        "black",
    )
    draw.line((17, 149, WIDTH - 18, 149), fill="black", width=2)

    groups = [("COMPLETED", completed), ("IN PLAY", live), ("UPCOMING", upcoming)]
    groups = [(label, items) for label, items in groups if items]
    top = 158
    footer_top = 744
    header_height = 27
    available_rows = footer_top - top - header_height * len(groups)
    row_height = max(42, min(54, available_rows // len(matches)))

    y = top
    for label, group_matches in groups:
        draw.rectangle((17, y, WIDTH - 18, y + header_height - 1), fill="black")
        draw.text((25, y + header_height // 2), label, font=section_font, fill="white", anchor="lm")
        draw.text(
            (WIDTH - 25, y + header_height // 2),
            str(len(group_matches)),
            font=section_font,
            fill="white",
            anchor="rm",
        )
        y += header_height
        for match in group_matches:
            draw_match_row(draw, match, y, row_height, team_font, score_font, meta_font)
            y += row_height

    updated = data["updated"].strftime("%a %b %-d  •  %-I:%M %p PT").upper()
    draw.line((17, footer_top, WIDTH - 18, footer_top), fill="black", width=2)
    center_text(draw, (WIDTH // 2, 760), f"UPDATED {updated}", footer_font, "black")
    center_text(draw, (WIDTH // 2, 777), "DATA: PREMIERLEAGUE.COM", meta_font, "black")

    # TrueType rendering is antialiased. Threshold once at the end so every pixel is pure B/W.
    image = image.convert("L").point(lambda pixel: 255 if pixel >= 128 else 0, mode="1").convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="BMP", compression="raw")


def draw_match_row(
    draw: ImageDraw.ImageDraw,
    match: dict[str, Any],
    y: int,
    height: int,
    team_font: ImageFont.ImageFont,
    score_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
) -> None:
    kickoff = match["kickoff"]
    meta = kickoff.strftime("%a %b %-d  •  %-I:%M %p PT").upper()
    center_text(draw, (WIDTH // 2, y + 11), meta, meta_font, "black")

    team_y = y + 31
    max_team_width = 181
    home = fitting_team_name(draw, match["home"], team_font, max_team_width)
    away = fitting_team_name(draw, match["away"], team_font, max_team_width)
    draw.text((216, team_y), home, font=team_font, fill="black", anchor="rm")
    draw.text((312, team_y), away, font=team_font, fill="black", anchor="lm")

    if match["status"] == "U":
        center = "v"
    else:
        status = "FT" if match["status"] == "C" else "LIVE"
        center = f"{match['home_score']}–{match['away_score']} {status}"
    center_text(draw, (WIDTH // 2, team_y), center, score_font, "black")
    draw.line((22, y + height - 1, WIDTH - 23, y + height - 1), fill="black", width=1)


def validate_bmp(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing output file: {path}")
    with path.open("rb") as bmp:
        header = bmp.read(54)
    if header[:2] != b"BM":
        raise RuntimeError("Output is not a BMP file")
    bits_per_pixel = struct.unpack_from("<H", header, 28)[0]
    compression = struct.unpack_from("<I", header, 30)[0]
    if bits_per_pixel != 24:
        raise RuntimeError(f"Expected 24-bit BMP, found {bits_per_pixel}-bit")
    if compression != 0:
        raise RuntimeError(f"Expected uncompressed BMP, compression={compression}")

    with Image.open(path) as image:
        image.load()
        if image.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Expected {WIDTH}x{HEIGHT}, found {image.size}")
        if image.mode != "RGB":
            raise RuntimeError(f"Expected RGB image, found mode {image.mode}")
        colors = set(image.getdata())
    allowed = {(0, 0, 0), (255, 255, 255)}
    if not colors or not colors.issubset(allowed):
        raise RuntimeError(f"Image contains non-black/white pixels: {colors - allowed}")
    print(
        f"Validated {path}: {WIDTH}x{HEIGHT}, RGB, 24-bit uncompressed BMP, "
        f"{len(colors)} pure B/W colors"
    )


def print_source_summary(data: dict[str, Any]) -> None:
    print(f"Season {data['season']} — Gameweek {data['gameweek']}")
    for match in data["matches"]:
        when = match["kickoff"].strftime("%Y-%m-%d %H:%M %Z")
        if match["status"] == "C":
            detail = f"{match['home_score']}-{match['away_score']} FT"
        elif match["status"] == "U":
            detail = "upcoming"
        else:
            detail = f"{match['home_score']}-{match['away_score']} LIVE"
        print(f"  {when} | {match['home']['name']} {detail} {match['away']['name']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("PremierLeague.bmp"))
    parser.add_argument("--validate", action="store_true", help="validate the BMP after generation")
    parser.add_argument("--validate-only", action="store_true", help="validate an existing BMP")
    args = parser.parse_args()

    if args.validate_only:
        validate_bmp(args.output)
        return 0

    now = datetime.now(timezone.utc)
    data = fetch_dashboard_data(now)
    print_source_summary(data)
    render_dashboard(data, args.output)
    print(f"Wrote {args.output}")
    if args.validate:
        validate_bmp(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
