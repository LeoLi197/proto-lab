# Path: backend/features/core_api/router.py
import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, HTTPException
from fastapi import __version__ as fastapi_version_str

# --- API Router Initialization ---
# [FIX] The prefix is removed here and will be added in main.py
# This makes the router module more reusable and avoids prefix conflicts.
router = APIRouter(
    tags=["Core API"]  # Group these endpoints in the API docs
)

# --- Pydantic Models for Type Hinting and Validation ---
class AIProxyRequest(BaseModel):
    provider: str
    model: str
    prompt: str = "Hello, AI!"
    image: Optional[str] = None
    images: Optional[List[str]] = None
    system: Optional[str] = None
    audio: Optional[str] = None
    api_key_tier: str = Field(alias='apiKeyTier', default='free')

class AIProxyResponse(BaseModel):
    success: bool
    response: str
    inputTokens: int
    outputTokens: int
    provider: str
    model: str
    
class HealthResponse(BaseModel):
    success: bool
    status: str
    message: str
    runtime: str
    timestamp: str
    env_vars_check: Optional[Dict[str, str]] = None

class VersionResponse(BaseModel):
    python_version: str
    python_version_info: list
    platform: str
    fastapi_version: str
    
class PlaceholderResponse(BaseModel):
    success: bool
    message: str
    summary: Optional[Dict[str, Any]] = None

# --- Helper Function for Gemini API call ---
def _call_gemini_api(api_key: str, model: str, prompt: str, image: Optional[str], images: Optional[List[str]], system: Optional[str], audio_b64: Optional[str]) -> Dict[str, Any]:
    """Helper function to call the Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    parts = []
    
    if system:
        parts.append({"text": f"System: {system}\n\n"})
    parts.append({"text": prompt})

    image_list_to_process = images or []
    if image and not image_list_to_process:
        image_list_to_process.append(image)

    for img_b64 in image_list_to_process:
        mime_type = "image/jpeg" if img_b64.startswith('/9j/') else "image/png"
        parts.append({"inline_data": {"mime_type": mime_type, "data": img_b64}})
        
    if audio_b64:
        parts.append({"inline_data": {"mime_type": "audio/wav", "data": audio_b64}})

    request_body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.7, "topK": 1, "topP": 1, "maxOutputTokens": 20000},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    response = requests.post(url, json=request_body)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Gemini API error: {response.text}")
    
    result = response.json()
    usage_metadata = result.get('usageMetadata', {})
    input_tokens = usage_metadata.get('promptTokenCount', 0)
    output_tokens = usage_metadata.get('candidatesTokenCount', 0)
    
    generated_text = ""
    if result.get('candidates'):
        candidate = result['candidates'][0]
        if 'content' in candidate and 'parts' in candidate['content']:
            text_parts = [part['text'] for part in candidate['content']['parts'] if 'text' in part]
            generated_text = "".join(text_parts)
        if not generated_text and candidate.get('finishReason') == 'SAFETY':
            raise HTTPException(status_code=400, detail="Response blocked by Gemini's safety settings.")

    return {
        'success': True, 'response': generated_text,
        'inputTokens': input_tokens, 'outputTokens': output_tokens,
        'provider': 'gemini', 'model': model
    }

# --- API Routes ---

@router.post("/ai-proxy", response_model=AIProxyResponse)
async def ai_proxy(data: AIProxyRequest):
    """
    Proxies requests to various AI providers.
    Currently implements Gemini and provides mocks for others.
    """
    env_key_name = f'{data.provider.upper()}_API_KEY'
    if data.provider == 'gemini' and data.api_key_tier == 'paid':
        env_key_name = 'GEMINI_API_KEY_PAID'
    
    api_key = os.environ.get(env_key_name)
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail=f"API key not configured on server. Please set {env_key_name} in Google Cloud Run Environment Variables."
        )

    if data.provider == 'gemini':
        return _call_gemini_api(
            api_key=api_key, model=data.model, prompt=data.prompt,
            image=data.image, images=data.images, system=data.system, audio_b64=data.audio
        )
    else:
        # Mock responses for other providers
        return AIProxyResponse(
            success=True,
            response=f'Mock response from {data.provider} {data.model}.',
            inputTokens=10,
            outputTokens=20,
            provider=data.provider,
            model=data.model
        )

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Provides an enhanced health check endpoint for monitoring and diagnostics."""
    
    keys_to_check = ['GEMINI_API_KEY', 'OPENAI_API_KEY', 'CLAUDE_API_KEY', 'QWEN_API_KEY']
    env_check_results = {}
    for key in keys_to_check:
        if os.environ.get(key):
            env_check_results[key] = "✅ Set"
        else:
            env_check_results[key] = "❌ Not Set"

    return HealthResponse(
        success=True,
        status='healthy',
        message='flashmvp API on Google Cloud Run is working!',
        runtime='FastAPI on Google Cloud Run',
        timestamp=datetime.now().isoformat(),
        env_vars_check=env_check_results
    )

@router.get("/version", response_model=VersionResponse)
async def get_version():
    """Returns Python and FastAPI version information."""
    return VersionResponse(
        python_version=sys.version,
        python_version_info=list(sys.version_info),
        platform=sys.platform,
        fastapi_version=fastapi_version_str
    )

# --- Placeholder Routes for Functionality Migrated to Cloudflare Workers ---
@router.post("/track-usage", response_model=PlaceholderResponse)
async def track_usage_placeholder(request: Request):
    """Placeholder: Usage tracking is now handled by Cloudflare Workers + D1."""
    data = await request.json()
    return PlaceholderResponse(
        success=True,
        message='This endpoint is a placeholder. Usage tracking is handled by Cloudflare Workers + D1.',
        summary={'todayCost': round(data.get('cost', 0), 4)}
    )

@router.get("/usage-report", response_model=PlaceholderResponse)
async def usage_report_placeholder():
    """Placeholder: Usage reporting is now handled by Cloudflare Workers + D1."""
    return PlaceholderResponse(
        success=True,
        message='This endpoint is a placeholder. Usage reporting is handled by Cloudflare Workers + D1.'
    )