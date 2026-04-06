"""Google review scanner for outbound prospect enrichment.

Fetches Google reviews via SerpAPI, extracts dispatch-pain signals via LLM,
computes metadata signals and desperation scores, and persists enrichment
to Supabase via store.py.

Usage:
    python -m outbound.review_scanner --dry-run
    python -m outbound.review_scanner --states MI
    python -m outbound.review_scanner --phone "+15551234567"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests

from outbound.ingest import normalize_phone
from outbound.lsa_db import DEFAULT_DB, get_place_id, init_db, save_place_id
from outbound.llm import llm_completion
from outbound.constants import (
    DESPERATION_WEIGHTS,
    OUTBOUND_TENANT_ID,
    REVIEW_ENRICHMENT_CAP,
    REVIEW_SIGNAL_WEIGHTS,
)
from outbound import store

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"
MAX_REVIEW_TEXT_LEN = 500  # truncate individual reviews to limit prompt size
REQUEST_DELAY = 75  # seconds between requests (50/hr SerpAPI Starter limit)
MAX_RETRIES = 3
MAX_REVIEW_PAGES = 2
REVIEWS_PER_PAGE = 20

REVIEW_SIGNAL_TYPES = [
    "responsiveness_gap",
    "after_hours_gap",
    "owner_absent",
    "small_team_confirmed",
    "declining_quality",
]

OWNER_RESPONSE_STYLES = ["absent", "defensive", "template", "engaged"]

# ---------------------------------------------------------------------------
# SerpAPI: place ID lookup
# ---------------------------------------------------------------------------


def lookup_place_id(
    business_name: str, phone: str, town: str, state: str,
    conn: sqlite3.Connection | None = None,
) -> str | None:
    """Look up Google Maps data_id for a business via SerpAPI.

    Checks the local cache first. If not cached, queries SerpAPI google_maps
    engine and matches by phone number when multiple results return.
    """
    if conn is not None:
        cached = get_place_id(conn, phone)
        if cached:
            return cached

    if not SERPAPI_KEY:
        logger.error("lookup_place_id.no_api_key")
        return None

    query = f"{business_name} {town} {state}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(SERPAPI_URL, params={
                "engine": "google_maps",
                "q": query,
                "api_key": SERPAPI_KEY,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                logger.warning("lookup_place_id.api_error: %s — %s", business_name, data["error"])
                if conn is not None:
                    save_place_id(conn, phone, None, status="api_error")
                return None

            results = data.get("local_results", [])
            if not results:
                logger.info("lookup_place_id.no_results: %s", business_name)
                if conn is not None:
                    save_place_id(conn, phone, None, status="no_results")
                return None

            # Single result: use it
            if len(results) == 1:
                data_id = results[0].get("data_id")
                if conn is not None:
                    if data_id:
                        save_place_id(conn, phone, data_id)
                    else:
                        save_place_id(conn, phone, None, status="no_data_id")
                return data_id

            # Multiple results: match by phone
            normalized = normalize_phone(phone)
            for result in results:
                result_phone = normalize_phone(result.get("phone", ""))
                if result_phone and result_phone == normalized:
                    data_id = result.get("data_id")
                    if conn is not None and data_id:
                        save_place_id(conn, phone, data_id)
                    return data_id

            # No phone match: ambiguous
            logger.warning(
                "lookup_place_id.ambiguous: %s (%d results, no phone match)",
                business_name, len(results),
            )
            if conn is not None:
                save_place_id(conn, phone, None, status="ambiguous")
            return None

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                wait = REQUEST_DELAY * (attempt + 1)
                logger.warning("lookup_place_id.throttled: waiting %ds", wait)
                time.sleep(wait)
                continue
            logger.exception("lookup_place_id.http_error: %s", business_name)
            break
        except Exception:
            logger.exception("lookup_place_id.error: %s", business_name)
            break

    if conn is not None:
        save_place_id(conn, phone, None, status="error")
    return None


# ---------------------------------------------------------------------------
# SerpAPI: fetch reviews
# ---------------------------------------------------------------------------


def fetch_reviews(data_id: str, max_pages: int = MAX_REVIEW_PAGES) -> list[dict]:
    """Fetch Google reviews for a place via SerpAPI google_maps_reviews engine.

    Returns a list of review dicts with keys:
    text, rating, date, response_text, user_name.
    """
    all_reviews: list[dict] = []
    next_page_token: str | None = None

    for page in range(max_pages):
        params: dict[str, Any] = {
            "engine": "google_maps_reviews",
            "data_id": data_id,
            "api_key": SERPAPI_KEY,
            "sort_by": "newestFirst",
        }
        if next_page_token:
            params["next_page_token"] = next_page_token

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(SERPAPI_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    error_msg = data["error"]
                    if "out of searches" in error_msg.lower():
                        logger.error("fetch_reviews.out_of_credits")
                        return all_reviews
                    logger.warning("fetch_reviews.api_error: %s", error_msg)
                    return all_reviews

                reviews = data.get("reviews", [])
                for review in reviews:
                    all_reviews.append({
                        "text": review.get("snippet", ""),
                        "rating": review.get("rating"),
                        "date": review.get("date", ""),
                        "response_text": (review.get("response", {}) or {}).get("snippet", ""),
                        "user_name": review.get("user", {}).get("name", ""),
                    })

                next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
                break  # success, exit retry loop

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = REQUEST_DELAY * (attempt + 1)
                    logger.warning("fetch_reviews.throttled: waiting %ds", wait)
                    time.sleep(wait)
                    continue
                logger.exception("fetch_reviews.http_error")
                return all_reviews
            except Exception:
                logger.exception("fetch_reviews.error")
                return all_reviews

        if not next_page_token:
            break

        if page < max_pages - 1:
            time.sleep(REQUEST_DELAY)

    return all_reviews


# ---------------------------------------------------------------------------
# Metadata signals (no LLM)
# ---------------------------------------------------------------------------


def compute_metadata_signals(reviews: list[dict]) -> dict[str, Any]:
    """Compute review metadata signals from raw review data. No LLM needed."""
    if not reviews:
        return {"response_rate": 0.0, "trend_delta": 0.0, "review_count": 0}

    total = len(reviews)
    responded = sum(1 for r in reviews if r.get("response_text"))
    response_rate = responded / total if total > 0 else 0.0

    ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
    if len(ratings) >= 10:
        recent_avg = sum(ratings[:10]) / 10
        all_avg = sum(ratings) / len(ratings)
        trend_delta = recent_avg - all_avg
    else:
        trend_delta = 0.0

    return {
        "response_rate": round(response_rate, 2),
        "trend_delta": round(trend_delta, 2),
        "review_count": total,
    }


# ---------------------------------------------------------------------------
# LLM signal extraction
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You analyze Google reviews for HVAC businesses to extract signals indicating dispatch or responsiveness problems. Return valid JSON only."""

EXTRACTION_USER_TEMPLATE = """Analyze these Google reviews for {business_name}, an HVAC business in {town}, {state}.

Extract signals that indicate dispatch or responsiveness problems. For each signal found, provide:
- signal_type: one of [responsiveness_gap, after_hours_gap, owner_absent, small_team_confirmed, declining_quality]
- evidence: the exact quote or close paraphrase from the review (keep under 100 chars)
- confidence: high, medium, or low

Signal guidance:
- responsiveness_gap: slow callbacks, unreturned voicemails, missed appointments, long hold times, calls going to voicemail
- after_hours_gap: no evening/weekend coverage, "called after hours and got voicemail", no emergency line
- small_team_confirmed: mentions of scheduling tools like Housecall Pro or Jobber (confirms small team using software, not staff, to manage dispatch), "owner came himself", "one-man shop", "family business"
- owner_absent: owner disengaged, no review responses, generic responses
- declining_quality: recent reviews worse than older ones, growing pains, overextended

Also classify the business owner's review response pattern:
- owner_response_style: one of [absent, defensive, template, engaged]
  - absent: rarely or never responds to reviews
  - defensive: responds with excuses or blame
  - template: copy-paste generic "thank you" responses
  - engaged: thoughtful, personalized responses

And provide:
- overall_sentiment: positive, mixed, or negative
- top_complaint: the single most common complaint category (or "none")
- recommended_opener: a one-sentence cold call opener based on what you found. Must reference a specific finding. Under 150 chars. No emojis.

Return JSON in this exact format:
{{
  "signals": [{{"signal_type": "...", "evidence": "...", "confidence": "..."}}],
  "owner_response_style": "...",
  "overall_sentiment": "...",
  "top_complaint": "...",
  "recommended_opener": "..."
}}

Reviews ({review_count} total):
{formatted_reviews}"""


def _format_reviews_for_prompt(reviews: list[dict]) -> str:
    lines = []
    for i, r in enumerate(reviews, 1):
        stars = f"{r.get('rating', '?')} stars"
        text = (r.get("text") or "").strip()[:MAX_REVIEW_TEXT_LEN]
        response = (r.get("response_text") or "").strip()[:MAX_REVIEW_TEXT_LEN]
        line = f"[{i}] {stars} | {text}"
        if response:
            line += f"\n     Owner response: {response}"
        lines.append(line)
    return "\n".join(lines)


def extract_review_signals(
    reviews: list[dict],
    business_name: str,
    town: str,
    state: str,
) -> dict[str, Any] | None:
    """Extract typed dispatch-pain signals from reviews via LLM.

    Returns structured dict with signals, owner_response_style,
    overall_sentiment, top_complaint, and recommended_opener.
    Returns None if LLM call fails.
    """
    if not reviews:
        return None

    formatted = _format_reviews_for_prompt(reviews)
    user_prompt = EXTRACTION_USER_TEMPLATE.format(
        business_name=business_name,
        town=town,
        state=state,
        review_count=len(reviews),
        formatted_reviews=formatted,
    )

    result = llm_completion(
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0,
    )

    if result["status"] != "complete" or not result["text"]:
        logger.warning("extract_review_signals.llm_failed: %s", business_name)
        return None

    try:
        text = result["text"]
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        parsed = json.loads(text)

        # Validate signal types
        valid_signals = []
        for sig in parsed.get("signals", []):
            if sig.get("signal_type") in REVIEW_SIGNAL_TYPES:
                valid_signals.append(sig)
        parsed["signals"] = valid_signals

        # Validate owner response style
        if parsed.get("owner_response_style") not in OWNER_RESPONSE_STYLES:
            parsed["owner_response_style"] = "absent"

        # Sanitize opener: strip anything that looks like injected JSON/code
        opener = str(parsed.get("recommended_opener", "") or "")
        if "{" in opener or "```" in opener or len(opener) > 200:
            parsed["recommended_opener"] = ""

        return parsed
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.exception("extract_review_signals.parse_error: %s", business_name)
        return None


# ---------------------------------------------------------------------------
# Desperation score
# ---------------------------------------------------------------------------


def compute_desperation_score(
    llm_signals: list[dict] | None,
    metadata: dict[str, Any],
    owner_style: str,
) -> int:
    """Compute a 0-100 desperation score from review signals.

    Higher score = more likely to need CallLock (responsiveness problems,
    disengaged owner, declining quality).
    """
    score = 0

    # LLM-extracted signals
    if llm_signals:
        for sig in llm_signals:
            signal_type = sig.get("signal_type", "")
            confidence = sig.get("confidence", "low")
            weight = DESPERATION_WEIGHTS.get(signal_type, 0)
            if confidence == "high":
                score += weight
            elif confidence == "medium":
                score += weight // 2

    # Owner response style
    if owner_style == "absent":
        score += DESPERATION_WEIGHTS.get("owner_absent", 0)
    elif owner_style == "defensive":
        score += DESPERATION_WEIGHTS.get("owner_absent", 0) // 2

    # Metadata signals
    if metadata.get("response_rate", 1.0) < 0.3:
        score += DESPERATION_WEIGHTS.get("low_response_rate", 0)
    if metadata.get("trend_delta", 0.0) < -0.5:
        score += DESPERATION_WEIGHTS.get("negative_trend", 0)

    return min(score, 100)


# ---------------------------------------------------------------------------
# Review enrichment score (ICP delta)
# ---------------------------------------------------------------------------


def compute_review_enrichment_score(
    llm_signals: list[dict] | None,
    metadata: dict[str, Any],
) -> int:
    """Compute the ICP score delta from review signals. Capped at REVIEW_ENRICHMENT_CAP."""
    score = 0

    if llm_signals:
        seen_types: set[str] = set()
        for sig in llm_signals:
            signal_type = sig.get("signal_type", "")
            if signal_type not in seen_types:
                score += REVIEW_SIGNAL_WEIGHTS.get(signal_type, 0)
                seen_types.add(signal_type)

    if metadata.get("response_rate", 1.0) < 0.3:
        score += REVIEW_SIGNAL_WEIGHTS.get("low_response_rate", 0)
    if metadata.get("trend_delta", 0.0) < -0.5:
        score += REVIEW_SIGNAL_WEIGHTS.get("negative_trend", 0)

    return min(score, REVIEW_ENRICHMENT_CAP)


# ---------------------------------------------------------------------------
# Discord summary
# ---------------------------------------------------------------------------


def post_discord_summary(result: dict[str, Any], top_desperate: list[dict]) -> None:
    """Post enrichment scan summary to Discord via webhook."""
    webhook_url = os.getenv("DISCORD_OUTBOUND_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("review_scanner.no_webhook_url")
        return

    lines = [
        "**Review Scanner Complete**",
        f"Scanned: {result.get('scanned', 0)} | "
        f"Enriched: {result.get('enriched', 0)} | "
        f"Errors: {result.get('errors', 0)}",
        f"Skipped (no place ID): {result.get('skipped_no_place_id', 0)} | "
        f"Skipped (no reviews): {result.get('skipped_no_reviews', 0)}",
    ]

    if top_desperate:
        lines.append("")
        lines.append("**Top Desperate Prospects:**")
        for i, p in enumerate(top_desperate[:10], 1):
            signals = p.get("signal_summary", "no signals")
            lines.append(
                f"{i}. **{p['business_name']}** ({p['town']}, {p['state']}) "
                f"- desperation: {p['desperation_score']} | {signals}"
            )

    message = "\n".join(lines)
    if len(message) > 1900:
        message = message[:1900] + "\n... (truncated)"

    try:
        import httpx
        httpx.post(webhook_url, json={"content": message}, timeout=10.0)
    except Exception:
        logger.exception("review_scanner.discord_post_failed")


# ---------------------------------------------------------------------------
# Batch scan
# ---------------------------------------------------------------------------


def run_review_scan(
    *,
    source: str = "lsa",
    states: list[str] | None = None,
    dry_run: bool = False,
    phone: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run batch review scan on prospects from lsa_discovery.db.

    Returns dict with scan statistics.
    """
    conn = init_db()

    # Build query for sweet-spot prospects (10-100 reviews)
    query = (
        "SELECT business_name, phone, town, state, review_count, rating "
        "FROM lsa_businesses "
        "WHERE phone IS NOT NULL AND review_count BETWEEN 10 AND 100"
    )
    params: list[Any] = []

    if states:
        placeholders = ",".join("?" for _ in states)
        query += f" AND UPPER(state) IN ({placeholders})"
        params.extend(s.upper() for s in states)

    if phone:
        normalized = normalize_phone(phone)
        if normalized:
            query += " AND phone = ?"
            params.append(normalized)

    query += " ORDER BY review_count ASC"

    if limit:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query, params).fetchall()
    prospects = [dict(row) for row in rows]

    if dry_run:
        # Estimate credit usage
        place_lookups = len(prospects)
        review_fetches = len(prospects)  # page 1
        page2_estimates = sum(1 for p in prospects if (p.get("review_count") or 0) > 20)
        total_credits = place_lookups + review_fetches + page2_estimates

        print(f"\n  DRY RUN — Review Scanner")
        print(f"  Prospects to scan: {len(prospects)}")
        print(f"  Estimated credits: ~{total_credits}")
        print(f"    Place ID lookups: {place_lookups}")
        print(f"    Review page 1:   {review_fetches}")
        print(f"    Review page 2:   ~{page2_estimates}")
        if states:
            print(f"  States filter: {', '.join(states)}")
        if phone:
            print(f"  Phone filter: {phone}")
        print(f"\n  Sample prospects:")
        for p in prospects[:10]:
            print(f"    {p['business_name']} ({p['town']}, {p['state']}) "
                  f"— {p['review_count']} reviews, {p['rating']} stars")
        return {
            "scanned": 0, "enriched": 0, "skipped_no_place_id": 0,
            "skipped_no_reviews": 0, "errors": 0, "dry_run": True,
            "estimated_credits": total_credits, "prospect_count": len(prospects),
        }

    scanned = 0
    enriched = 0
    skipped_no_place_id = 0
    skipped_no_reviews = 0
    errors = 0
    top_desperate: list[dict] = []

    try:
        for i, prospect in enumerate(prospects):
            biz_name = prospect["business_name"]
            biz_phone = prospect["phone"]
            town = prospect["town"]
            state = prospect["state"]

            print(f"[{i+1}/{len(prospects)}] {biz_name} ({town}, {state})")
            scanned += 1

            # Step 1: Look up place ID (may hit cache, no API call)
            cached_before = get_place_id(conn, biz_phone) is not None
            data_id = lookup_place_id(biz_name, biz_phone, town, state, conn=conn)
            if not data_id:
                print(f"  -> skipped (no place ID)")
                skipped_no_place_id += 1
                if not cached_before and i < len(prospects) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            # Only sleep if we made an actual API call
            if not cached_before and i < len(prospects) - 1:
                time.sleep(REQUEST_DELAY)

            # Step 2: Fetch reviews
            reviews = fetch_reviews(data_id)
            if not reviews:
                print(f"  -> skipped (no reviews returned)")
                skipped_no_reviews += 1
                if i < len(prospects) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            print(f"  -> {len(reviews)} reviews fetched")

            # Step 3: Compute metadata signals
            metadata = compute_metadata_signals(reviews)

            # Step 4: Extract LLM signals
            llm_result = extract_review_signals(reviews, biz_name, town, state)
            llm_signals = llm_result.get("signals", []) if llm_result else []
            owner_style = (llm_result or {}).get("owner_response_style", "absent")
            opener = (llm_result or {}).get("recommended_opener", "")

            # Step 5: Compute scores
            desperation = compute_desperation_score(llm_signals, metadata, owner_style)
            enrichment_delta = compute_review_enrichment_score(llm_signals, metadata)

            signal_summary = ", ".join(
                f"{s['signal_type']}({s.get('confidence', '?')})"
                for s in llm_signals
            ) or "no dispatch signals"

            print(f"  -> signals: {signal_summary}")
            print(f"  -> desperation: {desperation} | enrichment: +{enrichment_delta}")
            if opener:
                print(f"  -> opener: {opener}")

            # Step 6: Persist enrichment
            try:
                enrichment_record = {
                    "tenant_id": OUTBOUND_TENANT_ID,
                    "phone_normalized": biz_phone,
                    "review_signals": llm_result,
                    "review_opener": (opener or "")[:150],
                    "review_enrichment_score": enrichment_delta,
                    "desperation_score": desperation,
                }
                store.enrich_prospect_reviews(biz_phone, enrichment_record)
                enriched += 1

                top_desperate.append({
                    "business_name": biz_name,
                    "town": town,
                    "state": state,
                    "desperation_score": desperation,
                    "signal_summary": signal_summary,
                })
            except Exception:
                logger.exception("review_scanner.store_error: %s", biz_name)
                errors += 1

            if i < len(prospects) - 1:
                time.sleep(REQUEST_DELAY)
    finally:
        conn.close()

    # Sort by desperation for Discord summary
    top_desperate.sort(key=lambda x: -x["desperation_score"])

    result = {
        "scanned": scanned,
        "enriched": enriched,
        "skipped_no_place_id": skipped_no_place_id,
        "skipped_no_reviews": skipped_no_reviews,
        "errors": errors,
    }

    # Post Discord summary
    if enriched > 0:
        post_discord_summary(result, top_desperate)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Review scanner for outbound enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Estimate credits without scanning")
    parser.add_argument("--states", nargs="+", help="Filter by state codes (e.g., MI FL TX)")
    parser.add_argument("--phone", help="Scan a single prospect by phone")
    parser.add_argument("--limit", type=int, help="Max prospects to scan")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    result = run_review_scan(
        dry_run=args.dry_run,
        states=args.states,
        phone=args.phone,
        limit=args.limit,
    )

    print(f"\n  RESULTS: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
