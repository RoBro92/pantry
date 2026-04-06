import { redirect } from "next/navigation";
import { SetupWizard } from "../../components/setup-wizard";
import { getSession, getSetupStatus, getSetupWizardState } from "../../lib/server-auth";

type SetupPageProps = {
  searchParams: Promise<{
    step?: string;
  }>;
};

export default async function SetupPage({ searchParams }: SetupPageProps) {
  const params = await searchParams;
  const requestedStep = params.step;
  const [session, setupStatus, wizardState] = await Promise.all([
    getSession(),
    getSetupStatus(),
    getSetupWizardState()
  ]);

  if (setupStatus.is_initialized) {
    redirect(session ? "/admin" : "/login");
  }

  const allowedSteps = new Set(wizardState.status.steps.map((step) => step.key));
  const initialStep = allowedSteps.has(requestedStep as never)
    ? (requestedStep as typeof wizardState.status.steps[number]["key"])
    : "welcome";

  return (
    <main className="page-shell setup-page">
      <section className="auth-stage-shell">
        <div className="auth-stage-intro">
          <p className="eyebrow">Self-hosted onboarding</p>
          <h1>Finish first-run setup</h1>
          <p className="lede">
            Create the admin account, stage the first household, and finalize the installation in
            one controlled flow.
          </p>
        </div>
        <SetupWizard initialState={wizardState} initialStep={initialStep} />
      </section>
    </main>
  );
}
