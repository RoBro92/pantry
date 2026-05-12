export default function AdminLoading() {
  return (
    <main className="page-shell dashboard-page-shell">
      <div className="shell-grid">
        <aside className="sidebar panel" aria-hidden="true">
          <p className="eyebrow">Pantro</p>
          <h1 className="shell-title">Loading</h1>
          <p className="sidebar-copy">Preparing installation tools.</p>
        </aside>
        <section className="shell-content">
          <section className="panel">
            <p className="eyebrow">Admin Dashboard</p>
            <h1>Loading installation console</h1>
            <p className="section-copy">
              Pantro is loading operator status and administrative tools.
            </p>
          </section>
        </section>
      </div>
    </main>
  );
}
