import { useParams, Link } from "react-router-dom";
import { getWorkflow, listRuns, triggerRun, type WorkflowRun } from "../api/client";
import { useApi } from "../hooks/useApi";
import DAGVisualization from "../components/DAGVisualization";
import StateBadge from "../components/StateBadge";
import { formatDuration } from "../utils/state";

export default function WorkflowDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: workflow, loading: wfLoading } = useApi(
    () => getWorkflow(id!),
    [id]
  );
  const { data: runsData, loading: runsLoading, refetch: refetchRuns } = useApi(
    () => listRuns(id!),
    [id]
  );

  const handleTrigger = async () => {
    await triggerRun(id!);
    refetchRuns();
  };

  if (wfLoading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (!workflow) return <div className="text-center py-12 text-red-500">Workflow not found</div>;

  const tasks = workflow.dag_definition.tasks ?? [];

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <Link to="/" className="text-blue-600 hover:underline text-sm">&larr; All Workflows</Link>
          <h1 className="text-2xl font-bold mt-2">{workflow.name}</h1>
          {workflow.description && (
            <p className="text-gray-500 mt-1">{workflow.description}</p>
          )}
        </div>
        <button
          onClick={handleTrigger}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          Trigger Run
        </button>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-xs text-gray-500 uppercase">Status</div>
          <StateBadge state={workflow.is_active ? "success" : "pending"} />
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-xs text-gray-500 uppercase">Tasks</div>
          <div className="text-lg font-semibold">{tasks.length}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-xs text-gray-500 uppercase">Max Retries</div>
          <div className="text-lg font-semibold">{workflow.max_retries}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-xs text-gray-500 uppercase">Schedule</div>
          <div className="text-lg font-semibold">{workflow.cron_schedule ?? "Manual"}</div>
        </div>
      </div>

      {/* DAG Visualization */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-3">DAG</h2>
        {tasks.length > 0 ? (
          <DAGVisualization tasks={tasks} />
        ) : (
          <div className="bg-white p-8 rounded-lg border text-center text-gray-400">
            No tasks defined
          </div>
        )}
      </div>

      {/* Run History */}
      <div>
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold">Run History</h2>
          <button onClick={refetchRuns} className="text-sm text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
        {runsLoading ? (
          <div className="text-gray-500">Loading runs...</div>
        ) : !runsData || runsData.items.length === 0 ? (
          <div className="bg-white p-8 rounded-lg border text-center text-gray-400">
            No runs yet
          </div>
        ) : (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Run ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">State</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Trigger</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Duration</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {runsData.items.map((run: WorkflowRun) => (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/runs/${run.id}`}
                        className="text-blue-600 hover:underline font-mono text-xs"
                      >
                        {run.id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <StateBadge state={run.state} />
                    </td>
                    <td className="px-4 py-3 text-gray-500">{run.trigger_type}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {formatDuration(run.duration_seconds)}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
