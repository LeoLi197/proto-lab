"""Firecrawl site exporter feature.

This module exposes a small REST API that proxies the open source
`firecrawl` project (https://github.com/firecrawl/firecrawl).  It allows
frontend users to submit a URL, waits for Firecrawl to finish crawling the
site (current page + child pages) and produces a downloadable Markdown
archive.  All logic is isolated in this feature package so existing modules
remain unaffected.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

router = APIRouter(
    prefix="/firecrawl-exporter",
    tags=["Firecrawl Exporter"],
)

DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_PAGES = 25
MAX_ALLOWED_PAGES = 200


class CrawlRequest(BaseModel):
    """Payload used to start a crawl job."""

    url: HttpUrl = Field(..., description="Root URL to crawl")
    max_depth: int = Field(
        DEFAULT_MAX_DEPTH,
        ge=0,
        le=8,
        description="How deep Firecrawl should follow links from the root page.",
    )
    max_pages: int = Field(
        DEFAULT_MAX_PAGES,
        ge=1,
        le=MAX_ALLOWED_PAGES,
        description="Maximum number of pages to capture.",
    )
    include_subdomains: bool = Field(
        False,
        description="Whether to include subdomains while crawling.",
    )
    ignore_sitemap: bool = Field(
        False,
        description="If true the Firecrawl crawler will ignore sitemap.xml hints.",
    )


class CrawlJobStartResponse(BaseModel):
    """Response returned when a crawl job has been created."""

    job_id: str = Field(..., description="Firecrawl job identifier")
    firecrawl_status: str = Field(..., description="Raw status reported by Firecrawl")
    detail: str = Field(..., description="Human readable status message")
    poll_after_seconds: float = Field(
        2.5,
        description="Suggested delay before polling job status again.",
    )


class CrawlJobStatus(BaseModel):
    """Represents the status of an existing crawl job."""

    job_id: str
    status: str = Field(..., description="Normalized job status")
    firecrawl_status: str = Field(..., description="Raw status reported by Firecrawl")
    page_count: Optional[int] = Field(None, description="Number of Markdown pages ready")
    download_url: Optional[str] = Field(
        None,
        description="Relative API endpoint for downloading the Markdown archive.",
    )
    detail: Optional[str] = Field(None, description="Human readable explanation")
    last_updated: Optional[str] = Field(
        None,
        description="ISO timestamp when Firecrawl last updated the job.",
    )


def _require_firecrawl_headers() -> Dict[str, str]:
    """Builds the authorization headers for Firecrawl's REST API."""

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "FIRECRAWL_API_KEY environment variable is not configured. "
                "Please supply a valid Firecrawl API key before using this feature."
            ),
        )

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _firecrawl_base_url() -> str:
    """Returns the configured Firecrawl base URL."""

    base_url = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev")
    return base_url.rstrip("/")


def _build_crawl_payload(request: CrawlRequest) -> Dict[str, object]:
    """Constructs a payload compatible with Firecrawl's crawl endpoint."""

    crawl_options = {
        "maxDepth": request.max_depth,
        "limit": min(request.max_pages, MAX_ALLOWED_PAGES),
        "includeSubdomains": request.include_subdomains,
        "ignoreSitemap": request.ignore_sitemap,
        "allowUntrustedCertificates": False,
    }

    return {
        "url": str(request.url),
        "maxDepth": crawl_options["maxDepth"],
        "limit": crawl_options["limit"],
        "includeSubdomains": crawl_options["includeSubdomains"],
        "ignoreSitemap": crawl_options["ignoreSitemap"],
        "formats": ["markdown"],
        "options": {
            "crawl": crawl_options,
            "formats": ["markdown"],
        },
    }


def _call_firecrawl(
    method: str,
    path: str,
    *,
    json_payload: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Performs an HTTP request against the Firecrawl API."""

    headers = _require_firecrawl_headers()
    url = f"{_firecrawl_base_url()}{path}"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json_payload,
            timeout=120,
        )
    except requests.RequestException as exc:  # pragma: no cover - network errors at runtime only
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Firecrawl API: {exc}",
        ) from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}

        raise HTTPException(
            status_code=response.status_code,
            detail=payload.get("detail") or payload.get("message") or "Firecrawl API error",
        )

    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(
            status_code=502,
            detail="Firecrawl API returned invalid JSON response.",
        ) from exc


def _normalize_status(status: str) -> str:
    normalized = status.lower()
    if normalized in {"done", "completed", "succeeded"}:
        return "completed"
    if normalized in {"running", "processing", "in_progress"}:
        return "running"
    if normalized in {"queued", "pending"}:
        return "queued"
    if normalized in {"failed", "error"}:
        return "failed"
    return normalized


def _extract_markdown_pages(data: Iterable[Dict[str, object]]) -> List[Dict[str, str]]:
    """Extracts markdown strings from Firecrawl's crawl payload."""

    pages: List[Dict[str, str]] = []
    for index, page in enumerate(data, start=1):
        markdown: Optional[str] = None
        title: Optional[str] = None

        if isinstance(page, dict):
            if isinstance(page.get("markdown"), str):
                markdown = page["markdown"]
            elif isinstance(page.get("content"), dict):
                content = page["content"]
                if isinstance(content.get("markdown"), str):
                    markdown = content["markdown"]
                elif isinstance(content.get("md"), str):
                    markdown = content["md"]

            metadata = page.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("title"), str):
                title = metadata.get("title")
            elif isinstance(page.get("title"), str):
                title = page["title"]

            if not title and isinstance(page.get("url"), str):
                title = page["url"]

        if not markdown:
            continue

        pages.append(
            {
                "index": index,
                "title": title or f"Page {index}",
                "markdown": markdown,
            }
        )

    return pages


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower() or "page"


def _build_zip_archive(pages: List[Dict[str, str]], root_url: str) -> io.BytesIO:
    """Converts page markdown data into a downloadable zip archive."""

    buffer = io.BytesIO()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        combined_sections: List[str] = []
        metadata: Dict[str, object] = {
            "generated_at": timestamp,
            "source_url": root_url,
            "page_count": len(pages),
            "pages": [],
        }

        for page in pages:
            index = page["index"]
            title = page["title"]
            markdown = page["markdown"]
            slug = _slugify(title)
            filename = f"{index:02d}-{slug}.md"
            header = f"# {title}\n\n" if not markdown.lstrip().startswith("#") else ""
            zip_file.writestr(filename, f"{header}{markdown}")
            combined_sections.append(f"## {title}\n\n{markdown}")
            metadata["pages"].append({
                "index": index,
                "title": title,
                "filename": filename,
            })

        overview = (
            f"# Firecrawl Export Summary\n\n"
            f"- Generated at: {timestamp}\n"
            f"- Source URL: {root_url}\n"
            f"- Markdown pages: {len(pages)}\n\n"
            "Each page is exported as an individual Markdown file in this archive."
        )
        zip_file.writestr("README.md", overview)
        zip_file.writestr("full-site.md", "\n\n---\n\n".join(combined_sections))
        zip_file.writestr(
            "metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )

    buffer.seek(0)
    return buffer


@router.post("/jobs", response_model=CrawlJobStartResponse)
def create_crawl_job(request: CrawlRequest) -> CrawlJobStartResponse:
    """Starts a new crawl job using Firecrawl's REST API."""

    payload = _build_crawl_payload(request)
    firecrawl_response = _call_firecrawl("POST", "/v1/crawl", json_payload=payload)

    job_id = firecrawl_response.get("jobId") or firecrawl_response.get("id")
    status = str(firecrawl_response.get("status") or "queued")

    if not job_id:
        raise HTTPException(
            status_code=502,
            detail="Firecrawl did not return a job identifier.",
        )

    detail = (
        "Crawl job created successfully. Firecrawl is fetching pages now."
        if _normalize_status(status) in {"queued", "running"}
        else f"Firecrawl reported status: {status}."
    )

    return CrawlJobStartResponse(
        job_id=job_id,
        firecrawl_status=status,
        detail=detail,
    )


@router.get("/jobs/{job_id}", response_model=CrawlJobStatus)
def get_crawl_job_status(job_id: str) -> CrawlJobStatus:
    """Fetches the current status for an existing crawl job."""

    firecrawl_response = _call_firecrawl("GET", f"/v1/crawl/{job_id}")
    status = str(firecrawl_response.get("status") or firecrawl_response.get("state") or "queued")
    normalized_status = _normalize_status(status)

    page_data = firecrawl_response.get("data") or firecrawl_response.get("pages")
    page_count = None
    if isinstance(page_data, list):
        page_count = len(_extract_markdown_pages(page_data))

    detail = firecrawl_response.get("detail") or firecrawl_response.get("message")
    if not detail:
        if normalized_status == "completed":
            detail = "Crawl complete. Markdown archive is ready for download."
        elif normalized_status == "running":
            detail = "Crawl in progress. Firecrawl is still collecting pages."
        elif normalized_status == "queued":
            detail = "Crawl queued. Waiting for Firecrawl workers to start."
        elif normalized_status == "failed":
            detail = "Crawl failed. Please review Firecrawl logs for details."

    updated_at = firecrawl_response.get("updatedAt") or firecrawl_response.get("updated_at")

    download_url = None
    if normalized_status == "completed":
        download_url = f"/api/firecrawl-exporter/jobs/{job_id}/download"

    return CrawlJobStatus(
        job_id=job_id,
        status=normalized_status,
        firecrawl_status=status,
        page_count=page_count,
        download_url=download_url,
        detail=detail,
        last_updated=updated_at,
    )


@router.get("/jobs/{job_id}/download")
def download_crawl_archive(job_id: str):
    """Streams a Markdown zip archive for the given crawl job."""

    firecrawl_response = _call_firecrawl("GET", f"/v1/crawl/{job_id}")
    status = _normalize_status(str(firecrawl_response.get("status") or ""))

    if status != "completed":
        raise HTTPException(
            status_code=409,
            detail="Crawl is not complete yet. Please try again once Firecrawl finishes.",
        )

    page_data = firecrawl_response.get("data") or firecrawl_response.get("pages")
    if not isinstance(page_data, list):
        raise HTTPException(
            status_code=502,
            detail="Firecrawl response did not include page data.",
        )

    pages = _extract_markdown_pages(page_data)
    if not pages:
        raise HTTPException(
            status_code=404,
            detail="Firecrawl returned no Markdown content to export.",
        )

    source_url = firecrawl_response.get("url") or firecrawl_response.get("job", {}).get("url")
    zip_buffer = _build_zip_archive(pages, root_url=source_url or "")

    filename_slug = _slugify(source_url or job_id)
    response = StreamingResponse(
        zip_buffer,
        media_type="application/zip",
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename_slug}-markdown.zip"
    return response
