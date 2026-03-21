"""Example DAG definitions using the Python DSL.

Run this file directly to see the serialized output:
    python -m app.dsl.examples
"""

from app.dsl.dag import DAG, Task


def etl_pipeline() -> DAG:
    """Classic Extract-Transform-Load pipeline."""
    with DAG(
        "etl_pipeline",
        description="Daily ETL pipeline that extracts data, transforms it, and loads to warehouse",
        cron_schedule="0 2 * * *",  # Every day at 2 AM
        tags={"team": "data-eng", "priority": "high"},
    ) as dag:
        extract = Task(task_id="extract", callable_name="builtin.echo", kwargs={"message": "Extracting data..."})
        dag.add_task(extract)

        validate = Task(task_id="validate", callable_name="builtin.echo", kwargs={"message": "Validating schema..."})
        dag.add_task(validate)

        transform = Task(task_id="transform", callable_name="builtin.echo", kwargs={"message": "Transforming data..."})
        dag.add_task(transform)

        load = Task(task_id="load", callable_name="builtin.echo", kwargs={"message": "Loading to warehouse..."})
        dag.add_task(load)

        notify = Task(task_id="notify", callable_name="builtin.echo", kwargs={"message": "Sending notification..."})
        dag.add_task(notify)

        # Define the DAG structure:
        #   extract -> validate -> transform -> load -> notify
        extract >> validate >> transform >> load >> notify

    return dag


def parallel_pipeline() -> DAG:
    """Pipeline with parallel branches that converge."""
    with DAG(
        "parallel_pipeline",
        description="Pipeline demonstrating parallel execution with fan-out/fan-in",
        tags={"team": "platform"},
    ) as dag:
        start = Task(task_id="start", callable_name="builtin.echo", kwargs={"message": "Starting..."})
        dag.add_task(start)

        branch_a = Task(task_id="branch_a", callable_name="builtin.sleep", kwargs={"seconds": 2})
        dag.add_task(branch_a)

        branch_b = Task(task_id="branch_b", callable_name="builtin.sleep", kwargs={"seconds": 3})
        dag.add_task(branch_b)

        branch_c = Task(task_id="branch_c", callable_name="builtin.sleep", kwargs={"seconds": 1})
        dag.add_task(branch_c)

        merge = Task(task_id="merge", callable_name="builtin.echo", kwargs={"message": "Merging results..."})
        dag.add_task(merge)

        finalize = Task(task_id="finalize", callable_name="builtin.echo", kwargs={"message": "Done!"})
        dag.add_task(finalize)

        # Fan-out from start, fan-in at merge
        start >> [branch_a, branch_b, branch_c]
        [branch_a, branch_b, branch_c] >> merge  # type: ignore[operator]
        merge >> finalize

    return dag


def math_pipeline() -> DAG:
    """Pipeline demonstrating XCom data passing between tasks."""
    with DAG(
        "math_pipeline",
        description="Demonstrates inter-task data passing via XCom",
    ) as dag:
        add1 = Task(task_id="add_step1", callable_name="builtin.add", kwargs={"a": 10, "b": 20})
        dag.add_task(add1)

        add2 = Task(task_id="add_step2", callable_name="builtin.add", kwargs={"a": 5, "b": 15})
        dag.add_task(add2)

        final = Task(task_id="report", callable_name="builtin.echo", kwargs={"message": "Computation complete"})
        dag.add_task(final)

        [add1, add2] >> final  # type: ignore[operator]

    return dag


if __name__ == "__main__":
    import json

    for factory in [etl_pipeline, parallel_pipeline, math_pipeline]:
        dag = factory()
        print(f"\n{'='*60}")
        print(f"DAG: {dag.name}")
        print(f"Description: {dag.description}")
        print(f"Topological order: {dag.topological_sort()}")
        print(f"Validation: {dag.validate() or 'OK'}")
        print(json.dumps(dag.to_dict(), indent=2))
