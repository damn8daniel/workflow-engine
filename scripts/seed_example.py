#!/usr/bin/env python3
"""Seed the database with example workflows via the REST API."""

import httpx
import sys

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api/v1"

WORKFLOWS = [
    {
        "name": "etl_pipeline",
        "description": "Daily ETL: extract, validate, transform, load, notify",
        "cron_schedule": "0 2 * * *",
        "tags": {"team": "data-eng"},
        "dag_definition": {
            "tasks": [
                {"task_id": "extract", "callable_name": "builtin.echo", "kwargs": {"message": "Extracting data from S3..."}, "depends_on": []},
                {"task_id": "validate", "callable_name": "builtin.echo", "kwargs": {"message": "Validating schema..."}, "depends_on": ["extract"]},
                {"task_id": "transform", "callable_name": "builtin.echo", "kwargs": {"message": "Transforming data..."}, "depends_on": ["validate"]},
                {"task_id": "load", "callable_name": "builtin.echo", "kwargs": {"message": "Loading to warehouse..."}, "depends_on": ["transform"]},
                {"task_id": "notify", "callable_name": "builtin.echo", "kwargs": {"message": "Sending Slack notification..."}, "depends_on": ["load"]},
            ]
        },
    },
    {
        "name": "parallel_pipeline",
        "description": "Fan-out/fan-in demo with parallel branches",
        "tags": {"team": "platform"},
        "dag_definition": {
            "tasks": [
                {"task_id": "start", "callable_name": "builtin.echo", "kwargs": {"message": "Starting..."}, "depends_on": []},
                {"task_id": "branch_a", "callable_name": "builtin.sleep", "kwargs": {"seconds": 2}, "depends_on": ["start"]},
                {"task_id": "branch_b", "callable_name": "builtin.sleep", "kwargs": {"seconds": 3}, "depends_on": ["start"]},
                {"task_id": "branch_c", "callable_name": "builtin.sleep", "kwargs": {"seconds": 1}, "depends_on": ["start"]},
                {"task_id": "merge", "callable_name": "builtin.echo", "kwargs": {"message": "Merging..."}, "depends_on": ["branch_a", "branch_b", "branch_c"]},
                {"task_id": "finalize", "callable_name": "builtin.echo", "kwargs": {"message": "Done!"}, "depends_on": ["merge"]},
            ]
        },
    },
    {
        "name": "math_pipeline",
        "description": "Demonstrates XCom data passing between tasks",
        "dag_definition": {
            "tasks": [
                {"task_id": "add_step1", "callable_name": "builtin.add", "kwargs": {"a": 10, "b": 20}, "depends_on": []},
                {"task_id": "add_step2", "callable_name": "builtin.add", "kwargs": {"a": 5, "b": 15}, "depends_on": []},
                {"task_id": "report", "callable_name": "builtin.echo", "kwargs": {"message": "Computation complete"}, "depends_on": ["add_step1", "add_step2"]},
            ]
        },
    },
]


def main():
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        for wf_data in WORKFLOWS:
            resp = client.post("/workflows", json=wf_data)
            if resp.status_code == 201:
                wf = resp.json()
                print(f"Created workflow: {wf['name']} (id={wf['id'][:8]})")
            elif resp.status_code == 409:
                print(f"Workflow '{wf_data['name']}' already exists, skipping")
            else:
                print(f"Error creating '{wf_data['name']}': {resp.status_code} {resp.text}")

    print("\nDone! Visit http://localhost:3000 to see workflows.")


if __name__ == "__main__":
    main()
