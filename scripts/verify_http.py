"""Live HTTP verification script (not part of the package; used for release checks)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8742"


def req(method: str, path: str, payload: dict | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> None:
    checks: list[tuple[str, int, str]] = []

    status, body = req("GET", "/api/health")
    checks.append(("GET /api/health", status, json.loads(body)["status"]))
    status, body = req("GET", "/api/version")
    checks.append(("GET /api/version", status, json.loads(body)["version"]))
    status, body = req("GET", "/api/modes")
    checks.append(("GET /api/modes", status, str(len(json.loads(body)))))
    status, body = req("GET", "/api/examples")
    checks.append(("GET /api/examples", status, str(len(json.loads(body)["cases"]))))
    status, body = req("GET", "/api/providers")
    checks.append(("GET /api/providers", status, json.loads(body)["active"]))
    status, body = req("GET", "/api/rules")
    checks.append(("GET /api/rules", status, str(json.loads(body)["signal_rules"])))
    status, body = req("GET", "/api/easter-eggs")
    checks.append(("GET /api/easter-eggs", status, str(len(json.loads(body)["eggs"]))))

    status, body = req("POST", "/api/analyze", {"text": "我想你了", "mode": "extreme"})
    data = json.loads(body)
    checks.append(
        (
            "POST /api/analyze",
            status,
            "{} reaching={} verdict={}".format(
                data["signal_type"], data["ned_reaching_level"], data["verdict"]["text"]
            ),
        )
    )

    status, body = req(
        "POST",
        "/api/analyze",
        {
            "text": "我们已经结婚了",
            "mode": "extreme",
            "history": ["我喜欢你", "我想和你谈恋爱", "做我男朋友吧"],
        },
    )
    data = json.loads(body)
    checks.append(
        (
            "POST /api/analyze (escalation)",
            status,
            "{} {} / {}".format(
                data["ned_reaching_level"], data["reaching_label"], data["verdict"]["text"]
            ),
        )
    )

    status, body = req(
        "POST",
        "/api/asymmetry",
        {"positive_text": "她主动找我聊了两个小时", "negative_text": "五分钟没回复"},
    )
    data = json.loads(body)
    checks.append(
        (
            "POST /api/asymmetry",
            status,
            "{} {} {}/{}".format(
                data["asymmetry_score"],
                data["asymmetry_label"],
                data["positive_threshold"],
                data["negative_threshold"],
            ),
        )
    )

    status, body = req("POST", "/api/asymmetry", {})
    checks.append(("POST /api/asymmetry (invalid)", status, json.loads(body)["detail"][:52]))

    status, body = req(
        "POST",
        "/api/fnbp",
        {"expected_sender": "Fuyuki", "actual_senders": ["张三", "李四"], "notifications": 4},
    )
    data = json.loads(body)
    checks.append(
        (
            "POST /api/fnbp",
            status,
            "{}% {}".format(data["mispredict_rate"], data["verdict"]["text"]),
        )
    )

    status, body = req("POST", "/api/analyze", {"text": "x" * 9000})
    checks.append(("POST /api/analyze (too long)", status, "rejected"))

    status, body = req("GET", "/")
    ui = body
    checks.append(("GET /", status, f"{len(body)} bytes"))
    status, body = req("GET", "/static/style.css")
    checks.append(("GET /static/style.css", status, f"{len(body)} bytes"))
    status, body = req("GET", "/static/app.js")
    checks.append(("GET /static/app.js", status, f"{len(body)} bytes"))
    status, body = req("GET", "/docs")
    checks.append(("GET /docs", status, f"{len(body)} bytes"))
    status, body = req("GET", "/openapi.json")
    checks.append(("GET /openapi.json", status, "{} paths".format(len(json.loads(body)["paths"]))))

    for name, code, info in checks:
        print(f"{code:4d}  {name:34s} {info}")

    required = [
        "Nov1ce Evidence Denier",
        "Systematically explaining away good news since 2026.",
        "When reality becomes suspiciously positive",
        "Everything may be affection",
        "人好",
        "Local-first",
        "Paste a message or describe what happened",
        "Analyze Evidence",
        "Alternative Hypotheses",
        "NED Reaching Level",
        "Reality Check",
        "Final Verdict",
        "Negative Evidence Amplifier",
        "Evidence Asymmetry Detector",
        "Run Branch Predictor",
        "0.1.0",
    ]
    print("UI strings missing:", [item for item in required if item not in ui])
    print("unresolved jinja:", "{{" in ui or "{%" in ui)


if __name__ == "__main__":
    main()
