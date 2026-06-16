from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Sequence


def _import_foundry_sdk() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
        from openai.types.eval_create_params import DataSourceConfigCustom
        from openai.types.evals.create_eval_jsonl_run_data_source_param import (
            CreateEvalJSONLRunDataSourceParam,
            SourceFileID,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Foundry cloud evaluation dependencies are not installed. Run "
            "`pip install -r requirements-eval.txt` first."
        ) from exc

    return AIProjectClient, DefaultAzureCredential, DataSourceConfigCustom, CreateEvalJSONLRunDataSourceParam, SourceFileID


def _testing_criteria(eval_model: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            "initialization_parameters": {"model": eval_model},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_text}}",
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "task_adherence",
            "evaluator_name": "builtin.task_adherence",
            "initialization_parameters": {"model": eval_model},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}",
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "violence",
            "evaluator_name": "builtin.violence",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_text}}",
            },
        },
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Microsoft Foundry cloud evaluation against a hosted agent target.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/bad-config.queries.jsonl"))
    parser.add_argument("--endpoint", default=os.getenv("AZURE_AI_PROJECT_ENDPOINT"))
    parser.add_argument("--agent-name", default=os.getenv("FOUNDRY_AGENT_NAME") or os.getenv("CLAUDE_HOSTED_AGENT_NAME"))
    parser.add_argument("--agent-version", default=os.getenv("FOUNDRY_AGENT_VERSION") or os.getenv("CLAUDE_HOSTED_AGENT_VERSION", ""))
    parser.add_argument("--eval-model", default=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME"))
    parser.add_argument("--dataset-name", default="azure-waf-bad-config-queries")
    parser.add_argument("--dataset-version", default="1")
    parser.add_argument("--eval-name", default="azure-waf-agent-target-evaluation")
    parser.add_argument("--run-name", default="azure-waf-agent-target-run")
    parser.add_argument("--output", type=Path, default=Path(".foundry/results/latest-agent-eval.json"))
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.endpoint:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT or --endpoint is required.")
    if not args.agent_name:
        raise RuntimeError("FOUNDRY_AGENT_NAME, CLAUDE_HOSTED_AGENT_NAME, or --agent-name is required.")
    if not args.eval_model:
        raise RuntimeError("AZURE_AI_MODEL_DEPLOYMENT_NAME, FOUNDRY_MODEL_NAME, or --eval-model is required.")
    if not args.dataset.exists():
        raise RuntimeError(f"Dataset file not found: {args.dataset}")

    AIProjectClient, DefaultAzureCredential, DataSourceConfigCustom, CreateEvalJSONLRunDataSourceParam, SourceFileID = _import_foundry_sdk()

    project_client = AIProjectClient(endpoint=args.endpoint, credential=DefaultAzureCredential())
    openai_client = project_client.get_openai_client()

    data_id = project_client.datasets.upload_file(
        name=args.dataset_name,
        version=args.dataset_version,
        file_path=str(args.dataset),
    ).id

    data_source_config = DataSourceConfigCustom(
        type="custom",
        item_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "query": {"type": "string"},
                "expected": {"type": "object"},
            },
            "required": ["query"],
        },
        include_sample_schema=True,
    )

    eval_object = openai_client.evals.create(
        name=args.eval_name,
        data_source_config=data_source_config,
        testing_criteria=_testing_criteria(args.eval_model),
    )

    input_messages = {
        "type": "template",
        "template": [
            {
                "type": "message",
                "role": "user",
                "content": {
                    "type": "input_text",
                    "text": "{{item.query}}",
                },
            }
        ],
    }
    target = {
        "type": "azure_ai_agent",
        "name": args.agent_name,
    }
    if args.agent_version:
        target["version"] = args.agent_version

    eval_run = openai_client.evals.runs.create(
        eval_id=eval_object.id,
        name=args.run_name,
        data_source={
            "type": "azure_ai_target_completions",
            "source": SourceFileID(type="file_id", id=data_id),
            "input_messages": input_messages,
            "target": target,
        },
    )

    deadline = time.monotonic() + args.timeout_seconds
    while True:
        run = openai_client.evals.runs.retrieve(run_id=eval_run.id, eval_id=eval_object.id)
        if run.status in {"completed", "failed", "cancelled"}:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"Evaluation run did not finish within {args.timeout_seconds} seconds: {eval_run.id}")
        print(f"Waiting for eval run {eval_run.id}; status={run.status}")
        time.sleep(args.poll_interval)

    output_items = list(openai_client.evals.runs.output_items.list(run_id=run.id, eval_id=eval_object.id))
    result = {
        "evalId": eval_object.id,
        "runId": run.id,
        "status": run.status,
        "reportUrl": getattr(run, "report_url", None),
        "outputItems": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in output_items],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evalId": eval_object.id, "runId": run.id, "status": run.status, "reportUrl": result["reportUrl"]}, indent=2))
    return 0 if run.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
