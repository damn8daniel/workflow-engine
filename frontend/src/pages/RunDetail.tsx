import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getRun,
  getWorkflow,
  listTaskInstances,
  getTaskLogs,
  type TaskInstance,
} from "../api/client";
import { useApi } from "../hooks/useApi";
import DAGVisualization from "../components/DAGVisualization";
import StateBadge from "../components/StateBadge";
import { formatDuration } from "../utils/state";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [selectedTask, setSelectedTask] = useState<TaskInstance | null>(null);
  const [logs, setLogs] = useState<{
    log_output: string | null;
    error_message: string | null;
  } | null>(null);

  const { data: run, loading: runLoading } = useApi(
    () => getRun(id!),
    [id]
  );
  const { data: workflow } = useApi(
    () => (run ? getWorkflow(run.workflow_id) : Promise.reject("no run")),
    [run?.workflow_id]
  );
  const { data: taskInstances, refetch: refetchTasks } = useApi(
    () => listTaskInstances(id!),
    [id]
  );

  const handleViewLogs = async (ti: TaskInstance) => {
    setSelectedTask(ti);
    const resp = await getTaskLogs(ti.id);
    setLogs(resp.data);
  };

  if (runLoading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (!run) return <div className="text-center py-12 text-red-500">Run not found</div>;

  const tasks = workflow?.dag_definition.tasks ?? [];

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link
          to={`/workflows/${run.workflow_id}`}
          className="text-blue-600 hover:underline text-sm"
        >
          &larr; Back to Workflow
        </Link>
        <h1 className="text-2xl font-bold mt-2">
          Run <span className="font-mono text-base text-gray-500">{run.id.slice(0, 12)}</span>
        </h1>
        <div className="flex gap-4 mt-2">
          <StateBadge state={run.state} />
          <span className="text-sm text-gray-500">Trigger: {run.trigger_type}</span>
          <span className="text-sm text-gray-500">
            Duration: {formatDuration(run.duration_seconds)}
          </span>
        </div>
      </div>

      {/* DAG with task instance states */}
      {tasks.length > 0 && taskInstances && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-3">DAG Progress</h2>
          <DAGVisualization tasks={tasks} taskInstances={taskInstances} />
        </div>
      )}

      {/* Task Instances Table */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold">Task Instances</h2>
          <button onClick={refetchTasks} className="text-sm text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
        {!taskInstances || taskInstances.length === 0 ? (
          <div className="bg-white p-8 rounded-lg border text-center text-gray-400">
            No task instances
          </div>
        ) : (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Task</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">State</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Attempt</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Duration</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {taskInstances.map((ti: TaskInstance) => (
                  <tr key={ti.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{ti.task_id}</td>
                    <td className="px-4 py-3">
                      <StateBadge state={ti.state} />
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {ti.attempt_number}/{ti.max_retries}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {formatDuration(ti.duration_seconds)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleViewLogs(ti)}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        View Logs
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Logs Panel */}
      {selectedTask && (
        <div className="bg-white rounded-lg border p-5">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-semibold">
              Logs: {selectedTask.task_id} (attempt {selectedTask.attempt_number})
            </h2>
            <button
              onClick={() => {
                setSelectedTask(null);
                setLogs(null);
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              Close
            </button>
          </div>
          {logs ? (
            <div>
              {logs.log_output && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-gray-500 mb-1">Output</h3>
                  <pre className="bg-gray-900 text-green-400 p-4 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap">
                    {logs.log_output}
                  </pre>
                </div>
              )}
              {logs.error_message && (
                <div>
                  <h3 className="text-sm font-medium text-red-500 mb-1">Error</h3>
                  <pre className="bg-red-50 text-red-700 p-4 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap">
                    {logs.error_message}
                  </pre>
                </div>
              )}
              {!logs.log_output && !logs.error_message && (
                <p className="text-gray-400">No logs available</p>
              )}
            </div>
          ) : (
            <p className="text-gray-400">Loading logs...</p>
          )}
        </div>
      )}
    </div>
  );
}
