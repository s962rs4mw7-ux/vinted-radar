import json, os, re, time, http.cookiejar, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

CFG = json.load(open("config.json", encoding="utf-8"))
PATH = "data/items.json"
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
UA = "VintedRadarPersonal/1.0 (personal use)"
MAX_NOTIF = 15

MOD = {"A1706": "2016-2017", "A1707": "2016-2017", "A1708": "2016-2017",
       "A1989": "2018-2019", "A1990": "2018-2019", "A2159": "2019", "A2141": "2019",
       "A2251": "2020", "A2289": "2020", "A2338": "2020-2022", "A2442": "2021",
       "A2485": "2021", "A2779": "2023", "A2780": "2023"}


def year_of(text):
    t = text.upper()
    m = re.search(r"\b(20(?:1[5-9]|2[0-6]))\b", t)
    if m:
        y = int(m.group(1))
        return m.group(1), "ok" if 2017 <= y <= 2022 else "out"
    m = re.search(r"A\s?(1706|1707|1708|1989|1990|2159|2141|2251|2289|2338|2442|2485|2779|2780)", t)
    if m:
        v = MOD["A" + m.group(1)]
        y = int(v[:4])
        return v, "ok" if 2017 <= y <= 2022 else "out"
    if re.search(r"\bM2\b", t):
        return "2022-2023", "ok"
    if re.search(r"\bM1\b", t):
        return "2020-2021", "ok"
    return "?", "?"


def load():
    if os.path.exists(PATH):
        return json.load(open(PATH, encoding="utf-8"))
    return {"items": [], "seen": [], "status": {}, "updated": "", "alert": ""}


def notify(title, message, click="", image=""):
    if not WEBHOOK:
        return
    e = {"title": title[:250], "description": message, "color": 0x2B5FD9,
         "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if click:
        e["url"] = click
    if image:
        e["image"] = {"url": image}
    req = urllib.request.Request(WEBHOOK, json.dumps({"embeds": [e]}).encode("utf-8"),
                                 {"Content-Type": "application/json", "User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as ex:
        print("discord error", ex)
    time.sleep(1)


def fetch(m):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept", "application/json"),
                     ("Accept-Language", "fr,en;q=0.8")]
    base = "https://www.vinted." + m["domain"]
    op.open(base + "/", timeout=20).read(1)
    q = {"search_text": CFG["query"],
         "price_from": round(CFG["min"] * m["rate"]),
         "price_to": round(CFG["max"] * m["rate"]),
         "order": "newest_first", "per_page": 48, "page": 1}
    r = op.open(base + "/api/v2/catalog/items?" + urllib.parse.urlencode(q), timeout=20)
    return json.load(r).get("items", []), base


def main():
    st = load()
    before = json.dumps(st, sort_keys=True)
    first = not st["seen"]
    seen = set(st["seen"])
    new = []
    now = datetime.now(timezone.utc)
    for m in CFG["markets"]:
        try:
            items, base = fetch(m)
            st["status"][m["code"]] = "ok"
        except urllib.error.HTTPError as e:
            st["status"][m["code"]] = "HTTP %s" % e.code
            time.sleep(2)
            continue
        except Exception:
            st["status"][m["code"]] = "erreur"
            time.sleep(2)
            continue
        for it in items:
            key = "%s:%s" % (m["code"], it.get("id"))
            if key in seen:
                continue
            seen.add(key)
            p = it.get("price")
            amount = float(p["amount"]) if isinstance(p, dict) else float(p or 0)
            title = it.get("title", "")
            y, flag = year_of(title)
            new.append({"id": key, "title": title, "eur": round(amount / m["rate"], 2),
                        "price": amount, "cur": m["currency"], "country": m["name"],
                        "url": it.get("url") or "%s/items/%s" % (base, it.get("id")),
                        "photo": (it.get("photo") or {}).get("url", ""),
                        "year": y, "flag": flag, "found": now.isoformat(timespec="seconds")})
        time.sleep(2)

    if new:
        st["items"] = (new + st["items"])[:2000]
        st["seen"] = list(seen)[-4000:] if len(seen) > 4000 else list(seen)
        if first:
            notify("Radar MacBook actif", "%d annonces existantes enregistrées. Les prochaines seront notifiées." % len(new))
        else:
            for n in new[:MAX_NOTIF]:
                notify("%s - %s EUR" % (n["title"][:80], round(n["eur"])),
                     "%s | %s %s | annee %s | detecte %s" % (
                         n["country"], round(n["price"]), n["cur"], n["year"],
                         now.strftime("%d/%m %H:%M UTC")),
                     click=n["url"], image=n["photo"])
            if len(new) > MAX_NOTIF:
                notify("Radar MacBook", "+%d autres nouvelles annonces, voir la page." % (len(new) - MAX_NOTIF))

    ok = [k for k, v in st["status"].items() if v == "ok"]
    if not ok:
        last = st.get("alert")
        if not last or (now - datetime.fromisoformat(last)).total_seconds() > 43200:
            notify("Radar MacBook bloque", "Vinted refuse les requetes (voir data/items.json, champ status).")
            st["alert"] = now.isoformat(timespec="seconds")

    st["updated"] = now.strftime("%Y-%m-%d")
    if json.dumps(st, sort_keys=True) != before:
        os.makedirs("data", exist_ok=True)
        json.dump(st, open(PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print("nouvelles:", len(new), "statuts:", st["status"])


main()
