import json
import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaProvider:
    """
    Optional provider interface for local Ollama inference.
    Fails safely and gracefully if Ollama is offline or model is missing.
    """

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or getattr(settings, 'OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/')
        self.model = model or getattr(settings, 'OLLAMA_MODEL', 'llama3:latest')
        self.timeout = getattr(settings, 'OLLAMA_TIMEOUT_SECONDS', 25)

    def check_status(self) -> dict:
        """
        Pings Ollama endpoint to determine reachability and available models.
        Never raises exceptions; returns clean structured status.
        """
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get('name') for m in data.get('models', [])]
                    model_found = any(self.model == m or self.model in m for m in models)
                    return {
                        'reachable': True,
                        'provider': 'Ollama Local',
                        'base_url': self.base_url,
                        'configured_model': self.model,
                        'model_installed': model_found,
                        'available_models': models,
                        'error': None if model_found else f"Configured model '{self.model}' not found in local Ollama library."
                    }
                else:
                    return {
                        'reachable': False,
                        'provider': 'Ollama Local',
                        'base_url': self.base_url,
                        'configured_model': self.model,
                        'model_installed': False,
                        'available_models': [],
                        'error': f"Ollama returned HTTP status {res.status_code}."
                    }
        except httpx.ConnectError:
            return {
                'reachable': False,
                'provider': 'Ollama Local',
                'base_url': self.base_url,
                'configured_model': self.model,
                'model_installed': False,
                'available_models': [],
                'error': f"Cannot connect to Ollama at {self.base_url}. Service is offline or not installed."
            }
        except Exception as e:
            return {
                'reachable': False,
                'provider': 'Ollama Local',
                'base_url': self.base_url,
                'configured_model': self.model,
                'model_installed': False,
                'available_models': [],
                'error': str(e)
            }

    def generate_json_response(self, system_prompt: str, prompt: str) -> dict | None:
        """
        Sends structured JSON request to Ollama using format='json'.
        Returns parsed dict or None if offline or parsing fails.
        """
        status = self.check_status()
        if not status.get('reachable') or not status.get('model_installed'):
            return None

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    raw_text = res.json().get('response', '')
                    return json.loads(raw_text)
                else:
                    logger.warning(f"Ollama generation returned HTTP {res.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Ollama inference error: {e}")
            return None
