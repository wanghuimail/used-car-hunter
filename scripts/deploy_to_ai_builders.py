"""Deploy Used Car Hunter to ai-builders.space via the platform API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_URL = "https://space.ai-builders.com/backend/v1/deployments"
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "deploy-config.json"


def main() -> int:
    token = os.environ.get("AI_BUILDER_TOKEN")
    if not token:
        print("Error: set AI_BUILDER_TOKEN in your environment.", file=sys.stderr)
        return 1

    if not CONFIG_PATH.exists():
        print(f"Error: missing {CONFIG_PATH}", file=sys.stderr)
        return 1

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    repo_url = config.get("repo_url", "")
    if "REPLACE_WITH_YOUR_USERNAME" in repo_url:
        print("Error: update repo_url in deploy-config.json first.", file=sys.stderr)
        return 1

    payload = {
        "repo_url": repo_url,
        "service_name": config["service_name"],
        "branch": config["branch"],
        "port": config.get("port", 8000),
        "streaming_log_timeout_seconds": 120,
    }
    if config.get("env_vars"):
        payload["env_vars"] = config["env_vars"]

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"Deploy failed ({exc.code}):", exc.read().decode("utf-8", "replace"), file=sys.stderr)
        return 1

    result = json.loads(body)
    print(json.dumps(result, indent=2))
    service = config["service_name"]
    print(f"\nPublic URL (after provisioning): https://{service}.ai-builders.space")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
