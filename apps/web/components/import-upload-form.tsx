"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { ImportDetailResponse } from "../lib/api-types";
import { postFormToApi } from "../lib/client-api";

type ImportUploadFormProps = {
  householdExternalId: string;
};

export function ImportUploadForm({ householdExternalId }: ImportUploadFormProps) {
  const router = useRouter();
  const [sourceType, setSourceType] = useState("structured_import");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a file to upload.");
      setPending(false);
      return;
    }

    formData.set("source_type", sourceType);

    try {
      const response = await postFormToApi<ImportDetailResponse>(
        `/api/households/${householdExternalId}/imports/uploads`,
        formData
      );
      router.push(
        `/app/households/${householdExternalId}/imports/${response.import_job.external_id}`
      );
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Upload failed.");
      setPending(false);
    }
  }

  return (
    <form className="panel import-upload-form" onSubmit={handleSubmit} data-testid="import-upload-form">
      <p className="eyebrow">Create Import</p>
      <h2>Upload for review</h2>
      <p className="section-copy">
        Current foundation supports structured text, CSV, TSV, and JSON parsing. PDF and image
        files are stored safely and tracked, but OCR is still deferred.
      </p>
      <label className="field">
        <span>Import source</span>
        <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
          <option value="structured_import">Structured/manual foundation</option>
          <option value="receipt">Receipt</option>
          <option value="online_order">Online order</option>
        </select>
      </label>
      <div className="recipe-form-grid">
        <label className="field">
          <span>Occurred on</span>
          <input name="occurred_on" type="date" />
        </label>
        <label className="field">
          <span>Upload file</span>
          <input name="file" type="file" accept=".json,.csv,.tsv,.txt,.pdf,.png,.jpg,.jpeg" required />
        </label>
      </div>
      <label className="field">
        <span>Note</span>
        <input name="note" placeholder="Weekly shop, market receipt, pantry count" />
      </label>
      {error ? <p className="error-text">{error}</p> : null}
      <button type="submit" className="primary-button" disabled={pending}>
        {pending ? "Uploading..." : "Create import"}
      </button>
    </form>
  );
}
