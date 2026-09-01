"""
GuardPay LLM Incident Dossier Generator — commit 8

Generates human-readable, explainable incident dossiers for flagged alerts.

Hard design constraints (docs/DESIGN.md):
  1. Explanation only: The LLM NEVER decides whether to flag or block.
     The deterministic velocity engine already flagged the anomaly.
  2. Latency-isolated: Dossiers are generated asynchronously or on-demand
     (lazily on GET /alerts/{id}/dossier), never on the critical transaction
     ingestion path.
  3. Cached: Once generated, dossiers are stored on the Alert object.
  4. Resilient: If CLAUDE_API_KEY is not configured or Anthropic API is
     unreachable, falls back to a deterministic domain synthesis template
     without crashing.
"""

import json
import logging
from typing import Any, Dict

from backend.alerts import Alert
from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministic Fallback Synthesis (Rule-based domain template)
# ---------------------------------------------------------------------------

def _synthesize_deterministic_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Generates a structured incident dossier deterministically when Claude API
    is not available or configured.
    """
    txn_count = len(alert.transaction_ids)
    # Estimate standard gateway processing fee (~200 paise per auth attempt)
    # plus estimated chargeback / fraud risk overhead (250 paise per attempt)
    estimated_damage = txn_count * 450

    # Determine confidence and root-cause narrative based on pattern
    if alert.pattern_type == "card_testing":
        root_cause = (
            f"Coordinated low-value authorization attempts consistent with card-testing, "
            f"probing card validity against BIN {alert.affected_bin} from subnet {alert.affected_subnet}."
        )
        blast_radius = (
            f"1 BIN ({alert.affected_bin}), 1 subnet ({alert.affected_subnet}), "
            f"{txn_count} transactions"
        )
        confidence = "high"
        summary = (
            f"An automated bot burst of {txn_count} micro-transactions was detected targeting "
            f"card BIN {alert.affected_bin} from subnet {alert.affected_subnet}. "
            f"Immediate subnet blocking or 3DS verification is recommended to prevent authorization fee accumulation."
        )
    elif alert.pattern_type == "bin_clustering":
        root_cause = (
            f"Multi-BIN card rotation attack originating from subnet {alert.affected_subnet}. "
            f"Automated tool cycled through {alert.affected_bin} to evade single-card velocity limits."
        )
        blast_radius = (
            f"Multiple BINs ({alert.affected_bin}), 1 subnet ({alert.affected_subnet}), "
            f"{txn_count} transactions"
        )
        confidence = "high"
        summary = (
            f"A coordinated bot farm from {alert.affected_subnet} attempted {txn_count} transactions "
            f"cycling across multiple card BINs ({alert.affected_bin}). "
            f"This pattern indicates automated credential or BIN stuffing."
        )
    elif alert.pattern_type == "subnet_clustering":
        root_cause = (
            f"Distributed transaction burst originating from hosting block {alert.affected_subnet} "
            f"with high source IP diversity."
        )
        blast_radius = (
            f"Subnet {alert.affected_subnet}, {txn_count} transactions across distributed IPs"
        )
        confidence = "medium"
        summary = (
            f"Detected {txn_count} transactions distributed across multiple IPs within {alert.affected_subnet}. "
            f"If this corresponds to an expected merchant marketing campaign, it may be overridden in the dashboard."
        )
    else:
        root_cause = f"Anomaly triggered by rule: {alert.rule_fired}."
        blast_radius = f"{txn_count} transactions, subnet {alert.affected_subnet}"
        confidence = alert.severity
        summary = f"Flagged {txn_count} suspicious transactions for merchant review."

    return {
        "alert_id": alert.alert_id,
        "root_cause": root_cause,
        "estimated_fee_damage_paise": estimated_damage,
        "blast_radius": blast_radius,
        "confidence": confidence,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(alert: Alert) -> str:
    txn_count = len(alert.transaction_ids)
    return f"""You are the AI Risk Manager for GuardPay, an AI fraud triage system for Razorpay merchants.
A deterministic velocity rule has flagged an anomaly. Your job is to synthesize an Incident Dossier explaining the event clearly to a non-technical merchant.

Alert Details:
- Alert ID: {alert.alert_id}
- Pattern Type: {alert.pattern_type}
- Severity: {alert.severity}
- Rule Fired: {alert.rule_fired}
- Affected Card BIN(s): {alert.affected_bin}
- Affected Subnet: {alert.affected_subnet}
- Total Flagged Transactions: {txn_count}
- Alert Created At: {alert.created_at.isoformat()}

Respond ONLY with a valid JSON object matching this schema:
{{
  "alert_id": "{alert.alert_id}",
  "root_cause": "<1-2 sentences technical summary of root cause>",
  "estimated_fee_damage_paise": <integer estimate of gateway fee damage in paise, approx {txn_count * 450}>,
  "blast_radius": "<concise scope e.g. '1 BIN, 1 subnet, {txn_count} transactions'>",
  "confidence": "<high|medium|low>",
  "summary": "<2-3 sentence plain-language explanation and recommendation for a merchant>"
}}"""


def _parse_llm_json(content_text: str, alert: Alert) -> Dict[str, Any]:
    """Strip markdown fences and parse JSON from an LLM response."""
    text = content_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    parsed = json.loads(text)
    parsed["alert_id"] = alert.alert_id
    parsed["estimated_fee_damage_paise"] = int(
        parsed.get("estimated_fee_damage_paise", len(alert.transaction_ids) * 450)
    )
    return parsed


# ---------------------------------------------------------------------------
# LLM Generation — Provider 1: Anthropic Claude
# ---------------------------------------------------------------------------

def _generate_claude_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Calls Anthropic Claude API to generate an explainable incident dossier.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.claude_api_key)
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=600,
        temperature=0.2,
        messages=[{"role": "user", "content": _build_prompt(alert)}],
    )
    return _parse_llm_json(response.content[0].text, alert)


# ---------------------------------------------------------------------------
# LLM Generation — Provider 2: NVIDIA NIM (OpenAI-compatible API)
# ---------------------------------------------------------------------------

def _generate_nvidia_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Calls NVIDIA NIM's OpenAI-compatible endpoint to generate a dossier.
    Get a free API key at https://build.nvidia.com/
    """
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
    )
    response = client.chat.completions.create(
        model=settings.nvidia_model,
        max_tokens=600,
        temperature=0.2,
        messages=[{"role": "user", "content": _build_prompt(alert)}],
    )
    return _parse_llm_json(response.choices[0].message.content, alert)


# ---------------------------------------------------------------------------
# LLM Generation — Provider 3: Cloud Ollama / Remote LLM (with API key & custom URL)
# ---------------------------------------------------------------------------

def _generate_ollama_cloud_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Calls a cloud-hosted Ollama, OpenWebUI, or remote OpenAI-compatible endpoint with an API key.
    Configure OLLAMA_CLOUD_BASE_URL, OLLAMA_CLOUD_API_KEY, and OLLAMA_CLOUD_MODEL in .env.
    """
    import httpx

    base_url = settings.ollama_cloud_base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.ollama_cloud_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_cloud_api_key}"

    # Try Ollama native /api/chat endpoint first (if base_url is not specifically /v1)
    if not base_url.endswith("/v1"):
        try:
            payload = {
                "model": settings.ollama_cloud_model,
                "messages": [{"role": "user", "content": _build_prompt(alert)}],
                "stream": False,
            }
            resp = httpx.post(f"{base_url}/api/chat", json=payload, headers=headers, timeout=60.0)
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "")
                if content:
                    return _parse_llm_json(content, alert)
        except Exception:
            pass  # Try OpenAI-compatible endpoint fallback below

    # OpenAI-compatible /v1/chat/completions endpoint fallback
    openai_url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    payload = {
        "model": settings.ollama_cloud_model,
        "messages": [{"role": "user", "content": _build_prompt(alert)}],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    resp = httpx.post(openai_url, json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_llm_json(content, alert)


# ---------------------------------------------------------------------------
# LLM Generation — Provider 4: Local Ollama (localhost)
# ---------------------------------------------------------------------------

def _generate_ollama_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Calls a local Ollama instance via its REST API.
    Configure OLLAMA_BASE_URL and OLLAMA_MODEL in .env.
    Default: http://localhost:11434 with model llama3.
    """
    import httpx

    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": _build_prompt(alert)}],
        "stream": False,
    }
    resp = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]
    return _parse_llm_json(content, alert)


# ---------------------------------------------------------------------------
# Public Dossier Generator — auto-fallback chain
# ---------------------------------------------------------------------------

def generate_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Generates and returns an incident dossier for the given alert.
    If already generated, returns the cached version.

    Provider priority (first available & successful wins):
      1. Anthropic Claude      — if CLAUDE_API_KEY is configured
      2. NVIDIA NIM            — if NVIDIA_API_KEY is configured
      3. Cloud Ollama / Remote — if OLLAMA_CLOUD_BASE_URL is configured
      4. Local Ollama          — attempted on OLLAMA_BASE_URL (default http://localhost:11434)
      5. Deterministic         — rule-based domain template, always available
    """
    if alert.dossier:
        return alert.dossier

    dossier: Dict[str, Any]

    # Build the ordered list of providers to try
    providers = []

    claude_key = (settings.claude_api_key or "").strip()
    if claude_key and not claude_key.startswith("sk-ant-YOUR"):
        providers.append(("Claude", _generate_claude_dossier))

    nvidia_key = (settings.nvidia_api_key or "").strip()
    if nvidia_key and not nvidia_key.startswith("nvapi-YOUR"):
        providers.append(("NVIDIA NIM", _generate_nvidia_dossier))

    cloud_ollama_url = (settings.ollama_cloud_base_url or "").strip()
    if cloud_ollama_url and not cloud_ollama_url.startswith("YOUR_"):
        providers.append(("Cloud Ollama", _generate_ollama_cloud_dossier))

    # Local Ollama is always included in the attempt chain
    providers.append(("Local Ollama", _generate_ollama_dossier))

    for provider_name, generator in providers:
        try:
            logger.info("Calling %s to generate dossier for %s", provider_name, alert.alert_id)
            dossier = generator(alert)
            logger.info("%s dossier generation succeeded for %s", provider_name, alert.alert_id)
            alert.dossier = dossier
            return dossier
        except Exception as exc:
            logger.warning(
                "%s dossier generation failed: %s — trying next provider", provider_name, exc
            )

    logger.info("All LLM providers failed; using deterministic fallback for %s", alert.alert_id)
    dossier = _synthesize_deterministic_dossier(alert)
    alert.dossier = dossier
    return dossier

