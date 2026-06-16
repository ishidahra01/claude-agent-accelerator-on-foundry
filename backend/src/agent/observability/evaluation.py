from __future__ import annotations

import argparse
import glob
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.agent.runtime_contracts import EXPECTED_ANALYSIS_OUTPUT_SCHEMA


SEVERITY_ORDER = {
    "informational": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}
ANALYSIS_TOP_LEVEL_KEYS = {"summary", "security", "cost", "architecture"}


@dataclass(frozen=True)
class EvaluationFinding:
    id: str
    passed: bool
    message: str
    severity: str = "error"
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RubricScore:
    name: str
    weight: float
    score: float
    reason: str


@dataclass(frozen=True)
class EvaluationScorecard:
    dataset: str
    total_rows: int
    passed_rows: int
    policy_findings: list[EvaluationFinding]
    rubric_scores: list[RubricScore]

    @property
    def pass_rate(self) -> float:
        return self.passed_rows / self.total_rows if self.total_rows else 0.0

    @property
    def weighted_rubric_score(self) -> float:
        total_weight = sum(score.weight for score in self.rubric_scores)
        if total_weight <= 0:
            return 0.0
        return sum(score.score * score.weight for score in self.rubric_scores) / total_weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "totalRows": self.total_rows,
            "passedRows": self.passed_rows,
            "passRate": round(self.pass_rate, 4),
            "weightedRubricScore": round(self.weighted_rubric_score, 4),
            "policyFindings": [finding.__dict__ for finding in self.policy_findings],
            "rubricScores": [score.__dict__ for score in self.rubric_scores],
        }


def load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for evaluation YAML assets. Install optional evaluation dependencies with "
            "`pip install -r requirements-eval.txt`."
        ) from exc

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML object in {path}.")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}.")
            rows.append(row)
    return rows


def extract_analysis_output(response: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(response, Mapping):
        candidate = dict(response)
        if ANALYSIS_TOP_LEVEL_KEYS.issubset(candidate):
            return candidate
        raise ValueError("Response object does not contain the analysis output top-level keys.")

    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and ANALYSIS_TOP_LEVEL_KEYS.issubset(candidate):
            return candidate

    raise ValueError("Could not find a JSON object with summary/security/cost/architecture keys in response.")


def validate_analysis_output(analysis: Mapping[str, Any]) -> list[EvaluationFinding]:
    findings: list[EvaluationFinding] = []
    required = EXPECTED_ANALYSIS_OUTPUT_SCHEMA["required"]
    assert isinstance(required, list)

    for key in required:
        if key not in analysis:
            findings.append(EvaluationFinding(id=f"schema.missing.{key}", passed=False, message=f"Missing top-level key: {key}"))

    summary = analysis.get("summary")
    if not isinstance(summary, Mapping):
        findings.append(EvaluationFinding(id="schema.summary.type", passed=False, message="summary must be an object."))
    else:
        for key in ("resourcesAnalyzed", "securityFindings", "costSavingsOpportunities"):
            value = summary.get(key)
            if not isinstance(value, int) or value < 0:
                findings.append(
                    EvaluationFinding(
                        id=f"schema.summary.{key}",
                        passed=False,
                        message=f"summary.{key} must be a non-negative integer.",
                        evidence={"value": value},
                    )
                )

    _validate_array_items(findings, analysis, "security", ("severity", "resource", "finding", "remediation"))
    _validate_array_items(findings, analysis, "cost", ("resource", "recommendation", "estimatedSavings"))
    _validate_array_items(findings, analysis, "architecture", ("pillar", "finding", "recommendation"))
    return findings


def _validate_array_items(
    findings: list[EvaluationFinding], analysis: Mapping[str, Any], key: str, required_fields: Sequence[str]
) -> None:
    value = analysis.get(key)
    if not isinstance(value, list):
        findings.append(EvaluationFinding(id=f"schema.{key}.type", passed=False, message=f"{key} must be an array."))
        return

    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            findings.append(
                EvaluationFinding(id=f"schema.{key}.{index}.type", passed=False, message=f"{key}[{index}] must be an object.")
            )
            continue
        for field_name in required_fields:
            field_value = item.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                findings.append(
                    EvaluationFinding(
                        id=f"schema.{key}.{index}.{field_name}",
                        passed=False,
                        message=f"{key}[{index}].{field_name} must be a non-empty string.",
                    )
                )


def evaluate_policies(
    analysis: Mapping[str, Any], expected: Mapping[str, Any], policies: Sequence[Mapping[str, Any]]
) -> list[EvaluationFinding]:
    findings = validate_analysis_output(analysis)
    for policy_doc in policies:
        policy = policy_doc.get("policy", policy_doc)
        if not isinstance(policy, Mapping):
            continue
        policy_id = str(policy.get("id", "policy"))
        requirements = policy.get("requirements", [])
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if isinstance(requirement, Mapping):
                findings.append(_evaluate_requirement(policy_id, requirement, analysis, expected))
    return findings


def _evaluate_requirement(
    policy_id: str, requirement: Mapping[str, Any], analysis: Mapping[str, Any], expected: Mapping[str, Any]
) -> EvaluationFinding:
    requirement_id = str(requirement.get("id", "requirement"))
    check = str(requirement.get("check", "manual"))
    full_id = f"{policy_id}.{requirement_id}"

    if check == "schema-valid":
        schema_findings = validate_analysis_output(analysis)
        return EvaluationFinding(
            id=full_id,
            passed=not schema_findings,
            message="Analysis output follows the stable schema." if not schema_findings else "Analysis output violates the stable schema.",
            evidence={"errors": [finding.id for finding in schema_findings]},
        )

    if check == "require-non-empty":
        path = str(requirement.get("path", ""))
        values = _values_at_path(analysis, path)
        missing = [index for index, value in enumerate(values) if not isinstance(value, str) or not value.strip()]
        return EvaluationFinding(
            id=full_id,
            passed=bool(values) and not missing,
            message=f"All values at {path} are non-empty." if bool(values) and not missing else f"Missing non-empty values at {path}.",
            evidence={"path": path, "checked": len(values), "missingIndexes": missing},
        )

    if check == "expected-keywords":
        category = str(requirement.get("category", ""))
        expected_key = str(requirement.get("expected_key", ""))
        keywords = _expected_keywords(expected, expected_key) or _as_string_list(requirement.get("keywords", []))
        matched = _category_contains_any(analysis, category, keywords)
        return EvaluationFinding(
            id=full_id,
            passed=matched,
            message=f"Expected signal {expected_key or keywords} was found in {category}." if matched else f"Expected signal {expected_key or keywords} was not found in {category}.",
            evidence={"category": category, "keywords": keywords},
        )

    if check == "minimum-count":
        category = str(requirement.get("category", ""))
        minimum = int(requirement.get("minimum", 0))
        expected_key = requirement.get("minimum_from_expected")
        if isinstance(expected_key, str):
            expected_value = _value_at_dotted_path(expected, expected_key)
            if isinstance(expected_value, int):
                minimum = expected_value
        actual = len(analysis.get(category, [])) if isinstance(analysis.get(category), list) else 0
        return EvaluationFinding(
            id=full_id,
            passed=actual >= minimum,
            message=f"{category} has at least {minimum} findings." if actual >= minimum else f"{category} has {actual} findings, expected at least {minimum}.",
            evidence={"category": category, "actual": actual, "minimum": minimum},
        )

    if check == "severity-at-least":
        category = str(requirement.get("category", "security"))
        expected_key = str(requirement.get("expected_key", ""))
        keywords = _expected_keywords(expected, expected_key) or _as_string_list(requirement.get("keywords", []))
        minimum = str(requirement.get("minimum", "high")).lower()
        passed, evidence = _severity_at_least(analysis, category, keywords, minimum)
        return EvaluationFinding(
            id=full_id,
            passed=passed,
            message=f"Severity for {expected_key or keywords} is at least {minimum}." if passed else f"Severity for {expected_key or keywords} is below {minimum} or missing.",
            evidence=evidence,
        )

    return EvaluationFinding(id=full_id, passed=True, severity="info", message="Manual requirement recorded but not executed.")


def evaluate_rubric(analysis: Mapping[str, Any], expected: Mapping[str, Any], rubric_doc: Mapping[str, Any]) -> list[RubricScore]:
    rubric = rubric_doc.get("rubric", rubric_doc)
    dimensions = rubric.get("dimensions", []) if isinstance(rubric, Mapping) else []
    if not isinstance(dimensions, list):
        return []

    scores: list[RubricScore] = []
    for dimension in dimensions:
        if not isinstance(dimension, Mapping):
            continue
        name = str(dimension.get("name", "dimension"))
        weight = float(dimension.get("weight", 0.0))
        score, reason = _score_dimension(name, analysis, expected)
        scores.append(RubricScore(name=name, weight=weight, score=round(score, 4), reason=reason))
    return scores


def _score_dimension(name: str, analysis: Mapping[str, Any], expected: Mapping[str, Any]) -> tuple[float, str]:
    if name == "coverage":
        total, matched = _expected_keyword_coverage(analysis, expected)
        if total == 0:
            return 1.0, "No expected keyword groups were provided."
        return matched / total, f"Matched {matched} of {total} expected signal groups."

    if name == "actionability":
        required_paths = ["security[].remediation", "cost[].recommendation", "architecture[].recommendation"]
        values = [value for path in required_paths for value in _values_at_path(analysis, path)]
        if not values:
            return 0.0, "No actionable recommendation fields were present."
        non_empty = sum(1 for value in values if isinstance(value, str) and len(value.strip()) >= 8)
        return non_empty / len(values), f"{non_empty} of {len(values)} recommendation fields are substantive."

    if name == "accuracy":
        expected_resources = expected.get("resourcesAnalyzed") or expected.get("resources_analyzed")
        actual_resources = analysis.get("summary", {}).get("resourcesAnalyzed") if isinstance(analysis.get("summary"), Mapping) else None
        count_consistency = _summary_count_consistency(analysis)
        resource_score = 1.0 if expected_resources == actual_resources else 0.5 if isinstance(actual_resources, int) else 0.0
        score = (resource_score + count_consistency) / 2
        return score, f"Resource count score={resource_score}; summary count consistency={count_consistency}."

    if name == "prioritization":
        severe_signals = ["public_blob", "open_rdp"]
        matched = 0
        total = 0
        for key in severe_signals:
            keywords = _expected_keywords(expected, f"security.{key}")
            if not keywords:
                continue
            total += 1
            passed, _ = _severity_at_least(analysis, "security", keywords, "high")
            if passed:
                matched += 1
        if total == 0:
            return 1.0, "No severity-sensitive expected signals were provided."
        return matched / total, f"{matched} of {total} severity-sensitive signals were prioritized as High or Critical."

    return 0.0, f"No deterministic scorer is implemented for rubric dimension {name}."


def evaluate_rows(
    rows: Sequence[Mapping[str, Any]], policies: Sequence[Mapping[str, Any]], rubric_doc: Mapping[str, Any], dataset_name: str
) -> EvaluationScorecard:
    all_findings: list[EvaluationFinding] = []
    all_rubric_scores: list[RubricScore] = []
    passed_rows = 0

    for index, row in enumerate(rows):
        response = row.get("response")
        expected = row.get("expected", {})
        if not isinstance(expected, Mapping):
            expected = {}
        try:
            analysis = extract_analysis_output(response if response is not None else row)
        except ValueError as exc:
            row_findings = [EvaluationFinding(id=f"row.{index}.extract", passed=False, message=str(exc))]
            row_scores: list[RubricScore] = []
        else:
            row_findings = evaluate_policies(analysis, expected, policies)
            row_scores = evaluate_rubric(analysis, expected, rubric_doc)

        if all(finding.passed for finding in row_findings):
            passed_rows += 1
        all_findings.extend(_prefix_findings(index, row_findings))
        all_rubric_scores.extend(row_scores)

    return EvaluationScorecard(
        dataset=dataset_name,
        total_rows=len(rows),
        passed_rows=passed_rows,
        policy_findings=all_findings,
        rubric_scores=_average_rubric_scores(all_rubric_scores),
    )


def _prefix_findings(row_index: int, findings: Iterable[EvaluationFinding]) -> list[EvaluationFinding]:
    return [
        EvaluationFinding(
            id=f"row.{row_index}.{finding.id}",
            passed=finding.passed,
            message=finding.message,
            severity=finding.severity,
            evidence=finding.evidence,
        )
        for finding in findings
    ]


def _average_rubric_scores(scores: Sequence[RubricScore]) -> list[RubricScore]:
    by_name: dict[str, list[RubricScore]] = {}
    for score in scores:
        by_name.setdefault(score.name, []).append(score)

    averaged: list[RubricScore] = []
    for name, named_scores in by_name.items():
        weight = named_scores[0].weight
        average = sum(score.score for score in named_scores) / len(named_scores)
        reasons = "; ".join(score.reason for score in named_scores[:3])
        averaged.append(RubricScore(name=name, weight=weight, score=round(average, 4), reason=reasons))
    return averaged


def _values_at_path(value: Any, path: str) -> list[Any]:
    parts = path.split(".") if path else []
    values = [value]
    for part in parts:
        next_values: list[Any] = []
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        for current in values:
            if isinstance(current, Mapping) and key in current:
                child = current[key]
                if is_array and isinstance(child, list):
                    next_values.extend(child)
                elif not is_array:
                    next_values.append(child)
        values = next_values
    return values


def _value_at_dotted_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _expected_keywords(expected: Mapping[str, Any], expected_key: str) -> list[str]:
    value = _value_at_dotted_path(expected, expected_key) if expected_key else None
    return _as_string_list(value)


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    return []


def _category_contains_any(analysis: Mapping[str, Any], category: str, keywords: Sequence[str]) -> bool:
    text = _category_text(analysis, category)
    return any(keyword.lower() in text for keyword in keywords)


def _category_text(analysis: Mapping[str, Any], category: str) -> str:
    value = analysis.get(category, [])
    return json.dumps(value, ensure_ascii=False).lower()


def _severity_at_least(
    analysis: Mapping[str, Any], category: str, keywords: Sequence[str], minimum: str
) -> tuple[bool, dict[str, Any]]:
    minimum_value = SEVERITY_ORDER.get(minimum.lower(), 3)
    items = analysis.get(category, [])
    if not isinstance(items, list):
        return False, {"reason": "category is not an array"}

    for item in items:
        item_text = json.dumps(item, ensure_ascii=False).lower()
        if not any(keyword.lower() in item_text for keyword in keywords):
            continue
        severity = str(item.get("severity", "")) if isinstance(item, Mapping) else ""
        severity_value = SEVERITY_ORDER.get(severity.lower(), -1)
        return severity_value >= minimum_value, {"severity": severity, "minimum": minimum, "keywords": list(keywords)}

    return False, {"reason": "no matching finding", "keywords": list(keywords)}


def _expected_keyword_coverage(analysis: Mapping[str, Any], expected: Mapping[str, Any]) -> tuple[int, int]:
    total = 0
    matched = 0
    for category in ("security", "cost", "architecture"):
        category_expected = expected.get(category)
        if not isinstance(category_expected, Mapping):
            continue
        for value in category_expected.values():
            keywords = _as_string_list(value)
            if not keywords:
                continue
            total += 1
            if _category_contains_any(analysis, category, keywords):
                matched += 1
    return total, matched


def _summary_count_consistency(analysis: Mapping[str, Any]) -> float:
    summary = analysis.get("summary")
    if not isinstance(summary, Mapping):
        return 0.0
    checks = [
        summary.get("securityFindings") == len(analysis.get("security", [])) if isinstance(analysis.get("security"), list) else False,
        summary.get("costSavingsOpportunities") == len(analysis.get("cost", [])) if isinstance(analysis.get("cost"), list) else False,
    ]
    return sum(1 for check in checks if check) / len(checks)


def _load_policy_files(patterns: Sequence[str]) -> list[dict[str, Any]]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(Path(path) for path in sorted(glob.glob(pattern)))
    return [load_yaml_file(path) for path in files]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Azure analysis responses against local policy and rubric assets.")
    parser.add_argument("--responses", type=Path, required=True, help="JSONL file containing query/response/expected rows.")
    parser.add_argument("--policy", action="append", default=[], help="Policy YAML path or glob. Can be provided more than once.")
    parser.add_argument("--rubric", type=Path, required=True, help="Rubric YAML path.")
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON scorecard.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_jsonl(args.responses)
    policies = _load_policy_files(args.policy)
    rubric = load_yaml_file(args.rubric)
    scorecard = evaluate_rows(rows, policies, rubric, dataset_name=str(args.responses))
    result = scorecard.to_dict()

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0 if scorecard.pass_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
