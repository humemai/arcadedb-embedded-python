#!/usr/bin/env python3
"""Normalize a Stack Exchange dump into one multi-model Parquet dataset (for all backends).

Two sources:
  * LOCAL  — an already-extracted dataset under bindings/python/examples/data/<name>/
             (e.g. stackoverflow-tiny) with Posts.xml + Users.xml. No download.
  * REMOTE — a site name like coffee.stackexchange.com → download+extract from archive.org.

Output (Parquet) in <dataset>/prepared/:
  posts (id, post_type, parent_id, accepted_answer_id, owner_user_id, score, view_count,
         creation_date, title, tags, text), users (id, display_name, reputation, creation_date),
  edges_posted (user_id, post_id), edges_answers (answer_id, question_id).

Usage:  python prepare.py stackoverflow-tiny      # local
        python prepare.py coffee.stackexchange.com # remote
Deps:   pandas, pyarrow  (+ py7zr for remote)
"""
import os
import re
import sys
import time
import urllib.request
from xml.etree import ElementTree as ET

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DATA = os.path.abspath(os.path.join(
    HERE, "..", "..", "..", "..", "bindings", "python", "examples", "data"))

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean(html):
    return _WS.sub(" ", _TAG.sub(" ", html)).strip() if html else ""


def parse_rows(xml_path):
    for _, el in ET.iterparse(xml_path, events=("end",)):
        if el.tag == "row":
            yield el.attrib
            el.clear()


def to_int(v):
    return int(v) if v not in (None, "") else None


def normalize(raw_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    print(f"[parse] Users.xml")
    users = [
        {"id": to_int(a.get("Id")), "display_name": a.get("DisplayName"),
         "reputation": to_int(a.get("Reputation")), "creation_date": a.get("CreationDate")}
        for a in parse_rows(os.path.join(raw_dir, "Users.xml"))
    ]
    print(f"[parse] Posts.xml")
    posts, posted, answers = [], [], []
    for a in parse_rows(os.path.join(raw_dir, "Posts.xml")):
        pid, ptype = to_int(a.get("Id")), to_int(a.get("PostTypeId"))
        parent, owner = to_int(a.get("ParentId")), to_int(a.get("OwnerUserId"))
        posts.append({
            "id": pid, "post_type": ptype, "parent_id": parent,
            "accepted_answer_id": to_int(a.get("AcceptedAnswerId")),
            "owner_user_id": owner, "score": to_int(a.get("Score")),
            "view_count": to_int(a.get("ViewCount")), "creation_date": a.get("CreationDate"),
            "title": a.get("Title"), "tags": a.get("Tags"),
            "text": (clean(a.get("Title")) + " " + clean(a.get("Body"))).strip(),
        })
        if owner is not None:
            posted.append({"user_id": owner, "post_id": pid})
        if ptype == 2 and parent is not None:
            answers.append({"answer_id": pid, "question_id": parent})

    frames = {"users": pd.DataFrame(users), "posts": pd.DataFrame(posts),
              "edges_posted": pd.DataFrame(posted), "edges_answers": pd.DataFrame(answers)}
    for name, df in frames.items():
        path = os.path.join(out_dir, f"{name}.parquet")
        df.to_parquet(path, index=False)
        print(f"[write] {name:14} {len(df):>9,} rows -> {path}")
    q = int((frames["posts"]["post_type"] == 1).sum())
    a = int((frames["posts"]["post_type"] == 2).sum())
    print(f"\nDATASET READY: users={len(frames['users']):,} posts={len(frames['posts']):,} "
          f"(Q={q:,} A={a:,}) posted={len(frames['edges_posted']):,} answers={len(frames['edges_answers']):,}")


def download_and_extract(site):
    import py7zr
    raw = os.path.join(HERE, "raw")
    os.makedirs(raw, exist_ok=True)
    archive = os.path.join(raw, f"{site}.7z")
    if not os.path.exists(archive):
        url = f"https://archive.org/download/stackexchange/{site}.7z"
        print(f"[download] {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "scipy2026-bench/1.0"})
        t0 = time.time()
        with urllib.request.urlopen(req) as r, open(archive, "wb") as f:
            f.write(r.read())
        print(f"[download] {os.path.getsize(archive) / 1e6:.1f} MB in {time.time() - t0:.1f}s")
    ex = os.path.join(raw, site)
    with py7zr.SevenZipFile(archive, "r") as z:
        z.extract(path=ex, targets=["Posts.xml", "Users.xml"])
    return ex


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "stackoverflow-tiny"
    local = os.path.join(EXAMPLES_DATA, arg)
    if os.path.isdir(local) and os.path.exists(os.path.join(local, "Posts.xml")):
        print(f"[source] LOCAL {local}")
        normalize(local, os.path.join(local, "prepared"))
    else:
        print(f"[source] REMOTE {arg}")
        raw_dir = download_and_extract(arg)
        normalize(raw_dir, os.path.join(HERE, "prepared", arg))


if __name__ == "__main__":
    main()
