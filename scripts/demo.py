"""CLI demo of AyuConnect's Gemma 4 intake — handy for the video shoot.

Usage:
    python scripts/demo.py "I have crushing chest pain spreading to my left arm"

Requires the backend to be running (default http://localhost:8000) or an
override via AYU_API_URL.
"""

from __future__ import annotations

import json
import os
import sys
from urllib import error, request

API = os.environ.get("AYU_API_URL", "http://localhost:8000")


def _call(path: str, body: dict) -> dict:
    req = request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except error.HTTPError as exc:
        sys.exit(f"backend {exc.code}: {exc.read().decode()}")
    except error.URLError as exc:
        sys.exit(f"could not reach {API} — is the backend running? ({exc.reason})")


def main() -> None:
    user_message = " ".join(sys.argv[1:]) or "I've had a runny nose and mild headache for two days."
    history: list[dict[str, str]] = []
    age = 58
    sex = "Male"

    print(f"\n[Patient] {user_message}\n")
    for turn in range(8):
        resp = _call("/chat", {
            "history": history,
            "user_message": user_message,
            "patient_age": age,
            "patient_sex": sex,
        })
        assistant = resp["assistant_message"]
        print(f"[Ayu] {assistant}")
        for tc in resp.get("tool_calls", []):
            print(f"  ↳ tool {tc['name']}({tc['arguments']}) → {tc['result']}")

        if resp.get("final"):
            print("\n=== INTAKE COMPLETE ===")
            print(json.dumps(resp["summary"], indent=2))
            return

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant})
        user_message = input("\n[Patient] ").strip()
        if not user_message:
            print("(empty input — ending session)")
            return

    print("(turn budget exhausted)")


if __name__ == "__main__":
    main()
