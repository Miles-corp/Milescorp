"""Package des fournisseurs IA de MILES."""

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider

__all__ = ["AIProvider", "AIProviderError", "LocalProvider", "RemoteProvider"]
