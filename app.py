import os
from datetime import datetime, timedelta

import yfinance as yf
from dotenv import load_dotenv
from flask import Flask, flash, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

GPT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MARKET_SYMBOLS = [
    ("^GSPC", "S&P 500"),
    ("VTI", "Total US Stock Market"),
    ("BND", "Total US Bond Market"),
]


def parse_float(form, field_name, label):
    """Convert a form input to float, raising ValueError with a helpful message."""
    raw_value = (form.get(field_name) or "").replace(",", "").strip()
    if raw_value == "":
        raise ValueError(f"{label} is required.")

    try:
        return float(raw_value)
    except ValueError as exc:  # pragma: no cover - UI level validation only
        raise ValueError(f"{label} must be a number.") from exc


def build_user_profile(form):
    """Build the user profile dict from submitted form data."""
    name = (form.get("name") or "").strip() or "User"
    current_age = parse_float(form, "current_age", "Current age")
    target_age = parse_float(form, "target_age", "Target age")
    income = parse_float(form, "income", "Annual after-tax income")
    total_debt = parse_float(form, "total_debt", "Total debt")
    avg_debt_rate = parse_float(form, "avg_debt_rate", "Average debt interest rate")
    assets = parse_float(form, "assets", "Total financial assets")
    monthly_savings = parse_float(form, "monthly_savings", "Monthly savings")

    risk = (form.get("risk") or "moderate").lower()
    if risk not in {"conservative", "moderate", "aggressive"}:
        raise ValueError("Please choose a valid risk appetite option.")

    years_to_goal = max(target_age - current_age, 0)
    net_worth = assets - total_debt
    yearly_savings = monthly_savings * 12
    debt_to_income = (total_debt / income) if income > 0 else None

    growth_rate = {"conservative": 0.03, "moderate": 0.06, "aggressive": 0.08}[risk]

    # Highly simplified compounding assumption
    projected_net_worth = net_worth
    for _ in range(int(years_to_goal)):
        projected_net_worth = (projected_net_worth + yearly_savings) * (1 + growth_rate)

    return {
        "name": name,
        "current_age": current_age,
        "target_age": target_age,
        "years_to_goal": years_to_goal,
        "annual_income": income,
        "total_debt": total_debt,
        "avg_debt_rate_percent": avg_debt_rate,
        "total_assets": assets,
        "monthly_savings": monthly_savings,
        "yearly_savings": yearly_savings,
        "net_worth": net_worth,
        "risk_appetite": risk,
        "growth_rate_assumed": growth_rate,
        "projected_net_worth_at_goal": projected_net_worth,
        "debt_to_income_ratio": debt_to_income,
    }


def fetch_market_snapshot():
    """Fetch a snapshot of a few common market proxies."""
    end = datetime.today()
    start = end - timedelta(days=90)

    snapshot = {}
    for symbol, label in MARKET_SYMBOLS:
        try:
            history = yf.download(symbol, start=start, end=end, progress=False)
            if history.empty:
                snapshot[symbol] = {
                    "label": label,
                    "error": "No data returned for this period.",
                }
                continue

            first_close = history["Close"].iloc[0]
            last_close = history["Close"].iloc[-1]
            pct_change = (last_close - first_close) / first_close * 100.0

            snapshot[symbol] = {
                "label": label,
                "start_date": history.index[0].strftime("%Y-%m-%d"),
                "end_date": history.index[-1].strftime("%Y-%m-%d"),
                "start_price": float(first_close),
                "end_price": float(last_close),
                "pct_change_90d": float(pct_change),
            }
        except Exception as exc:  # pragma: no cover - network error path
            snapshot[symbol] = {"label": label, "error": str(exc)}

    return snapshot


def summarize_for_model(profile, market_data):
    """Create a human-readable summary that will be sent to GPT."""
    lines = [
        "USER FINANCIAL PROFILE:",
        f"- Name: {profile['name']}",
        f"- Current age: {profile['current_age']}",
        f"- Target retirement age: {profile['target_age']}",
        f"- Years until goal: {profile['years_to_goal']:.1f}",
        f"- Annual after-tax income: ${profile['annual_income']:,.2f}",
        f"- Total debt: ${profile['total_debt']:,.2f}",
        f"- Average debt interest rate: {profile['avg_debt_rate_percent']:.2f}%",
        f"- Total assets: ${profile['total_assets']:,.2f}",
        f"- Monthly savings: ${profile['monthly_savings']:,.2f}",
        f"- Yearly savings: ${profile['yearly_savings']:,.2f}",
        f"- Net worth (assets - debt): ${profile['net_worth']:,.2f}",
    ]

    if profile["debt_to_income_ratio"] is not None:
        lines.append(
            f"- Debt-to-income ratio: {profile['debt_to_income_ratio']:.2f} "
            "(total debt / annual income)"
        )
    else:
        lines.append("- Debt-to-income ratio: N/A (income is zero or not provided)")

    lines.extend(
        [
            f"- Risk appetite: {profile['risk_appetite']}",
            f"- Simple assumed growth rate based on risk: {profile['growth_rate_assumed']*100:.2f}%",
            f"- Rough projected net worth at target age: ${profile['projected_net_worth_at_goal']:,.2f}",
            "",
            "MARKET SNAPSHOT (last ~90 days):",
        ]
    )

    for symbol, info in market_data.items():
        label = info.get("label", symbol)
        if "error" in info:
            lines.append(f"- {label} ({symbol}): error fetching data: {info['error']}")
        else:
            lines.append(
                f"- {label} ({symbol}): {info['start_date']} close=${info['start_price']:.2f}, "
                f"{info['end_date']} close=${info['end_price']:.2f}, "
                f"{info['pct_change_90d']:.2f}% change over 90 days"
            )

    return "\n".join(lines)


def call_gpt(user_summary):
    """Send the summarized context to GPT and return the plain text reply."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file before running the app."
        )

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a cautious but helpful personal finance educator (NOT an advisor). "
        "You explain concepts in simple language. You must not provide personalized "
        "financial advice, but you can offer educational scenarios, tradeoffs, and "
        "example asset allocations. Always include clear disclaimers."
    )

    user_prompt = f"""
Here is structured information about a user's finances and a tiny market snapshot.

{user_summary}

TASK:
1. Briefly restate the user's situation and time horizon.
2. Comment at a high level on the market snapshot (ONLY educational, no predictions).
3. Provide 2–3 educational retirement investing scenarios appropriate to their time horizon
   and risk appetite. For each scenario, include a sample asset mix, pros/cons, and the type
   of person it generally fits.
4. Give 3–5 simple, practical habits they could focus on: savings rate, debt payoff,
   diversification, emergency fund, etc.
5. End with a bold-looking disclaimer (ALL CAPS) stating this is not financial, legal,
   or tax advice and that they should consider a licensed professional.

IMPORTANT:
- Do NOT recommend specific tickers or products.
- Speak in plain English and keep it friendly and encouraging.
- Make it clear that markets are uncertain and past performance does not guarantee future results.
"""

    response = client.responses.create(
        model=GPT_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    try:
        return response.output[0].content[0].text
    except Exception:  # pragma: no cover - defensive fallback
        return str(response)


def format_currency(value):
    """Helper exposed to templates for consistent currency formatting."""
    return f"${value:,.2f}"


@app.context_processor
def inject_helpers():
    return {"format_currency": format_currency}


@app.route("/", methods=["GET", "POST"])
def index():
    profile = None
    market_data = None
    summary = None
    gpt_text = None
    gpt_error = None
    form_values = request.form.to_dict() if request.method == "POST" else {}

    if request.method == "POST":
        try:
            profile = build_user_profile(request.form)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            market_data = fetch_market_snapshot()
            summary = summarize_for_model(profile, market_data)
            try:
                gpt_text = call_gpt(summary)
            except Exception as exc:  # pragma: no cover - network errors
                gpt_error = str(exc)
                flash(
                    "The OpenAI request failed. Check your API key, quota, or logs for details.",
                    "error",
                )
                app.logger.exception("OpenAI API error: %s", exc)

    return render_template(
        "index.html",
        form_values=form_values,
        profile=profile,
        market_data=market_data,
        summary=summary,
        gpt_text=gpt_text,
        gpt_error=gpt_error,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        debug=False
    )
