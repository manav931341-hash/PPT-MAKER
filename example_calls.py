"""
example_calls.py — Tests the full agent flow via HTTP.
Run: python example_calls.py
Make sure FastAPI backend is running first: uvicorn main:app --port 8000
"""

import requests
import time
import sys

BASE = "http://localhost:8000"

def post(path, data, headers=None):
    r = requests.post(f"{BASE}{path}", json=data, headers=headers or {}, timeout=120)
    r.raise_for_status()
    return r.json()

def get(path):
    r = requests.get(f"{BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

def run_full_flow(goal: str, choices: list, label: str):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"GOAL: {goal}")
    print("="*60)

    # Start
    resp = post("/start", {"goal": goal})
    print(f"\n[C1] {resp['message'][:200]}")
    session_id = resp["session_id"]

    for i, choice in enumerate(choices, 1):
        print(f"\n>>> Sending choice: {choice}")
        time.sleep(1)
        resp = post("/respond", {"session_id": session_id, "choice": choice, "extra": ""})
        print(f"[C{i+1}] {resp.get('message','')[:300]}")
        if resp.get("type") == "file" or resp.get("files"):
            print(f"\n✅ FILES GENERATED:")
            for f in resp.get("files", []):
                print(f"  📥 {f['filename']} → {BASE}{f['download_url']}")
            return session_id

    print("⚠️  Flow ended before file generation")
    return session_id


def test_refine(session_id: str, message: str):
    print(f"\n{'='*60}")
    print(f"REFINEMENT TEST — session: {session_id}")
    print(f"Message: {message}")
    resp = requests.post(
        f"{BASE}/refine/{session_id}",
        json={"session_id": session_id, "message": message},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"Result: {data.get('message','')[:200]}")
    for f in data.get("files", []):
        print(f"  📥 {f['filename']}")


if __name__ == "__main__":
    # Health check
    try:
        h = get("/health")
        print(f"✅ Backend healthy: {h}")
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        sys.exit(1)

    # Test 1: PPTX pitch deck
    sid1 = run_full_flow(
        goal="Create a 10-slide pitch deck for an AI-powered fitness app targeting Gen Z",
        choices=["A", "A", "A T2", "approve"],  # confirm pptx, structure A, theme A tone 2, approve
        label="PPTX Pitch Deck",
    )

    # Test 2: Excel dashboard
    sid2 = run_full_flow(
        goal="Build a sales performance tracker Excel for Q2 2025 with regional breakdown",
        choices=["A", "B", "B T3", "approve"],
        label="XLSX Sales Tracker",
    )

    # Test 3: Both files
    sid3 = run_full_flow(
        goal="Marketing campaign report for a new product launch",
        choices=["C", "A", "C T1", "approve"],  # C = both
        label="Both PPTX + XLSX",
    )

    # Test 4: Refinement
    if sid1:
        test_refine(sid1, "Make the title slide use the ocean theme and add a stats slide with 3 KPIs")

    print("\n\n✅ All tests complete!")
