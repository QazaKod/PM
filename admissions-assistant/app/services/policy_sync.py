"""Refresh structured official admissions tables while retaining the last valid snapshot."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import tempfile

from bs4 import BeautifulSoup
import httpx

URL = "https://sdu.edu.kz/en/admission-3-2/"
SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "official_admissions.json"


def read_policy():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def extract(html):
    documents, grant_codes, stages = [], set(), []
    for table in BeautifulSoup(html, "html.parser").find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in row.find_all(["th", "td"], recursive=False)]
                for row in table.find_all("tr")]
        if not rows or not rows[0]:
            continue
        if rows[0][0] == "Document" and len(rows[0]) == 4:
            stages = rows[0][1:]
            for row in rows[1:]:
                if len(row) == 4 and all(mark in {"✓", "✔", "–", "-", "—"} for mark in row[1:]):
                    documents.append({"name": row[0], "required": [mark in {"✓", "✔"} for mark in row[1:]]})
        if "Number of state grants" in rows[0]:
            for row in rows[1:]:
                if row:
                    grant_codes.update(re.findall(r"6B\d{5}", row[-1].upper().replace("В", "B")))
    if len(documents) < 8 or len(grant_codes) < 5:
        raise ValueError("Official tables could not be validated")
    return {"source": URL, "checked": datetime.now(timezone.utc).date().isoformat(), "stages": stages,
            "documents": documents, "grant_codes": sorted(grant_codes)}


def refresh():
    response = httpx.get(URL, timeout=15, follow_redirects=True)
    response.raise_for_status()
    data = extract(response.text)
    if SNAPSHOT.exists() and data == read_policy():
        return
    with tempfile.NamedTemporaryFile(dir=SNAPSHOT.parent, delete=False, mode="w", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")
    os.replace(output.name, SNAPSHOT)


async def refresh_daily():
    while True:
        try:
            await asyncio.to_thread(refresh)
        except (ValueError, OSError, httpx.HTTPError) as exc:
            logging.getLogger(__name__).warning("Official admissions refresh failed: %s", exc)
        await asyncio.sleep(86400)


if __name__ == "__main__":
    refresh()
