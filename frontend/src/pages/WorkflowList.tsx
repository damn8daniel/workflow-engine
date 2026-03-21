import { Link } from "react-router-dom";
import { listWorkflows, deleteWorkflow, type Workflow } from "../api/client";
import { useApi } from "../hooks/useApi";
import StateBadge from "../components/StateBadge";

export default function WorkflowList() {
  const { data, loading, error, refetch } = useApi(
    () => listWorkflows(),
    []
  );

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this workflow?")) return;
    await deleteWorkflow(id);
    refetch();
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading workflows...</div>;
  if (error) return <div className="text-center py-12 text-red-500">Error: {error}</div>;
  if (!data) return null;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Workflows</h1>
        <div className="text-sm text-gray-500">{data.total} workflow(s)</div>
      </div>

      {data.items.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No workflows yet</p>
          <p className="mt-2">Create one via the API: POST /api/v1/workflows</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {data.items.map((wf: Workflow) => (
            <Link
              key={wf.id}
              to={`/workflows/${wf.id}`}
              className="block bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-semibold">{wf.name}</h2>
                  {wf.description && (
                    <p className="text-gray-500 text-sm mt-1">{wf.description}</p>
                  )}
                  <div className="flex gap-2 mt-3">
                    <StateBadge state={wf.is_active ? "success" : "pending"} />
                    {wf.cron_schedule && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                        {wf.cron_schedule}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {wf.dag_definition.tasks?.length ?? 0} tasks
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    handleDelete(wf.id);
                  }}
                  className="text-gray-400 hover:text-red-500 text-sm"
                >
                  Delete
                </button>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
