import os

# Environment variables
STAGE = os.getenv("STAGE", "dev").lower()
DOMAIN = os.getenv("DOMAIN_NAME", "bhaang.com").lower()

def _stage_suffix() -> str:
    """Return the stage-specific email suffix."""
    if STAGE in {"prod", "production", "prd"}:
        return ""
    return f".{STAGE}"

def to_local(full_email: str) -> str:
    """
    Convert full email to local part for database storage.
    Input: 'marketing@bhaang.com' or 'marketing.dev@bhaang.com'
    Output: 'marketing' (prod) or 'marketing.dev' (non-prod)
    """
    if not full_email:
        return ""
    
    local = full_email.split("@", 1)[0].lower().strip()
    suffix = _stage_suffix()
    
    # Ensure stage suffix is present exactly once
    if suffix and not local.endswith(suffix):
        local = f"{local}{suffix}"
    elif not suffix and local.endswith(tuple([f".{s}" for s in ("dev", "staging", "stage", STAGE)])):
        # Remove any non-prod suffix when stage is prod
        local = local.split(".")[0]
    
    return local

def to_full(local: str) -> str:
    """
    Convert local part back to full email address.
    Input: 'marketing' or 'marketing.dev'
    Output: 'marketing@bhaang.com' or 'marketing.dev@bhaang.com'
    """
    if not local:
        return ""
    return f"{local}@{DOMAIN}"

def validate_email_format(email: str) -> bool:
    """Basic email format validation."""
    import re
    return bool(re.match(r'^[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email)) 