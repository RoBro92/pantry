import { redirect } from "next/navigation";
import { LoginForm } from "../../../components/login-form";
import { getSession } from "../../../lib/server-auth";

export default async function LoginPage() {
  const session = await getSession();
  if (session) {
    redirect("/app");
  }

  return (
    <main className="page-shell">
      <section className="hero compact-hero">
        <p className="eyebrow">Milestone 1</p>
        <h1>Pantry Login</h1>
        <p className="lede">
          Session-based authentication for the self-hosted Pantry admin surface.
        </p>
      </section>
      <div className="auth-grid">
        <LoginForm />
        <section className="panel">
          <p className="eyebrow">Current scope</p>
          <ul>
            <li>Password login</li>
            <li>Platform admin session shell</li>
            <li>Household membership-aware API foundations</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
