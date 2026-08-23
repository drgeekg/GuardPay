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
# LLM Generation via Anthropic Claude API
# ---------------------------------------------------------------------------

def _generate_claude_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Calls Anthropic Claude API to generate an explainable incident dossier.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.claude_api_key)

    txn_count = len(alert.transaction_ids)
    prompt = f"""You are the AI Risk Manager for GuardPay, an AI fraud triage system for Razorpay merchants.
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

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=600,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    content_text = response.content[0].text.strip()
    # Strip markdown fences if present
    if content_text.startswith("```json"):
        content_text = content_text[7:]
    if content_text.startswith("```"):
        content_text = content_text[3:]
    if content_text.endswith("```"):
        content_text = content_text[:-3]
    content_text = content_text.strip()

    parsed = json.loads(content_text)
    # Ensure all required fields exist
    parsed["alert_id"] = alert.alert_id
    parsed["estimated_fee_damage_paise"] = int(parsed.get("estimated_fee_damage_paise", txn_count * 450))
    return parsed


# ---------------------------------------------------------------------------
# Public Dossier Generator
# ---------------------------------------------------------------------------

def generate_dossier(alert: Alert) -> Dict[str, Any]:
    """
    Generates and returns an incident dossier for the given alert.
    If already generated, returns the cached version.
    """
    if alert.dossier:
        return alert.dossier

    dossier: Dict[str, Any]

    # Check if a real Anthropic key is configured
    key = settings.claude_api_key.strip() if settings.claude_api_key else ""
    if key and not key.startswith("sk-ant-YOUR"):
        try:
            logger.info("Calling Claude API to generate dossier for %s", alert.alert_id)
            dossier = _generate_claude_dossier(alert)
        except Exception as exc:
            logger.warning("Claude API dossier generation failed: %s; using deterministic fallback", exc)
            dossier = _synthesize_deterministic_dossier(alert)
    else:
        dossier = _synthesize_deterministic_dossier(alert)

    alert.dossier = dossier
    return dossier
