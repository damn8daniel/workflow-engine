import { getStateColor } from "../utils/state";

interface Props {
  state: string;
}

export default function StateBadge({ state }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStateColor(state)}`}
    >
      {state}
    </span>
  );
}
