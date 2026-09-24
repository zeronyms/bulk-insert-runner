import time
from collections.abc import Callable
from typing import Any

import requests

from core.data_handler import format_template_str, group_items_for_request


def get_item_label(item: dict[str, Any], index: int) -> str:
    """Extract a user-friendly label from an item dictionary."""
    return (
        item.get("nama")
        or item.get("name")
        or item.get("kode")
        or item.get("code")
        or item.get("id")
        or f"Row #{index}"
    )


def build_execution_tasks(
    url: str,
    headers: dict[str, str],
    items: list[dict[str, Any]],
    group_by: str | None = None,
    array_key: str | None = None,
) -> list[tuple[str, dict[str, str], dict[str, Any], str]]:
    """Build prepared HTTP request tasks (url, headers, payload, label) for execution.

    Supports both single-row standard requests and array-grouped batch requests.
    """
    if array_key:
        grouped = group_items_for_request(items, group_by, array_key)
        tasks: list[tuple[str, dict[str, str], dict[str, Any], str]] = []
        for ctx, payload in grouped:
            req_url = format_template_str(url, ctx)
            req_headers = {k: format_template_str(v, ctx) for k, v in headers.items()}
            count = len(payload.get(array_key, []))
            if group_by and group_by in ctx:
                label = f"{group_by}={ctx[group_by]} ({count} items)"
            else:
                label = f"Batch ({count} items)"
            tasks.append((req_url, req_headers, payload, label))
        return tasks

    tasks = []
    for idx, item in enumerate(items, start=1):
        req_url = format_template_str(url, item) if "{" in url else url
        req_headers = {
            k: format_template_str(v, item) if "{" in v else v for k, v in headers.items()
        }
        label = get_item_label(item, idx)
        tasks.append((req_url, req_headers, item, label))
    return tasks


def execute_bulk_requests(
    url: str,
    method: str,
    headers: dict[str, str],
    items: list[dict[str, Any]],
    interval: float = 2.0,
    timeout: int = 30,
    group_by: str | None = None,
    array_key: str | None = None,
    on_progress: Callable[[int, int, str, int, bool, str], None] | None = None,
) -> tuple[int, int]:
    """Execute HTTP requests for a list of items sequentially.

    Supports both:
    - Standard Mode: 1 item = 1 request
    - Grouped Mode: groups items into batches wrapped in array_key (e.g. {"courses": [...]})
      with dynamic URL and header formatting.

    Returns:
        tuple[int, int]: (success_count, fail_count)
    """
    tasks = build_execution_tasks(
        url=url,
        headers=headers,
        items=items,
        group_by=group_by,
        array_key=array_key,
    )

    success_count = 0
    fail_count = 0
    session = requests.Session()
    total = len(tasks)

    for idx, (req_url, req_headers, req_payload, label) in enumerate(tasks, start=1):
        print(f"[{idx}/{total}] Sending: {label}...")

        try:
            resp = session.request(
                method=method,
                url=req_url,
                headers=req_headers,
                json=req_payload,
                timeout=timeout,
            )

            status = resp.status_code
            if resp.ok:
                print(f"   Status : {status} (Success)")
                success_count += 1
                if on_progress:
                    on_progress(idx, total, label, status, True, resp.text)
            else:
                print(f"   Status : {status} (Failed)")
                print(f"   Detail : {resp.text[:180]}...")
                fail_count += 1
                if on_progress:
                    on_progress(idx, total, label, status, False, resp.text)

                # Auto-stop if session expired
                if status in (401, 419):
                    print(
                        "\n[STOP] Login session / CSRF token expired. "
                        "Please copy a new cURL and run Menu 1."
                    )
                    break

        except requests.RequestException as err:
            print(f"   Network Error: {err}")
            fail_count += 1
            if on_progress:
                on_progress(idx, total, label, 0, False, str(err))

        if idx < total and interval > 0:
            print(f"   Waiting {interval} second(s)...\n")
            time.sleep(interval)

    return success_count, fail_count
