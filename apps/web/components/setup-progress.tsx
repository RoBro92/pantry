import type { SetupStatusResponse } from "../lib/api-types";

type SetupProgressProps = {
  steps: SetupStatusResponse["steps"];
  currentStep: SetupStatusResponse["steps"][number]["key"];
  onJump: (step: SetupStatusResponse["steps"][number]["key"]) => void;
};

export function SetupProgress({ steps, currentStep, onJump }: SetupProgressProps) {
  return (
    <nav className="setup-progress" aria-label="Setup progress">
      {steps.map((step, index) => {
        const stateClass = step.key === currentStep ? "is-current" : step.is_complete ? "is-complete" : "is-upcoming";
        return (
          <button
            key={step.key}
            type="button"
            className={`setup-progress-item ${stateClass}`}
            onClick={() => onJump(step.key)}
          >
            <span className="setup-progress-count">{step.is_complete ? "✓" : index + 1}</span>
            <span className="setup-progress-copy">
              <strong>{step.title}</strong>
              <small>{step.required ? "Required" : "Optional"}</small>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
