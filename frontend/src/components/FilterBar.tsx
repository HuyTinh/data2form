import type { ChangeEvent } from 'react';

export interface FilterOption {
  label: string;
  value: string;
}

interface FilterBarProps {
  statuses: FilterOption[];
  selectedStatus: string;
  onStatusChange: (status: string) => void;
  allLabel?: string;
  label?: string;
}

export default function FilterBar({
  statuses,
  selectedStatus,
  onStatusChange,
  allLabel = 'All statuses',
  label = 'Status',
}: FilterBarProps) {
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onStatusChange(event.target.value);
  };

  return (
    <div className="filter-bar">
      <label className="filter-bar__label">
        <span>{label}</span>
        <select
          className="filter-bar__select"
          value={selectedStatus}
          onChange={handleChange}
        >
          <option value="">{allLabel}</option>
          {statuses.map((status) => (
            <option key={status.value} value={status.value}>
              {status.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
