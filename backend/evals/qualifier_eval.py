"""Qualifier eval on 9 real companies from the candle campaigns (evidence snapshot).

Run: .venv/bin/python -m evals.qualifier_eval   (uses the real LLM pool, ~2 minutes)
Each case lists the verdicts a careful human would accept and why.
"""

import json
from pathlib import Path

from app.agents import qualifier

CASES = json.loads((Path(__file__).parent / "qualifier_cases.json").read_text())


def main() -> None:
    passed = 0
    for case in CASES:
        out = qualifier.qualify(case["campaign"], case["name"], case["evidence"])
        ok = out["verdict"] in case["expected"]
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(
            f"{mark} {case['name']}: {out['verdict']} {out['score']} "
            f"(want {'/'.join(case['expected'])}: {case['why']})"
        )
    print(f"\n{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
