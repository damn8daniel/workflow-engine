"""Unit tests for the DAG DSL."""

import pytest

from app.dsl.dag import DAG, Task


class TestTask:
    def test_rshift_creates_dependency(self):
        t1 = Task(task_id="a", callable_name="builtin.echo")
        t2 = Task(task_id="b", callable_name="builtin.echo")
        t1 >> t2
        assert t2.depends_on == ["a"]

    def test_lshift_creates_dependency(self):
        t1 = Task(task_id="a", callable_name="builtin.echo")
        t2 = Task(task_id="b", callable_name="builtin.echo")
        t2 << t1
        assert t2.depends_on == ["a"]

    def test_chaining(self):
        t1 = Task(task_id="a", callable_name="builtin.echo")
        t2 = Task(task_id="b", callable_name="builtin.echo")
        t3 = Task(task_id="c", callable_name="builtin.echo")
        t1 >> t2 >> t3
        assert t2.depends_on == ["a"]
        assert t3.depends_on == ["b"]

    def test_fan_out(self):
        root = Task(task_id="root", callable_name="builtin.echo")
        c1 = Task(task_id="c1", callable_name="builtin.echo")
        c2 = Task(task_id="c2", callable_name="builtin.echo")
        root >> [c1, c2]
        assert c1.depends_on == ["root"]
        assert c2.depends_on == ["root"]

    def test_to_dict(self):
        t = Task(task_id="x", callable_name="builtin.echo", kwargs={"msg": "hi"})
        d = t.to_dict()
        assert d["task_id"] == "x"
        assert d["callable_name"] == "builtin.echo"
        assert d["kwargs"] == {"msg": "hi"}


class TestDAG:
    def test_context_manager(self):
        with DAG("test") as dag:
            t1 = Task(task_id="a", callable_name="builtin.echo")
            dag.add_task(t1)
        assert "a" in dag.tasks

    def test_topological_sort_linear(self):
        dag = DAG("linear")
        t1 = Task(task_id="a", callable_name="x")
        t2 = Task(task_id="b", callable_name="x", depends_on=["a"])
        t3 = Task(task_id="c", callable_name="x", depends_on=["b"])
        dag.add_task(t1)
        dag.add_task(t2)
        dag.add_task(t3)
        order = dag.topological_sort()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_sort_diamond(self):
        dag = DAG("diamond")
        dag.add_task(Task(task_id="a", callable_name="x"))
        dag.add_task(Task(task_id="b", callable_name="x", depends_on=["a"]))
        dag.add_task(Task(task_id="c", callable_name="x", depends_on=["a"]))
        dag.add_task(Task(task_id="d", callable_name="x", depends_on=["b", "c"]))
        order = dag.topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_cycle_detection(self):
        dag = DAG("cycle")
        dag.add_task(Task(task_id="a", callable_name="x", depends_on=["b"]))
        dag.add_task(Task(task_id="b", callable_name="x", depends_on=["a"]))
        with pytest.raises(ValueError, match="cycle"):
            dag.topological_sort()

    def test_get_ready_tasks(self):
        dag = DAG("ready")
        dag.add_task(Task(task_id="a", callable_name="x"))
        dag.add_task(Task(task_id="b", callable_name="x", depends_on=["a"]))
        dag.add_task(Task(task_id="c", callable_name="x"))
        # Initially a and c are ready
        assert set(dag.get_ready_tasks(set())) == {"a", "c"}
        # After a completes, b becomes ready
        assert set(dag.get_ready_tasks({"a"})) == {"b", "c"}
        # After all complete, nothing ready
        assert dag.get_ready_tasks({"a", "b", "c"}) == []

    def test_duplicate_task_id_raises(self):
        dag = DAG("dup")
        dag.add_task(Task(task_id="a", callable_name="x"))
        with pytest.raises(ValueError, match="Duplicate"):
            dag.add_task(Task(task_id="a", callable_name="y"))

    def test_serialization_roundtrip(self):
        dag = DAG("rt")
        dag.add_task(Task(task_id="a", callable_name="x"))
        dag.add_task(Task(task_id="b", callable_name="y", depends_on=["a"]))
        data = dag.to_dict()
        dag2 = DAG.from_dict("rt2", data)
        assert set(dag2.tasks.keys()) == {"a", "b"}
        assert dag2.tasks["b"].depends_on == ["a"]

    def test_validate_empty(self):
        dag = DAG("empty")
        errors = dag.validate()
        assert any("no tasks" in e for e in errors)

    def test_validate_missing_dep(self):
        dag = DAG("missing")
        dag.add_task(Task(task_id="a", callable_name="x", depends_on=["ghost"]))
        errors = dag.validate()
        assert any("unknown task" in e for e in errors)
