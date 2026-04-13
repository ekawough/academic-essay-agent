import os
import httpx
import base64
import re
from typing import Optional

class OriginalityChecker:
    """
    Two-layer originality checking:
    1. Copyleaks API — plagiarism + AI detection (paid, best quality)
    2. Local heuristics — burstiness analysis + sentence variance (free)
    """

    def __init__(self):
        self.copyleaks_email = os.getenv("COPYLEAKS_EMAIL")
        self.copyleaks_key = os.getenv("COPYLEAKS_KEY")
        self.token = None
        self.use_copyleaks = bool(self.copyleaks_email and self.copyleaks_key)

    async def _authenticate_copyleaks(self):
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://id.copyleaks.com/v3/account/login/api",
                json={"email": self.copyleaks_email, "key": self.copyleaks_key}
            )
            if r.status_code == 200:
                self.token = r.json().get("access_token")

    async def check(self, text: str, essay_id: str) -> dict:
        """Run all available originality checks."""
        results = {}

        # Always run local analysis (free, instant)
        results["local_analysis"] = self._local_analysis(text)

        # Run Copyleaks if configured
        if self.use_copyleaks:
            try:
                copyleaks_result = await self._copyleaks_submit(text, essay_id)
                results["copyleaks"] = copyleaks_result
            except Exception as e:
                results["copyleaks"] = {"error": str(e), "status": "unavailable"}
        else:
            results["copyleaks"] = {
                "status": "not_configured",
                "note": "Set COPYLEAKS_EMAIL and COPYLEAKS_KEY in .env for plagiarism scanning"
            }

        # Compute overall score
        ai_prob = results["local_analysis"]["ai_probability_estimate"]
        results["overall"] = {
            "ai_content_risk": _risk_label(ai_prob),
            "ai_probability": ai_prob,
            "originality_estimate": round(1 - ai_prob, 2),
            "recommendation": _recommendation(ai_prob)
        }

        return results

    async def _copyleaks_submit(self, text: str, scan_id: str) -> dict:
        if not self.token:
            await self._authenticate_copyleaks()

        callback_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://your-app.railway.app")

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {
                "base64": base64.b64encode(text.encode()).decode(),
                "filename": f"{scan_id}.txt",
                "properties": {
                    "webhooks": {
                        "status": f"{callback_url}/check/webhook/{scan_id}"
                    },
                    "filters": {"minCopiedWords": 8},
                    "scanning": {"internet": True, "repositories": True}
                }
            }
            r = await client.put(
                f"https://api.copyleaks.com/v3/education/submit/file/{scan_id}",
                headers=headers,
                json=payload
            )
            return {"scan_id": scan_id, "status": "submitted", "copyleaks_status": r.status_code}

    def _local_analysis(self, text: str) -> dict:
        """
        Free local analysis:
        - Burstiness score (AI tends to write uniform sentence lengths)
        - Vocabulary richness
        - Sentence structure variance
        """
        # Sentence analysis
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]

        if not sentences:
            return {"error": "Text too short to analyze"}

        lengths = [len(s.split()) for s in sentences]
        n = len(lengths)
        avg = sum(lengths) / n
        variance = sum((l - avg) ** 2 for l in lengths) / n
        std_dev = variance ** 0.5

        # Burstiness: high variance = human-like, low variance = AI-like
        burstiness = std_dev / avg if avg > 0 else 0

        # Vocabulary richness (type-token ratio)
        words = text.lower().split()
        unique_words = len(set(words))
        ttr = unique_words / len(words) if words else 0

        # Repetition detection
        word_freq = {}
        for word in words:
            if len(word) > 5:
                word_freq[word] = word_freq.get(word, 0) + 1
        overused = {w: c for w, c in word_freq.items() if c > 5}

        # AI probability heuristic
        # Low burstiness + lower TTR = more likely AI
        burstiness_score = min(burstiness / 0.7, 1.0)  # normalize: 0.7 is typical human burstiness
        ttr_score = min(ttr / 0.6, 1.0)                # normalize: 0.6 is typical human TTR
        ai_probability = max(0, min(1, 1 - (burstiness_score * 0.6 + ttr_score * 0.4)))

        return {
            "ai_probability_estimate": round(ai_probability, 2),
            "burstiness": round(burstiness, 3),
            "vocabulary_richness": round(ttr, 3),
            "sentence_count": n,
            "avg_sentence_length": round(avg, 1),
            "overused_words": list(overused.keys())[:10],
            "note": "Local heuristic only. Use Copyleaks for certified plagiarism detection."
        }

def _risk_label(probability: float) -> str:
    if probability < 0.3:
        return "low"
    elif probability < 0.6:
        return "moderate"
    else:
        return "high"

def _recommendation(probability: float) -> str:
    if probability < 0.3:
        return "Content appears human-written. Good to submit."
    elif probability < 0.6:
        return "Moderate AI signals detected. Review and add personal voice before submitting."
    else:
        return "High AI content probability. Significant rewriting recommended."
