from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import os
from datetime import date, datetime
from supabase import create_client, Client
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvkbcstbhoqrsegbptpy.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2a2Jjc3RiaG9xcnNlZ2JwdHB5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3ODk2MzUsImV4cCI6MjA5NDM2NTYzNX0.81qvhH_Wf-QU_kshSWZfBzCiZwzH27xf2bUxJ2KZ-iE")

db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Aktien-Universum für Scanner (weniger bekannte Mid/Small-Caps) ────────────

STOCK_UNIVERSE = [
    # US Mid-Cap Industrie & Dienstleistungen
    "ALLE","AOS","AWI","BCO","BRC","CBRL","CFX","CGNX","CLH","CRVL",
    "CSV","DCI","DLB","DNB","EAT","EHC","ENSG","EPAM","ESE","EWBC",
    "EXPO","FAF","FBIN","FFIN","FHI","FLO","FORM","FOUR","FSS","GATX",
    "GMS","GPI","GRMN","HCSG","HNI","HRI","HS","IBP","ICFI","IDCC",
    "INN","INSW","ITT","J","JBSS","JOE","KAI","KFRC","KMT","KNF",
    "KNX","KTB","LANC","LCII","LNN","MATX","MGRC","MHO","MKSI","MLR",
    "MMSI","MMS","MRC","MSA","MTZ","MWA","NARI","NHC","NRC","NSA",
    "NUS","OGS","OII","OMCL","ORA","PATK","PAYO","PDCO","PH","PIPR",
    "PLXS","PMFG","POOL","POWL","PRDO","PRGS","PSN","PTCT","RES","RLI",
    "RRR","RUSHA","SCI","SIGI","SJW","SKT","SLG","SSD","STC","STEP",
    "SWX","TASK","TGNA","TNK","TPC","TREX","TRMK","TRNC","TRR","TSCO",
    "UFPI","UMBF","URBN","USAC","USCF","UTHR","VBTX","VCEL","VICR","VIRT",
    "VSCO","WGO","WHR","WINA","WLYB","WSBF","WSO","WTFC","WTRG","WWW",
    # US Healthcare / Biotech weniger bekannt
    "ACAD","ACLS","AGIO","AKBA","ALEC","ANAB","APLS","ARDX","ARQT","ASND",
    "ATRC","AVNS","AXNX","BCPC","BEAT","BFLY","BLFS","BMRN","BPMC","BRKR",
    "CENTA","CHRS","CLFD","CNMD","CNST","CODA","CPRX","CRNX","CRVS","CSII",
    "CTSO","DXCM","ELAN","ELMD","ENTA","EVBG","EVER","FOLD","FWRD","GKOS",
    "GLPG","GLYC","HALO","HCAT","HIIQ","HMHC","HRMY","HRTX","HSIC","ICAD",
    "ICLR","IDEX","IMED","INMD","IONS","IRMD","ITGR","JAZZ","KIDS","KRTX",
    "LGND","LMAT","LNTH","LQDA","LWAY","MDXG","MGNX","MKTX","MNKD","MORF",
    "MRNA","NBTX","NKTR","NRIX","NTLA","NVCR","NVST","NXTC","OFIX","OMAB",
    "OMER","OPCH","PCRX","PDVX","PHAT","PMVP","PNTM","PTGX","PTLA","QDEL",
    "RARE","RCKT","RDVT","RGEN","RLMD","RPRX","RVMD","RXRX","RYTM","SAGE",
    "SANA","SDGR","SEER","SLDB","SLNO","SMMT","SPNV","SPRB","SRTX","STOK",
    "SUPN","SWAV","TCMD","TGTX","TMCI","TNXP","TPVG","TRDA","TRIL","TROY",
    "TVTX","UDMY","URGN","VCEL","VRTX","VTRS","XOMA","XRAY","YMAB","ZLAB",
    # US Tech weniger bekannt
    "ACMR","ADEA","ADTN","AGYS","AMBA","APPF","ARLO","ATNI","AVAV","AVLR",
    "AZPN","BAND","BIGC","BLKB","BOMB","BSIG","CARG","CCSI","CLSK","CMPR",
    "CODA","COHU","COMM","CSGS","CSWI","CTXS","CWAN","DDD","DMRC","DOCN",
    "DV","DWAC","EGHT","EGAN","ENFN","EPAY","EVTC","EXLS","EXTR","FARO",
    "FBMS","FIVN","FLNC","FRSH","GENI","GILT","GLBE","GRND","GSAT","GTLB",
    "HAYW","HIMS","HLIT","HMPT","IIIV","INFA","INFN","INST","IO","IOVA",
    "JAMF","JNPR","JOSE","KLIC","LPSN","LQDT","LSPD","LSTR","LYTS","MANH",
    "MARA","MCFE","MGNI","MIMO","MKSI","MODN","MRIN","MSTR","NCNO","NEON",
    "NTCT","NTNX","NVEI","NXGN","OMNI","OPEN","OPFI","PAYA","PCOR","PEGA",
    "PERI","PGNY","POWI","PRFT","PRGS","PSFE","PTLO","PWSC","QLYS","QMCO",
    "QUOT","RAMP","RELY","RPAY","RSKD","SDGR","SEIC","SHSP","SMAR","SMSI",
    "SPSC","SSYS","STNE","SWIR","SYBT","TASK","TOST","TPVG","TRMR","TRUP",
    "TTEC","TTGT","TUYA","TXRH","TYRA","UPLD","UPWK","VERI","VIAV","VNET",
    "VRNS","VRRM","VSAT","WEAV","WDAY","WKME","WIX","XMTR","YEXT","ZETA",
    # Deutschland MDAX / SDAX / weniger bekannt
    "LEO.DE","EVK.DE","FNTN.DE","GBF.DE","HAB.DE","HDD.DE","HFG.DE",
    "HIL.DE","HOT.DE","HNR1.DE","JDEP.DE","JEN.DE","KGX.DE","KWS.DE",
    "MDGN.DE","MED.DE","MVST.DE","NDX1.DE","NEM.DE","NWO.DE","OHB.DE",
    "PAH3.DE","PBB.DE","PDY.DE","PSM.DE","PUM.DE","RAA.DE","RRTL.DE",
    "SDF.DE","SDM.DE","SFQ.DE","SGL.DE","SKB.DE","SMHN.DE","SZG.DE",
    "SZU.DE","TCOM.DE","TGH.DE","TKA.DE","TLX.DE","TUI1.DE","VBK.DE",
    "VIB3.DE","VNA.DE","WAF.DE","WCH.DE","WET.DE","WUW.DE","UTDI.DE",
    # Frankreich / Niederlande / Schweden weniger bekannt
    "ALSTOM.PA","GL.PA","ICAD.PA","IPSOS.PA","LDC.PA","MCPHY.PA",
    "NEXANS.PA","OPT.PA","SAFE.PA","SIGNAUX.PA","SQLI.PA","TXCOM.PA",
    "BESI.AS","FLOW.AS","HEIJM.AS","IMCD.AS","NEDAP.AS","NSI.AS",
    "ACAD.ST","ACER.ST","ADDT.ST","BETS.ST","CEVT.ST","CLAV.ST",
    # Kanada weniger bekannt
    "ATD.TO","BYD.TO","CLS.TO","CRNC.TO","EMP-A.TO","FSV.TO",
    "GFL.TO","KXS.TO","LNF.TO","MDA.TO","MRE.TO","TFII.TO",
]

SCAN_SAMPLE_SIZE = 80  # pro Scan zufällig 80 auswählen


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def safe_float(df, row, col):
    try:
        v = df.loc[row, col]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None


def get_5y_growth(growth_est):
    try:
        v = growth_est.loc["+5y"].dropna().iloc[0]
        return float(v)
    except Exception:
        return None


def fmt(value):
    if value >= 1e12: return f"{value / 1e12:.2f} Bio."
    elif value >= 1e9: return f"{value / 1e9:.2f} Mrd."
    elif value >= 1e6: return f"{value / 1e6:.2f} Mio."
    return f"{value:.2f}"


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_kuv(kuv):
    if kuv <= 1.0:   return 10.0, "Sehr gut"
    elif kuv <= 2.0: return 10 - 2 * (kuv - 1.0), "Gut"
    elif kuv <= 3.0: return 8 - 4 * (kuv - 2.0), "Okay"
    elif kuv <= 5.0: return max(0, 4 - 2 * (kuv - 3.0)), "Schwach"
    return 0.0, "Teuer"


def score_kgv(kgv):
    if kgv is None or kgv <= 0: return 0.0, "Verlust erwartet"
    if kgv <= 10:    return 10.0, "Sehr gut"
    elif kgv <= 15:  return 10 - 0.4 * (kgv - 10), "Gut"
    elif kgv <= 20:  return 8 - 0.6 * (kgv - 15), "Okay"
    elif kgv <= 25:  return 5 - 0.4 * (kgv - 20), "Schwach"
    elif kgv <= 40:  return max(0, 3 - 0.2 * (kgv - 25)), "Teuer"
    return 0.0, "Sehr teuer"


def combined_rating(kuv_s, kgv_s):
    score = round(0.4 * kuv_s + 0.6 * kgv_s, 2)
    if score >= 8.5:   label = "Stark unterbewertet"
    elif score >= 7.0: label = "Attraktiv bewertet"
    elif score >= 5.5: label = "Fair bewertet"
    elif score >= 3.5: label = "Leicht überbewertet"
    else:              label = "Stark überbewertet"
    return score, label


# ── Kursziel ──────────────────────────────────────────────────────────────────

def effective_kgv(raw):
    if raw <= 40:    return raw, None
    elif raw <= 60:  eff = raw * 0.80; return eff, f"KGV {raw:.0f}× → auf {eff:.0f}× reduziert"
    elif raw <= 100: eff = raw * 0.60; return eff, f"KGV {raw:.0f}× → auf {eff:.0f}× reduziert (Compression)"
    else:            return 40.0, f"KGV {raw:.0f}× → auf 40× normalisiert"


def calculate_target_price(market_cap, shares, price_raw, current_revenue,
                            net_income, rev_2029, earnings_2029, currency):
    out = {}
    if not shares or not price_raw: return out
    if net_income and net_income > 0 and earnings_2029:
        eff, note = effective_kgv(market_cap / net_income)
        out.update({"tp_kgv": round((eff * earnings_2029) / shares, 2),
                    "current_kgv_real": round(market_cap / net_income, 1),
                    "eff_kgv": round(eff, 1), "kgv_note": note})
    elif earnings_2029 and earnings_2029 > 0 and (not net_income or net_income <= 0):
        out.update({"tp_kgv": round((30.0 * earnings_2029) / shares, 2),
                    "current_kgv_real": None, "eff_kgv": 30.0,
                    "kgv_note": "Kein aktueller Gewinn – KGV 30× für 2029 angenommen"})
    elif earnings_2029 and earnings_2029 <= 0:
        out["kgv_note"] = "Verlust in 2029 erwartet – KGV-Kursziel nicht berechenbar"
    if current_revenue and current_revenue > 0 and rev_2029:
        kuv_real = market_cap / current_revenue
        out.update({"tp_kuv": round((kuv_real * rev_2029) / shares, 2),
                    "current_kuv_real": round(kuv_real, 2)})
    hk, hu = "tp_kgv" in out, "tp_kuv" in out
    if hk and hu:   combined = 0.4 * out["tp_kuv"] + 0.6 * out["tp_kgv"]
    elif hk:        combined = out["tp_kgv"]
    elif hu:        combined = out["tp_kuv"]
    else:           return out
    out["tp_combined"] = round(combined, 2)
    out["upside_pct"] = round((combined - price_raw) / price_raw * 100, 1)
    out["currency"] = currency
    return out


# ── Kerndaten laden ───────────────────────────────────────────────────────────

def fetch_stock_data(symbol):
    t = yf.Ticker(symbol)
    info = t.info
    market_cap = info.get("marketCap")
    shares = info.get("sharesOutstanding")
    name = info.get("longName") or info.get("shortName") or symbol
    price_raw = info.get("currentPrice") or info.get("regularMarketPrice")
    currency = info.get("currency", "USD")
    current_revenue = info.get("totalRevenue")
    net_income = info.get("netIncomeToCommon")

    if not market_cap:
        return {"error": "Marktkapitalisierung nicht verfügbar"}

    rev_est = t.revenue_estimate
    earn_est = t.earnings_estimate
    growth_est = t.growth_estimates

    rev_2027 = safe_float(rev_est, "+1y", "avg") if rev_est is not None and not rev_est.empty else None
    eps_2027 = safe_float(earn_est, "+1y", "avg") if earn_est is not None and not earn_est.empty else None

    growth_5y = get_5y_growth(growth_est) if growth_est is not None and not growth_est.empty else None
    if growth_5y is None and rev_est is not None and not rev_est.empty:
        growth_5y = safe_float(rev_est, "+1y", "growth")
    growth_5y = max(0.0, min(growth_5y or 0.08, 0.60))

    factor = (1 + growth_5y) ** 2
    rev_2029 = rev_2027 * factor if rev_2027 else None
    earnings_2029 = (eps_2027 * shares * factor) if (eps_2027 and shares) else None

    kuv_2029 = market_cap / rev_2029 if rev_2029 else None
    kgv_2029 = market_cap / earnings_2029 if (earnings_2029 and earnings_2029 > 0) else None

    kuv_score = kuv_label = kgv_score = kgv_label = total_score = total_label = None
    if kuv_2029 is not None:
        kuv_score, kuv_label = score_kuv(kuv_2029); kuv_score = round(kuv_score, 2)
    if kgv_2029 is not None:
        kgv_score, kgv_label = score_kgv(kgv_2029); kgv_score = round(kgv_score, 2)
    if kuv_score is not None and kgv_score is not None:
        total_score, total_label = combined_rating(kuv_score, kgv_score)

    target = calculate_target_price(market_cap, shares, price_raw,
                                    current_revenue, net_income, rev_2029, earnings_2029, currency)
    return {
        "name": name, "symbol": symbol, "market_cap": fmt(market_cap),
        "price": f"{price_raw:.2f} {currency}" if price_raw else "—",
        "price_raw": price_raw, "currency": currency,
        "growth": f"{growth_5y * 100:.1f}",
        "rev_2029": fmt(rev_2029) if rev_2029 else None,
        "kuv_2029": f"{kuv_2029:.2f}" if kuv_2029 else None,
        "kuv_score": kuv_score, "kuv_label": kuv_label,
        "earnings_2029": fmt(earnings_2029) if earnings_2029 else None,
        "kgv_2029": f"{kgv_2029:.1f}" if kgv_2029 else None,
        "kgv_score": kgv_score, "kgv_label": kgv_label,
        "total_score": total_score, "total_label": total_label, **target,
    }


# ── Watchlist DB ──────────────────────────────────────────────────────────────

def db_load_watchlist():
    rows = db.table("watchlist").select("*, watchlist_history(*)").execute().data
    wl = {}
    for row in rows:
        sym = row["symbol"]
        history = sorted(row.get("watchlist_history", []), key=lambda x: x["date"])
        wl[sym] = {
            "name": row["name"], "latest": row.get("latest_data") or {},
            "history": [{"date": h["date"], "total_score": h["total_score"],
                         "kuv_score": h["kuv_score"], "kgv_score": h["kgv_score"],
                         "tp_combined": h["tp_combined"], "upside_pct": h["upside_pct"]}
                        for h in history]
        }
    return wl


def db_upsert_watchlist_entry(symbol, name, latest_data, today, entry):
    db.table("watchlist").upsert({"symbol": symbol, "name": name,
                                   "latest_data": latest_data, "updated_at": "now()"}).execute()
    db.table("watchlist_history").upsert({
        "symbol": symbol, "date": today,
        "total_score": entry.get("total_score"), "kuv_score": entry.get("kuv_score"),
        "kgv_score": entry.get("kgv_score"), "tp_combined": entry.get("tp_combined"),
        "upside_pct": entry.get("upside_pct"),
    }).execute()


# ── Analysten-Prognosen ───────────────────────────────────────────────────────

def _next_quarter(year, q):
    return (year, q + 1) if q < 4 else (year + 1, 1)

def _safe_val(df, key, col="avg"):
    try:
        if df is None or df.empty or key not in df.index: return None
        v = df.loc[key, col] if col in df.columns else None
        return float(v) if v is not None and not pd.isna(v) else None
    except Exception:
        return None

def fetch_and_save_estimates(symbol):
    try:
        t = yf.Ticker(symbol)
        rev_est  = t.revenue_estimate
        earn_est = t.earnings_estimate
        today    = str(date.today())
        cy = date.today().year
        cq = (date.today().month - 1) // 3 + 1

        estimates = []

        # Jährliche Schätzungen
        for key, year in [("0y", cy), ("+1y", cy + 1), ("+2y", cy + 2)]:
            rev = _safe_val(rev_est,  key)
            eps = _safe_val(earn_est, key)
            if rev is not None or eps is not None:
                estimates.append({"period": str(year), "period_type": "annual",
                                   "revenue_est": rev, "eps_est": eps})

        # Quartalschätzungen
        qy, qq = cy, cq
        for key in ["0q", "+1q", "+2q", "+3q"]:
            rev = _safe_val(rev_est,  key)
            eps = _safe_val(earn_est, key)
            if rev is not None or eps is not None:
                estimates.append({"period": f"{qy}Q{qq}", "period_type": "quarterly",
                                   "revenue_est": rev, "eps_est": eps})
            qy, qq = _next_quarter(qy, qq)

        # Nur speichern wenn sich etwas geändert hat
        for est in estimates:
            period = est["period"]
            ptype  = est["period_type"]
            rev    = est["revenue_est"]
            eps    = est["eps_est"]

            last = db.table("analyst_estimates_history").select("revenue_est,eps_est") \
                .eq("symbol", symbol).eq("period", period).eq("period_type", ptype) \
                .order("recorded_date", desc=True).limit(1).execute().data

            changed = True
            if last:
                lr = float(last[0]["revenue_est"]) if last[0]["revenue_est"] is not None else None
                le = float(last[0]["eps_est"])     if last[0]["eps_est"]     is not None else None
                rev_chg = rev is not None and lr is not None and abs(rev - lr) / max(abs(lr), 1) > 0.001
                eps_chg = eps is not None and le is not None and abs(eps - le) / max(abs(le), 0.01) > 0.001
                new_val = (rev is not None and lr is None) or (eps is not None and le is None)
                changed = rev_chg or eps_chg or new_val

            if changed:
                db.table("analyst_estimates_history") \
                    .delete().eq("symbol", symbol).eq("period", period) \
                    .eq("period_type", ptype).eq("recorded_date", today).execute()
                db.table("analyst_estimates_history").insert({
                    "symbol": symbol, "recorded_date": today,
                    "period": period, "period_type": ptype,
                    "revenue_est": rev, "eps_est": eps,
                }).execute()
    except Exception:
        pass  # Schätzungen nicht kritisch für Watchlist-Refresh


# ── Portfolio DB ──────────────────────────────────────────────────────────────

def db_load_portfolio(positions_table="portfolio_positions",
                      history_table="portfolio_pos_history",
                      summary_table="portfolio_history"):
    positions_raw = db.table(positions_table).select(f"*, {history_table}(*)").execute().data
    history_raw = db.table(summary_table).select("*").order("date").execute().data
    positions = {}
    for row in positions_raw:
        sym = row["symbol"]
        ph = sorted(row.get(history_table, []), key=lambda x: x["date"])
        status_key = "sell_date" if "sell_date" in row else "cover_date"
        close_price_key = "sell_price" if "sell_price" in row else "cover_price"
        close_pct_key = "sell_pct" if "sell_pct" in row else "cover_pct"
        positions[sym] = {
            "name": row["name"],
            "buy_date": row.get("buy_date") or row.get("short_date"),
            "buy_price": float(row.get("buy_price") or row.get("short_price") or 0),
            "shares": float(row["shares"]),
            "investment": float(row["investment"]),
            "currency": row["currency"],
            "status": row["status"],
            "close_date": row.get(status_key),
            "close_price": float(row[close_price_key]) if row.get(close_price_key) else None,
            "close_pct": float(row[close_pct_key]) if row.get(close_pct_key) else None,
            "daily_history": [
                {"date": h["date"], "price": float(h["price"] or 0),
                 "value": float(h["value"] or 0), "score": h["score"],
                 "daily_pct": float(h["daily_pct"] or 0), "total_pct": float(h["total_pct"] or 0)}
                for h in ph
            ]
        }
    port_history = [{"date": h["date"], "total_value": float(h["total_value"] or 0),
                     "total_invested": float(h["total_invested"] or 0),
                     "daily_pct": float(h["daily_pct"] or 0)} for h in history_raw]
    return {"positions": positions, "portfolio_history": port_history}


def _refresh_portfolio_generic(score_threshold_fn, buy_key, positions_table,
                                history_table, summary_table, short_mode=False):
    wl = db_load_watchlist()
    portfolio = db_load_portfolio(positions_table, history_table, summary_table)
    positions = portfolio["positions"]
    port_history = portfolio["portfolio_history"]
    today = str(date.today())
    errors = []

    # Auto-Buy auf Basis gespeicherter Watchlist-Scores (zuverlässig, kein Fetch-Fehler möglich)
    buy_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    for symbol, wl_entry in wl.items():
        latest = wl_entry.get("latest") or {}
        score = latest.get("total_score")
        price = latest.get("price_raw")
        already_active = positions.get(symbol, {}).get("status") == "active"
        if score is not None and score_threshold_fn(score) and price and not already_active:
            shares = round(1000 / price, 6)
            row = {"symbol": symbol, "name": wl_entry.get("name", symbol),
                   buy_key: buy_ts, "short_price" if short_mode else "buy_price": round(price, 4),
                   "shares": shares, "investment": 1000,
                   "currency": latest.get("currency", "USD"), "status": "active"}
            # Alte Position + alte History löschen damit Performance sauber von Kaufzeitpunkt startet
            db.table(history_table).delete().eq("symbol", symbol).execute()
            db.table(positions_table).delete().eq("symbol", symbol).execute()
            db.table(positions_table).insert(row).execute()
            positions[symbol] = {
                "name": wl_entry.get("name", symbol), "buy_date": buy_ts,
                "buy_price": round(price, 4), "shares": shares,
                "investment": 1000, "currency": latest.get("currency", "USD"),
                "status": "active", "close_date": None,
                "close_price": None, "close_pct": None, "daily_history": [],
            }

    # Frische Kurse nur für aktive Positionen laden
    active_symbols = [sym for sym, pos in positions.items() if pos["status"] == "active"]
    fresh = {}
    def fetch_one(sym):
        try:
            d = fetch_stock_data(sym)
            return sym, d if "error" not in d else None
        except Exception as e:
            errors.append(f"{sym}: {e}")
            return sym, None
    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, d in ex.map(fetch_one, active_symbols):
            if d:
                fresh[sym] = d

    total_value = total_invested = 0

    for symbol, pos in positions.items():
        if pos["status"] != "active": continue
        d = fresh.get(symbol)
        if not d or not d.get("price_raw"): continue

        price = d["price_raw"]
        score = d.get("total_score")
        buy_price = pos["buy_price"]

        if short_mode:
            # Short P&L: profitiert wenn Kurs fällt
            current_value = round(pos["investment"] * (2 - price / buy_price), 2)
            daily_history = pos["daily_history"]
            prev = [h for h in daily_history if h["date"] != today]
            prev_price = prev[-1]["price"] if prev else buy_price
            daily_pct = round((prev_price - price) / prev_price * 100, 2)  # invertiert
            total_pct = round((buy_price - price) / buy_price * 100, 2)
        else:
            current_value = round(pos["shares"] * price, 2)
            daily_history = pos["daily_history"]
            prev = [h for h in daily_history if h["date"] != today]
            prev_price = prev[-1]["price"] if prev else buy_price
            daily_pct = round((price - prev_price) / prev_price * 100, 2)
            total_pct = round((price - buy_price) / buy_price * 100, 2)

        db.table(history_table).delete().eq("symbol", symbol).eq("date", today).execute()
        db.table(history_table).insert({
            "symbol": symbol, "date": today, "price": round(price, 4),
            "value": current_value, "score": score,
            "daily_pct": daily_pct, "total_pct": total_pct,
        }).execute()

        # Auto-Close
        should_close = (score is not None and (
            (not short_mode and score < 8) or (short_mode and score > 2)
        ))
        close_col = "cover_date" if short_mode else "sell_date"
        close_price_col = "cover_price" if short_mode else "sell_price"
        close_pct_col = "cover_pct" if short_mode else "sell_pct"

        if should_close:
            db.table(positions_table).update({
                "status": "closed", close_col: today,
                close_price_col: round(price, 4), close_pct_col: total_pct,
            }).eq("symbol", symbol).execute()
        else:
            total_value += current_value
            total_invested += pos["investment"]

    prev_port = port_history[-1] if port_history else None
    prev_total = prev_port["total_value"] if prev_port and prev_port["date"] != today else (total_invested or 1)
    daily_pct = round((total_value - prev_total) / prev_total * 100, 2) if prev_total else 0

    db.table(summary_table).delete().eq("date", today).execute()
    db.table(summary_table).insert({
        "date": today, "total_value": round(total_value, 2),
        "total_invested": total_invested, "daily_pct": daily_pct,
    }).execute()

    return {"ok": True, "errors": errors,
            "data": db_load_portfolio(positions_table, history_table, summary_table)}


# ── Routen ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bewerten")
def bewerten():
    symbol = request.args.get("ticker", "").strip().upper()
    if not symbol:
        return jsonify({"error": "Kein Ticker angegeben"}), 400
    try:
        return jsonify(fetch_stock_data(symbol))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/watchlist")
def get_watchlist():
    return jsonify(db_load_watchlist())


@app.route("/watchlist/add", methods=["POST"])
def add_to_watchlist():
    data = request.json
    symbol = data.get("symbol", "").upper()
    if not symbol:
        return jsonify({"error": "Kein Symbol"}), 400
    db_upsert_watchlist_entry(symbol, data.get("name", symbol), data, str(date.today()), data)
    return jsonify({"ok": True})


@app.route("/watchlist/remove/<symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    # Watchlist + History
    db.table("watchlist_history").delete().eq("symbol", symbol).execute()
    db.table("analyst_estimates_history").delete().eq("symbol", symbol).execute()
    db.table("watchlist").delete().eq("symbol", symbol).execute()
    # Long-Portfolio
    db.table("portfolio_pos_history").delete().eq("symbol", symbol).execute()
    db.table("portfolio_positions").delete().eq("symbol", symbol).execute()
    # Short-Portfolio
    db.table("short_pos_history").delete().eq("symbol", symbol).execute()
    db.table("short_positions").delete().eq("symbol", symbol).execute()
    return jsonify({"ok": True})


@app.route("/watchlist/refresh")
def refresh_watchlist():
    wl = db_load_watchlist()
    today = str(date.today())
    errors = []
    for symbol in list(wl.keys()):
        try:
            result = fetch_stock_data(symbol)
            if "error" in result:
                errors.append(f"{symbol}: {result['error']}"); continue
            entry = {k: result.get(k) for k in
                     ["total_score", "kuv_score", "kgv_score", "tp_combined", "upside_pct"]}
            db_upsert_watchlist_entry(symbol, result.get("name", symbol), result, today, entry)
            fetch_and_save_estimates(symbol)
        except Exception as e:
            errors.append(f"{symbol}: {str(e)}")
    return jsonify({"ok": True, "errors": errors, "data": db_load_watchlist()})


@app.route("/estimates/<symbol>")
def get_estimates(symbol):
    try:
        data = db.table("analyst_estimates_history").select("*") \
            .eq("symbol", symbol).order("recorded_date").execute().data
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/portfolio")
def get_portfolio():
    try:
        return jsonify(db_load_portfolio())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/portfolio/refresh")
def refresh_portfolio():
    try:
        result = _refresh_portfolio_generic(
            score_threshold_fn=lambda s: s > 8,
            buy_key="buy_date",
            positions_table="portfolio_positions",
            history_table="portfolio_pos_history",
            summary_table="portfolio_history",
            short_mode=False,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/short-portfolio")
def get_short_portfolio():
    try:
        return jsonify(db_load_portfolio("short_positions", "short_pos_history", "short_portfolio_history"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/short-portfolio/refresh")
def refresh_short_portfolio():
    try:
        result = _refresh_portfolio_generic(
            score_threshold_fn=lambda s: s <= 2,
            buy_key="short_date",
            positions_table="short_positions",
            history_table="short_pos_history",
            summary_table="short_portfolio_history",
            short_mode=True,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/scan")
def scan():
    try:
        min_score = float(request.args.get("min", 0))
        max_score = float(request.args.get("max", 10))
    except ValueError:
        return jsonify({"error": "Ungültige Score-Werte"}), 400

    wl = db_load_watchlist()
    wl_symbols = set(wl.keys())
    available = [s for s in STOCK_UNIVERSE if s not in wl_symbols]
    to_scan = random.sample(available, min(SCAN_SAMPLE_SIZE, len(available)))

    results = []
    errors = []

    def scan_one(symbol):
        try:
            return symbol, fetch_stock_data(symbol)
        except Exception as e:
            return symbol, {"error": str(e)}

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(scan_one, sym): sym for sym in to_scan}
        for future in as_completed(futures):
            sym, data = future.result()
            if "error" in data:
                errors.append(f"{sym}: {data['error']}")
                continue
            score = data.get("total_score")
            if score is not None and min_score <= score <= max_score:
                results.append(data)

    results.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    return jsonify({"results": results, "scanned": len(to_scan), "errors": len(errors)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
