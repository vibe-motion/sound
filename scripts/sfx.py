#!/usr/bin/env python3
"""Search & download SFX from Freesound using the Python standard library.

Uses the shell's http(s)_proxy settings.

  sfx.py freesound "<query>" [--license cc0|by|any] [--sort relevance|downloads|rating|short] [-n N] [-p PAGE] [--pages K]
                                       relevance (default) is re-ranked by downloads across K pages
  sfx.py get <out_dir> <key>...        keys: fs:<id>
"""
import argparse, hashlib, html, json, os, re, sys, tempfile, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) sfx-sources"}
CACHE = Path.home() / ".cache" / "sfx-sources"
INDEX = CACHE / "index.json"  # search results, so `get` knows title + download url
FS_LICENSE = {"cc0": '"Creative Commons 0"', "by": '("Attribution" OR "Creative Commons 0")', "any": None}
FS_LIC_SHORT = {"Creative Commons 0": "CC0", "Attribution": "BY", "Attribution NonCommercial": "BY-NC", "Sampling+": "Sampling+"}
FS_SORT = {"downloads": "Downloads (most first)", "rating": "Rating (highest first)",
           "relevance": "Automatic by relevance", "short": "Duration (shortest first)"}


def validate_url(url, hosts):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)):
        raise ValueError("URL must use HTTPS on an allowed Freesound host")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, timeout=60, tries=3, audio=False):
    hosts = {"cdn.freesound.org"} if audio else {"freesound.org", "www.freesound.org"}
    validate_url(url, hosts)
    opener = urllib.request.build_opener(SafeRedirect(hosts))
    limit = 32 * 1024 * 1024 if audio else 4 * 1024 * 1024
    for n in range(tries):
        try:
            with opener.open(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                validate_url(r.geturl(), hosts)
                if audio and r.headers.get_content_type() not in {
                        "audio/mpeg", "audio/mp3", "application/octet-stream"}:
                    raise ValueError("Expected an MP3 preview response")
                data = r.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("Response exceeds size limit")
                if audio and not (data.startswith(b"ID3") or
                                  (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)):
                    raise ValueError("Response has no MP3 header")
                return data
        except OSError:
            if n == tries - 1:
                raise
            time.sleep(1 + n)


def project_path(path):
    root = Path.cwd().resolve()
    target = Path(os.path.abspath(path))
    if not target.is_relative_to(root):
        raise ValueError("Output must be inside the current project directory")
    for part in (target, *target.parents):
        if part.is_symlink():
            raise ValueError("Symlinks are not allowed in output paths")
        if part == root:
            break
    return target


def write_new(path, data):
    # Publish a complete file atomically, without replacing files or symlinks.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.close()
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def load_index():
    if CACHE.is_symlink() or INDEX.is_symlink():
        raise ValueError("Symlinked cache is not supported")
    try:
        value = json.loads(INDEX.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_index(rows):
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = load_index()
    idx.update({r["key"]: r for r in rows})
    if CACHE.is_symlink() or INDEX.is_symlink():
        raise ValueError("Symlinked cache is not supported")
    with tempfile.NamedTemporaryFile(mode="w", dir=CACHE, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(idx, stream, ensure_ascii=False)
            stream.close()
            temp.replace(INDEX)
        finally:
            temp.unlink(missing_ok=True)


def show(rows, a, lic=False, hint=""):
    save_index(rows)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
        return
    for r in rows:
        print("\t".join([r["key"], r["title"], r["dur"]] + ([r["stats"]] if "stats" in r else []) + [r["license"]] * lic + ([r["desc"]] if r.get("desc") else []) + [r["preview"]] * a.urls))
    if not rows:
        print("(none)" + hint)


def freesound(a):
    # Pull several relevance pages and rank them by downloads, since sorting by downloads
    # server-side lets globally popular but off-topic sounds (gunshots, ambiences) win on a loose tag match.
    q = {"q": a.query, "s": FS_SORT[a.sort]}
    if FS_LICENSE[a.license]:
        q["f"] = "license:" + FS_LICENSE[a.license]
    pages = range(a.page, a.page + a.pages)
    with ThreadPoolExecutor(len(pages)) as ex:
        htmls = list(ex.map(lambda n: fetch("https://freesound.org/search/?" + urllib.parse.urlencode({**q, "page": n})).decode(), pages))
    rows = []
    for blk in (b for h in htmls for b in h.split('class="bw-search__result"')[1:]):
        g = lambda k: (re.search(rf'data-{k}="([^"]*)"', blk) or [None, ""])[1]
        lic = re.search(r'title="License: ([^"]+)"', blk)
        rt = re.search(r'aria-label="Average rating of ([\d.]+)"', blk)
        rn = re.search(r'bw-rating__count[^>]*>\((\d+)\)', blk)
        desc = re.search(r'<div class="max-h-60px[^"]*"\s*>\s*(.*?)\s*</div>', blk, re.S)
        sid, user, dl = g("sound-id"), g("username"), int(g("num-downloads") or 0)
        if not re.fullmatch(r"[0-9]+", sid):
            continue
        license_name = FS_LIC_SHORT.get(lic.group(1), lic.group(1)) if lic else "?"
        if a.license != "any" and license_name not in ({"CC0"} if a.license == "cc0" else {"CC0", "BY"}):
            continue
        rows.append({"source": f"https://freesound.org/people/{urllib.parse.quote(user, safe='')}/sounds/{sid}/", "key": f"fs:{sid}", "title": html.unescape(g("title")), "dur": f"{float(g('duration') or 0):.1f}s",
                     "author": user, "license": FS_LIC_SHORT.get(lic.group(1), lic.group(1)) if lic else "?", "preview": g("mp3").replace("-lq.mp3", "-hq.mp3"),
                     "url": g("mp3").replace("-lq.mp3", "-hq.mp3"), "downloads": dl,
                     "stats": f"↓{dl} ★{rt[1]}({rn[1]})" if rt and rn else f"↓{dl} ★-",
                     # the uploader's own words (mic, source, processing) are the closest thing to hearing it
                     "desc": html.unescape(re.sub(r"<[^>]+>|\s+", " ", desc[1])).strip()[:90] if desc else ""})
    if a.sort == "relevance":
        rows.sort(key=lambda r: -r["downloads"])
    show(rows[: a.n], a, lic=a.license != "cc0")


def get(a):
    out = project_path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    idx = load_index()

    def one(key):
        if not re.fullmatch(r"fs:[0-9]+", key):
            raise ValueError("Expected fs:<numeric id>")
        r = idx.get(key)
        if not isinstance(r, dict):
            raise ValueError("Unknown key — search first")
        lic = r.get("license", "?")
        allowed = {"cc0": {"CC0"}, "by": {"CC0", "BY"}}
        if a.license in allowed and lic not in allowed[a.license]:
            raise ValueError("License excluded; explicitly choose --license by or any if appropriate")
        if lic == "?":
            raise ValueError("Unknown license; verify the source before downloading")
        url = r["url"]
        validate_url(url, {"cdn.freesound.org"})
        if not urllib.parse.urlsplit(url).path.endswith(".mp3"):
            raise ValueError("Only MP3 previews are supported")
        source = r.get("source", "")
        validate_url(source, {"freesound.org"})
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", r.get("title", "")).strip("-")[:40]
        dst = project_path(out / f"fs_{key[3:]}{'_' + slug if slug else ''}.mp3")
        manifest = project_path(dst.with_suffix(".source.json"))
        if dst.exists() or manifest.exists():
            raise ValueError("Output already exists; choose another directory or remove it explicitly")
        data = fetch(url, timeout=300, audio=True)
        record = {k: r.get(k) for k in ("key", "title", "author", "license", "source")}
        record.update(preview=url, file=dst.name, sha256=hashlib.sha256(data).hexdigest())
        # Reserve metadata first; a competing invocation cannot overwrite this pair.
        write_new(manifest, json.dumps(record, ensure_ascii=False, indent=2).encode())
        try:
            write_new(dst, data)
        except Exception:
            manifest.unlink()
            raise
        return {"key": key, "file": str(dst), "metadata": str(manifest), "license": lic}

    def safe(key):
        try:
            return one(key)
        except (OSError, ValueError, KeyError, TypeError) as e:
            return {"key": key, "error": str(e)}

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(safe, dict.fromkeys(a.keys)))
    if a.json:
        print(json.dumps(results, ensure_ascii=False))
    else:
        for result in results:
            print(f"FAIL {result['key']}: {result['error']}" if "error" in result else
                  f"{result['file']} [{result['license']}; metadata: {result['metadata']}]")
    if any("error" in result for result in results):
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("freesound"); f.add_argument("query"); f.add_argument("--license", choices=FS_LICENSE, default="cc0")
    f.add_argument("--sort", choices=FS_SORT, default="relevance"); f.add_argument("-n", type=int, default=8); f.add_argument("--urls", action="store_true")
    f.add_argument("-p", "--page", type=int, default=1)
    f.add_argument("--pages", type=int, default=3, help="relevance pages (15 each) to rank by downloads"); f.set_defaults(fn=freesound)
    g = sp.add_parser("get"); g.add_argument("out_dir"); g.add_argument("keys", nargs="+"); g.set_defaults(fn=get)
    g.add_argument("--license", choices=FS_LICENSE, default="cc0")
    for parser in (f, g):
        parser.add_argument("--json", action="store_true", help="machine-readable results")
    a = ap.parse_args()
    if a.cmd == "freesound" and not (1 <= a.pages <= 5 and 1 <= a.page <= 100 and 1 <= a.n <= 100):
        ap.error("pages must be 1–5, page and n must be 1–100")
    try:
        a.fn(a)
    except (OSError, ValueError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
