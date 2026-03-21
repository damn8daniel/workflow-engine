import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

const client = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  dag_definition: { tasks: TaskDef[] };
  is_active: boolean;
  cron_schedule: string | null;
  max_retries: number;
  created_at: string;
  updated_at: string;
  tags: Record<string, unknown> | null;
}

export interface TaskDef {
  task_id: string;
  callable_name: string;
  depends_on: string[];
  args: unknown[];
  kwargs: Record<string, unknown>;
  max_retries: number;
  timeout_seconds: number;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  state: string;
  trigger_type: string;
  config: Record<string, unknown> | null;
  execution_date: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface TaskInstance {
  id: string;
  run_id: string;
  task_id: string;
  state: string;
  attempt_number: number;
  max_retries: number;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  log_output: string | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// Workflows
export const listWorkflows = (page = 1) =>
  client.get<PaginatedResponse<Workflow>>("/workflows", { params: { page } });

export const getWorkflow = (id: string) =>
  client.get<Workflow>(`/workflows/${id}`);

export const createWorkflow = (data: Partial<Workflow>) =>
  client.post<Workflow>("/workflows", data);

export const deleteWorkflow = (id: string) =>
  client.delete(`/workflows/${id}`);

// Runs
export const listRuns = (workflowId: string, page = 1) =>
  client.get<PaginatedResponse<WorkflowRun>>(`/workflows/${workflowId}/runs`, {
    params: { page },
  });

export const triggerRun = (workflowId: string) =>
  client.post<WorkflowRun>(`/workflows/${workflowId}/runs`);

export const getRun = (runId: string) =>
  client.get<WorkflowRun>(`/workflows/runs/${runId}`);

// Task instances
export const listTaskInstances = (runId: string) =>
  client.get<TaskInstance[]>(`/workflows/runs/${runId}/tasks`);

export const getTaskLogs = (taskInstanceId: string) =>
  client.get<{ task_id: string; log_output: string | null; error_message: string | null }>(
    `/workflows/tasks/${taskInstanceId}/logs`
  );

export default client;
