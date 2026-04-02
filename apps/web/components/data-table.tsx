import type { ReactNode } from "react";

type DataTableProps = {
  title: string;
  columns: string[];
  children: ReactNode;
};

export function DataTable({ title, columns, children }: DataTableProps) {
  return (
    <section className="panel">
      <p className="eyebrow">{title}</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
    </section>
  );
}

