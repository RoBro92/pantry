"use client";

type PantryBarcodeFieldProps = {
  value: string;
  inputName: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  onSubmitValue?: (value: string) => void;
  onLookup: () => void;
  onScan: () => void;
  lookupPending: boolean;
  lookupDisabled: boolean;
  lookupLabel?: string;
  helperText: string;
  placeholder?: string;
};

export function PantryBarcodeField({
  value,
  inputName,
  onChange,
  onBlur,
  onSubmitValue,
  onLookup,
  onScan,
  lookupPending,
  lookupDisabled,
  lookupLabel = "Look up OFF data",
  helperText,
  placeholder = "5000111046244",
}: PantryBarcodeFieldProps) {
  return (
    <label className="field">
      <span>Barcode</span>
      <div className="barcode-field">
        <div className="barcode-input-row">
          <input
            name={inputName}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onBlur={onBlur}
            onKeyDown={(event) => {
              if (event.key !== "Enter" || !onSubmitValue) {
                return;
              }
              event.preventDefault();
              onSubmitValue(event.currentTarget.value);
            }}
            placeholder={placeholder}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            inputMode="numeric"
          />
          <button
            type="button"
            className="ghost-button compact-button barcode-scan-button"
            onClick={onScan}
            aria-label="Scan barcode"
            title="Scan barcode"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path
                d="M4 5.5V4h2.5M13.5 4H16v1.5M16 14.5V16h-2.5M6.5 16H4v-1.5M7.5 5v10M10 5v10M12.5 5v10"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.6"
              />
            </svg>
          </button>
        </div>
        <div className="barcode-field-footer">
          <button
            type="button"
            className="ghost-button compact-button"
            disabled={lookupPending || lookupDisabled}
            onClick={onLookup}
          >
            {lookupPending ? "Looking up..." : lookupLabel}
          </button>
          <p className="helper-text">{helperText}</p>
        </div>
      </div>
    </label>
  );
}
