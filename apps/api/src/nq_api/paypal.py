"""PayPal Subscriptions API client.

Creates subscription links and verifies webhook signatures.
Requires PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET env vars.
"""
import base64
import logging
import os
import time
import httpx

log = logging.getLogger(__name__)

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE_URL = (
    "https://api-m.paypal.com"
    if os.environ.get("PAYPAL_LIVE") == "true"
    else "https://api-m.sandbox.paypal.com"
)

# Cache access token
_token_cache: dict = {"token": "", "expires": 0}


def _get_access_token() -> str:
    """Fetch OAuth2 access token from PayPal."""
    if _token_cache["token"] and _token_cache["expires"] > time.time() + 60:
        return _token_cache["token"]

    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

    creds = base64.b64encode(
        f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()
    ).decode()

    resp = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        headers={"Authorization": f"Basic {creds}"},
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["token"]


def create_subscription_link(
    plan_id: str,
    user_id: str,
    user_email: str,
    tier: str,
) -> str:
    """Create a PayPal subscription and return the approval URL.

    Returns the HATEOAS link the user clicks to authorize payment.
    """
    token = _get_access_token()

    resp = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/billing/subscriptions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "plan_id": plan_id,
            "subscriber": {"email_address": user_email},
            "metadata": {"user_id": user_id, "tier": tier},
            "application_context": {
                "brand_name": "NeuralQuant",
                "return_url": os.environ.get(
                    "PAYPAL_RETURN_URL",
                    "https://neuralquant.co/dashboard?upgraded=1",
                ),
                "cancel_url": os.environ.get(
                    "PAYPAL_CANCEL_URL",
                    "https://neuralquant.co/pricing",
                ),
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract approval link from HATEOAS links
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return link["href"]

    raise ValueError("No approval link found in PayPal subscription response")


def verify_webhook_signature(
    headers: dict,
    body: bytes,
) -> bool:
    """Verify PayPal webhook signature.

    In production, you should verify the signature using PayPal's webhook
    verification API. For now, we do a basic check that required headers exist.
    Full verification requires PAYPAL_WEBHOOK_ID.
    """
    webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID", "")
    if not webhook_id:
        if os.environ.get("ENVIRONMENT") == "development":
            log.warning("PAYPAL_WEBHOOK_ID not set — allowing webhook in development")
            return True
        log.error("PAYPAL_WEBHOOK_ID not set in production — rejecting webhook")
        return False

    token = _get_access_token()

    # Build verification payload per PayPal spec
    import json

    transmission_id = headers.get("paypal-transmission-id", "")
    transmission_time = headers.get("paypal-transmission-time", "")
    cert_url = headers.get("paypal-cert-url", "")
    auth_algo = headers.get("paypal-auth-algo", "SHA256withRSA")
    signature = headers.get("paypal-transmission-sig", "")

    resp = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": signature,
            "webhook_id": webhook_id,
            "webhook_event": json.loads(body),
        },
        timeout=30,
    )

    if resp.status_code != 200:
        log.error("PayPal webhook verification failed: %s", resp.text[:200])
        return False

    result = resp.json()
    return result.get("verification_status") == "SUCCESS"


def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a PayPal subscription."""
    token = _get_access_token()

    resp = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/billing/subscriptions/{subscription_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"reason": "Cancelled by user"},
        timeout=30,
    )
    return resp.status_code == 204