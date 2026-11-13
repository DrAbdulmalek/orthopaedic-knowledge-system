"""تشغيل Demo التوليف الرسمي — مكافئ المرحلة الثانية لـ run_pilot.

    python -m pilot.run_synthesis_demo --out out/synth_demo
    orthok synthesize-demo --out out/synth_demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orthopaedic_knowledge.synthesis import run_synthesis

from .synthesis_demo import build_demo_documents


def run_official_synthesis_demo(out_dir: Path) -> dict:
    """شغّل الدمج الثلاثي على البيانات الوهمية وأنتج المخرجات الرسمية."""
    spine, others = build_demo_documents()
    out_dir.mkdir(parents=True, exist_ok=True)
    result, outputs = run_synthesis(
        spine, others,
        out_dir / "synthesis.db",
        out_dir=out_dir,
    )
    return {"pipeline": result.to_dict(), "outputs": outputs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="دمج ثلاثي وهمي: MILLER + ROCKWOOD + APLEY")
    ap.add_argument("--out", default="out/synth_demo")
    ns = ap.parse_args(argv)
    summary = run_official_synthesis_demo(Path(ns.out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
