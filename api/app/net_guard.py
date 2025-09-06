"""
Network Egress Guard - Blocks outbound HTTP calls to non-local hosts.

This module monkey-patches the requests library to prevent any outbound
HTTP calls unless explicitly allowed. This ensures compliance with the
local-only requirement for the hackathon.
"""

import logging
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from requests.sessions import Session

from .config import settings

logger = logging.getLogger(__name__)


class EgressBlockedError(Exception):
    """Raised when an outbound HTTP call is blocked."""
    pass


def is_local_host(hostname: str) -> bool:
    """
    Check if a hostname is local (localhost, 127.0.0.1, or Docker service names).
    
    Args:
        hostname: The hostname to check
        
    Returns:
        True if the hostname is considered local
    """
    if not hostname:
        return False
    
    # Check against allowed domains from settings
    if hostname.lower() in [domain.lower() for domain in settings.allowed_domains]:
        return True
    
    # Check for localhost variants
    localhost_variants = [
        'localhost',
        '127.0.0.1',
        '::1',
        '0.0.0.0'
    ]
    
    if hostname.lower() in localhost_variants:
        return True
    
    # Check for Docker service names (no dots, typical service names)
    if '.' not in hostname and hostname.islower():
        # This is likely a Docker service name
        return True
    
    # Check if it's a private IP address
    try:
        ip = socket.gethostbyname(hostname)
        # Check for private IP ranges
        if ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('172.'):
            return True
    except socket.gaierror:
        # If we can't resolve, be conservative and block
        pass
    
    return False


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate if a URL is allowed for outbound requests.
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_allowed, reason)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False, "No hostname in URL"
        
        if is_local_host(hostname):
            return True, f"Local hostname: {hostname}"
        
        return False, f"Non-local hostname: {hostname}"
        
    except Exception as e:
        return False, f"URL parsing error: {str(e)}"


class EgressGuardAdapter(HTTPAdapter):
    """
    Custom HTTPAdapter that blocks outbound requests.
    """
    
    def send(self, request, **kwargs):
        """Override send to check URL before making request."""
        if not settings.allow_egress:
            is_allowed, reason = validate_url(request.url)
            if not is_allowed:
                logger.warning(
                    f"Blocked outbound HTTP request to {request.url}: {reason}",
                    extra={
                        "url": request.url,
                        "method": request.method,
                        "reason": reason
                    }
                )
                raise EgressBlockedError(
                    f"Outbound HTTP request blocked: {reason}. "
                    f"URL: {request.url}. "
                    f"Set ALLOW_EGRESS=true to allow (not recommended for production)."
                )
        
        return super().send(request, **kwargs)


def install_egress_guard():
    """
    Install the egress guard by monkey-patching requests.
    
    This function should be called early in the application lifecycle,
    before any HTTP requests are made.
    """
    if settings.allow_egress:
        logger.info("Egress guard disabled - outbound HTTP calls are allowed")
        return
    
    logger.info("Installing egress guard - blocking outbound HTTP calls")
    
    # Create a custom session with our adapter
    original_session = requests.Session
    
    def patched_session(*args, **kwargs):
        session = original_session(*args, **kwargs)
        session.mount('http://', EgressGuardAdapter())
        session.mount('https://', EgressGuardAdapter())
        return session
    
    # Monkey patch the Session class
    requests.Session = patched_session
    
    # Also patch the default session
    requests.sessions.Session = patched_session
    
    # Patch the default adapter for new sessions
    requests.adapters.HTTPAdapter = EgressGuardAdapter
    
    logger.info("Egress guard installed successfully")


def test_egress_guard():
    """
    Test the egress guard by attempting to make a blocked request.
    
    This is useful for verifying the guard is working correctly.
    """
    logger.info("Testing egress guard...")
    
    try:
        # This should be blocked
        response = requests.get("https://httpbin.org/get", timeout=5)
        logger.error("EGRESS GUARD FAILED: Request to external site succeeded!")
        return False
    except EgressBlockedError:
        logger.info("EGRESS GUARD WORKING: External request properly blocked")
        return True
    except Exception as e:
        logger.warning(f"EGRESS GUARD TEST: Unexpected error: {e}")
        return False


def test_local_requests():
    """
    Test that local requests still work.
    
    This verifies that the guard doesn't break legitimate local communication.
    """
    logger.info("Testing local requests...")
    
    try:
        # Test localhost request (should work)
        response = requests.get("http://localhost:8000/health", timeout=5)
        logger.info("Local request test passed")
        return True
    except requests.exceptions.ConnectionError:
        # This is expected if the service isn't running
        logger.info("Local request test: Connection error (expected if service not running)")
        return True
    except Exception as e:
        logger.error(f"Local request test failed: {e}")
        return False


# Install the guard when this module is imported
if not settings.allow_egress:
    install_egress_guard()
