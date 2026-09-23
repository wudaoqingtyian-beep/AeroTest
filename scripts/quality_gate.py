"""质量门禁：解析 JUnit XML，核心套件通过率低于阈值则流水线失败。

用法：
    python scripts/quality_gate.py reports/junit-suite.xml --min-rate 1.0
"""
import argparse
import sys
import xml.etree.ElementTree as ET


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit_xml")
    parser.add_argument("--min-rate", type=float, default=1.0,
                        help="最低通过率（1.0 = 全过才算通过）")
    args = parser.parse_args()

    root = ET.parse(args.junit_xml).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    passed = total - failures - skipped
    rate = passed / total if total else 0.0

    print(f"质量门禁: 通过 {passed}/{total}（{rate:.1%}），"
          f"阈值 {args.min_rate:.1%}")
    if rate < args.min_rate:
        print("质量门禁未达标，阻断合并！")
        return 1
    print("质量门禁通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
