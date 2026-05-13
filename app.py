from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import json
import os
from datetime import date

app = Flask(__name__)
WATCHLIST_FILE = "watchlist.json"


# ── Persistenz ────────────────────────────────────────────────────────────────

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_watchlist(data):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def safe_float(df, row, col):
    try:
        v = df.loc[row, col]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None


def get_5y_growth(growth_est):
    try:
        row = growth_est.loc["+5y"]
        v = row.dropna().iloc[0]
        return float(v)
    except Exception:
        return None


def fmt(value):
    if value >= 1e12:
        return f"{value / 1e12:.2f} Bio."
    elif value >= 1e9:
        return f"{value / 1e9:.2f} Mrd."
    elif value >= 1e6:
        return f"{value / 1e6:.2f} Mio."
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


def combined_rating(kuv_score, kgv_score):
    score = round(0.4 * kuv_score + 0.6 * kgv_score, 2)
    if score >= 8.5:   label = "Stark unterbewertet"
    elif score >= 7.0: label = "Attraktiv bewertet"
    elif score >= 5.5: label = "Fair bewertet"
    elif score >= 3.5: label = "Leicht überbewertet"
    else:              label = "Stark überbewertet"
    return score, label


# ── Kursziel-Berechnung ───────────────────────────────────────────────────────

def effective_kgv(raw_kgv):
    """Realistisches KGV für Projektion: hohe Multiples werden normalisiert."""
    if raw_kgv <= 40:
        return raw_kgv, None
    elif raw_kgv <= 60:
        eff = raw_kgv * 0.80
        return eff, f"KGV {raw_kgv:.0f}× → auf {eff:.0f}× reduziert (leichte Normalisierung)"
    elif raw_kgv <= 100:
        eff = raw_kgv * 0.60
        return eff, f"KGV {raw_kgv:.0f}× → auf {eff:.0f}× reduziert (Multiple-Compression erwartet)"
    else:
        return 40.0, f"KGV {raw_kgv:.0f}× → auf 40× normalisiert (extreme Bewertung, starke Compression)"


def calculate_target_price(market_cap, shares, price_raw,
                            current_revenue, net_income,
                            rev_2029, earnings_2029, currency):
    out = {}
    if not shares or not price_raw:
        return out

    # ── KGV-Methode ──────────────────────────────────────────────────────────
    if net_income and net_income > 0 and earnings_2029:
        raw_kgv = market_cap / net_income
        eff, note = effective_kgv(raw_kgv)
        target_mc = eff * earnings_2029
        tp_kgv = target_mc / shares
        out["tp_kgv"] = round(tp_kgv, 2)
        out["current_kgv_real"] = round(raw_kgv, 1)
        out["eff_kgv"] = round(eff, 1)
        out["kgv_note"] = note
    elif earnings_2029 and earnings_2029 > 0 and (not net_income or net_income <= 0):
        # Heute Verlust, aber 2029 profitabel: konservatives KGV von 30 annehmen
        eff = 30.0
        tp_kgv = (eff * earnings_2029) / shares
        out["tp_kgv"] = round(tp_kgv, 2)
        out["current_kgv_real"] = None
        out["eff_kgv"] = eff
        out["kgv_note"] = "Kein aktueller Gewinn – KGV 30× für 2029 angenommen (konservativ)"
    elif earnings_2029 and earnings_2029 <= 0:
        out["kgv_note"] = "Verlust in 2029 erwartet – KGV-Kursziel nicht berechenbar"

    # ── KUV-Methode ──────────────────────────────────────────────────────────
    if current_revenue and current_revenue > 0 and rev_2029:
        kuv_real = market_cap / current_revenue
        tp_kuv = (kuv_real * rev_2029) / shares
        out["tp_kuv"] = round(tp_kuv, 2)
        out["current_kuv_real"] = round(kuv_real, 2)

    # ── Kombiniertes Kursziel ─────────────────────────────────────────────────
    has_kgv = "tp_kgv" in out
    has_kuv = "tp_kuv" in out

    if has_kgv and has_kuv:
        combined = 0.4 * out["tp_kuv"] + 0.6 * out["tp_kgv"]
    elif has_kgv:
        combined = out["tp_kgv"]
    elif has_kuv:
        combined = out["tp_kuv"]
    else:
        return out

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
        return {"error": "Marktkapitalisierung nicht verfügbar – Ticker prüfen"}

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

    kuv_score, kuv_label = (None, None)
    kgv_score, kgv_label = (None, None)
    total_score, total_label = (None, None)

    if kuv_2029 is not None:
        kuv_score, kuv_label = score_kuv(kuv_2029)
        kuv_score = round(kuv_score, 2)
    if kgv_2029 is not None:
        kgv_score, kgv_label = score_kgv(kgv_2029)
        kgv_score = round(kgv_score, 2)
    if kuv_score is not None and kgv_score is not None:
        total_score, total_label = combined_rating(kuv_score, kgv_score)

    # Kursziel berechnen
    target = calculate_target_price(
        market_cap, shares, price_raw,
        current_revenue, net_income,
        rev_2029, earnings_2029, currency
    )

    return {
        "name": name,
        "symbol": symbol,
        "market_cap": fmt(market_cap),
        "price": f"{price_raw:.2f} {currency}" if price_raw else "—",
        "price_raw": price_raw,
        "growth": f"{growth_5y * 100:.1f}",
        "rev_2029": fmt(rev_2029) if rev_2029 else None,
        "kuv_2029": f"{kuv_2029:.2f}" if kuv_2029 else None,
        "kuv_score": kuv_score,
        "kuv_label": kuv_label,
        "earnings_2029": fmt(earnings_2029) if earnings_2029 else None,
        "kgv_2029": f"{kgv_2029:.1f}" if kgv_2029 else None,
        "kgv_score": kgv_score,
        "kgv_label": kgv_label,
        "total_score": total_score,
        "total_label": total_label,
        **target,
    }


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
    return jsonify(load_watchlist())


@app.route("/watchlist/add", methods=["POST"])
def add_to_watchlist():
    data = request.json
    symbol = data.get("symbol", "").upper()
    if not symbol:
        return jsonify({"error": "Kein Symbol"}), 400

    watchlist = load_watchlist()
    today = str(date.today())

    if symbol not in watchlist:
        watchlist[symbol] = {"name": data.get("name", symbol), "history": []}

    entry = {
        "date": today,
        "total_score": data.get("total_score"),
        "kuv_score": data.get("kuv_score"),
        "kgv_score": data.get("kgv_score"),
        "tp_combined": data.get("tp_combined"),
        "upside_pct": data.get("upside_pct"),
    }

    history = watchlist[symbol]["history"]
    idx = next((i for i, h in enumerate(history) if h["date"] == today), None)
    if idx is not None:
        history[idx] = entry
    else:
        history.append(entry)

    watchlist[symbol]["name"] = data.get("name", symbol)
    watchlist[symbol]["latest"] = data
    save_watchlist(watchlist)
    return jsonify({"ok": True})


@app.route("/watchlist/remove/<symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    watchlist = load_watchlist()
    if symbol in watchlist:
        del watchlist[symbol]
        save_watchlist(watchlist)
    return jsonify({"ok": True})


@app.route("/watchlist/refresh")
def refresh_watchlist():
    watchlist = load_watchlist()
    today = str(date.today())
    errors = []

    for symbol in list(watchlist.keys()):
        try:
            result = fetch_stock_data(symbol)
            if "error" in result:
                errors.append(f"{symbol}: {result['error']}")
                continue

            entry = {
                "date": today,
                "total_score": result.get("total_score"),
                "kuv_score": result.get("kuv_score"),
                "kgv_score": result.get("kgv_score"),
                "tp_combined": result.get("tp_combined"),
                "upside_pct": result.get("upside_pct"),
            }

            history = watchlist[symbol]["history"]
            idx = next((i for i, h in enumerate(history) if h["date"] == today), None)
            if idx is not None:
                history[idx] = entry
            else:
                history.append(entry)

            watchlist[symbol]["name"] = result.get("name", symbol)
            watchlist[symbol]["latest"] = result

        except Exception as e:
            errors.append(f"{symbol}: {str(e)}")

    save_watchlist(watchlist)
    return jsonify({"ok": True, "errors": errors, "data": watchlist})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
