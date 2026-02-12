#!/usr/bin/env python3
"""
Extract referrals from your LinkedIn Connections CSV export and save matches by company to JSON.

Usage:
- Export your Connections CSV from LinkedIn (Settings → Data privacy → Get a copy of your data → Connections).
- Place the CSV on your machine and run:
    python extractReferals.py
- The script will prompt for the CSV path and the target company, then output JSON.

This version does not call the LinkedIn API and only relies on the user-provided CSV export.
"""

import os
import json
import csv
from typing import List, Dict


def parse_linkedin_csv(csv_path: str) -> List[Dict]:
    """Parse LinkedIn's exported Connections CSV and normalize rows.

    Expected exported CSV columns (may vary by LinkedIn version):
    - First Name, Last Name, Email Address, Company, Position, Profile Url
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            name = "".join(filter(None, [r.get("First Name", ""), " ", r.get("Last Name", "")])).strip()
            profile = (
                r.get("Profile Url") or r.get("Profile URL") or r.get("Profile") or
                r.get("Profile Urls") or r.get("LinkedIn Profile") or r.get("Profile Link") or ""
            )
            company = r.get("Company") or r.get("Organization") or r.get("Current Company") or ""
            position = r.get("Position") or r.get("Title") or ""
            rows.append({
                "name": name,
                "profile_url": profile,
                "company": company,
                "position": position,
                "raw": r,
            })
    return rows


def filter_by_company(connections: List[Dict], company_name: str) -> List[Dict]:
    company_lower = company_name.lower()
    out = []
    for c in connections:
        comp_fields = []
        for k in ("company", "position"):
            v = c.get(k, "")
            if isinstance(v, dict):
                v = v.get("localized") or v.get("text") or ""
            comp_fields.append(str(v))
        combined = " ".join(comp_fields).lower()
        if company_lower in combined:
            out.append(c)
    return out


def save_json(data, filename: str):
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def preview_connections(connections: List[Dict], n: int = 5):
    print(f"Previewing first {min(n, len(connections))} connections:")
    for c in connections[:n]:
        name = c.get("name") or "(no name)"
        profile = c.get("profile_url") or "(no url)"
        company = c.get("company") or "(no company)"
        position = c.get("position") or ""
        print(f" - {name} | {position} | {company} | {profile}")


def main():
    print("LinkedIn Connections → Company filter (CSV only)")
    csv_path = input("Path to your LinkedIn Connections CSV file: ").strip()
    if not csv_path or not os.path.exists(csv_path):
        print("CSV file not found. Export your connections from LinkedIn and provide the path to the CSV.")
        return

    connections = parse_linkedin_csv(csv_path)
    print(f"Loaded {len(connections)} connections from CSV.")
    preview_connections(connections, n=3)

    company = input("Target company name to match in your connections (e.g. Amazon): ").strip()
    if not company:
        print("Company is required.")
        return

    matches = filter_by_company(connections, company)
    out_file = f"linked_connections_{company.replace(' ', '_')}.json"
    save_json(matches, out_file)

    print(f"Saved {len(matches)} matches to {out_file}")
    if matches:
        print("Example match:")
        m = matches[0]
        print(json.dumps({"name": m.get("name"), "company": m.get("company"), "profile_url": m.get("profile_url")}, indent=2))


if __name__ == "__main__":
    main()
