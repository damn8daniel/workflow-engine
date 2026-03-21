/** Map task/run states to Tailwind color classes. */
export const stateColor: Record<string, string> = {
  pending: "bg-gray-200 text-gray-800",
  queued: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  retry: "bg-orange-100 text-orange-800",
  skipped: "bg-gray-100 text-gray-600",
  upstream_failed: "bg-red-50 text-red-600",
  cancelled: "bg-gray-300 text-gray-700",
};

export function getStateColor(state: string): string {
  return stateColor[state] ?? "bg-gray-100 text-gray-700";
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(0);
  return `${mins}m ${secs}s`;
}
