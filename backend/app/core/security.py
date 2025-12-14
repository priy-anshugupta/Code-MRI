import re

def redact_secrets(text: str) -> str:
    """
    Redacts sensitive information from the text using Regex.
    Targeting: OpenAI keys, Stripe keys, and Generic High-Entropy assignments.
    """
    if not text:
        return ""

    redacted = text

    # 1. OpenAI Keys (sk-...)
    # Matches sk- followed by 48+ alphanumeric chars
    openai_pattern = r"(sk-[a-zA-Z0-9]{48,})|(sk-proj-[a-zA-Z0-9-]{20,})"
    redacted = re.sub(openai_pattern, "[REDACTED_OPENAI_KEY]", redacted)

    # 2. Stripe Keys (sk_live_, rk_live_)
    stripe_pattern = r"(sk_live_[0-9a-zA-Z]{24,})|(rk_live_[0-9a-zA-Z]{24,})"
    redacted = re.sub(stripe_pattern, "[REDACTED_STRIPE_KEY]", redacted)

    # 3. Generic "api_key = 'xyz'" patterns
    # Look for identifiers like api_key, secret, token followed by assignment
    # This is conservative to avoid false positives in code logic
    # Group 1: key + assignment + quote
    # Group 2: secret value
    # Group 3: quote
    generic_assignment_pattern = re.compile(
        r"((?:api_?key|secret|token|password|passwd)\s*=\s*['\"])([\w-]{16,})(['\"])", 
        re.IGNORECASE
    )
    
    def generic_replacement(match):
        prefix = match.group(1)
        # value = match.group(2) 
        quote = match.group(3)
        return f"{prefix}[REDACTED_SECRET]{quote}"

    redacted = generic_assignment_pattern.sub(generic_replacement, redacted)

    return redacted
