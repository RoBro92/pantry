"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationGroupSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type PantryRoomDialogProps = {
  householdExternalId: string;
  rooms: PantryLocationGroupSummary[];
  onClose: () => void;
};

type FormStatus = {
  pending: boolean;
  error: string | null;
  success: string | null;
};

const EMPTY_STATUS: FormStatus = {
  pending: false,
  error: null,
  success: null,
};

export function PantryRoomDialog({
  householdExternalId,
  rooms,
  onClose,
}: PantryRoomDialogProps) {
  const router = useRouter();
  const [roomStatus, setRoomStatus] = useState<FormStatus>(EMPTY_STATUS);
  const [locationStatus, setLocationStatus] = useState<FormStatus>(EMPTY_STATUS);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
    path: string,
    payload: Record<string, unknown>,
    setStatus: (status: FormStatus) => void,
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    setStatus({ pending: true, error: null, success: null });

    try {
      await postToApi(path, payload);
      form.reset();
      setStatus({ pending: false, error: null, success: "Saved." });
      router.refresh();
    } catch (requestError) {
      setStatus({
        pending: false,
        error: requestError instanceof Error ? requestError.message : "Request failed.",
        success: null,
      });
    }
  }

  return (
    <ModalShell
      title="Manage rooms"
      description="Create a room such as Kitchen or Garage, then add storage locations inside it."
      onClose={onClose}
    >
      <div className="content-grid">
        <form
          className="panel embedded-panel"
          data-testid="pantry-create-room-form"
          onSubmit={(event) =>
            handleSubmit(
              event,
              `/api/households/${householdExternalId}/location-groups`,
              { name: String(new FormData(event.currentTarget).get("name") ?? "") },
              setRoomStatus,
            )
          }
        >
          <p className="eyebrow">Rooms</p>
          <h3>Create room</h3>
          <label className="field">
            <span>Room name</span>
            <input name="name" placeholder="Kitchen" required />
          </label>
          {roomStatus.error ? <p className="error-text">{roomStatus.error}</p> : null}
          {roomStatus.success ? <p className="status-note">{roomStatus.success}</p> : null}
          <button type="submit" className="primary-button" disabled={roomStatus.pending}>
            {roomStatus.pending ? "Saving..." : "Add room"}
          </button>
        </form>

        <form
          className="panel embedded-panel"
          data-testid="pantry-create-location-form"
          onSubmit={(event) =>
            handleSubmit(
              event,
              `/api/households/${householdExternalId}/locations`,
              {
                location_group_external_id: String(
                  new FormData(event.currentTarget).get("location_group_external_id") ?? "",
                ),
                name: String(new FormData(event.currentTarget).get("name") ?? ""),
              },
              setLocationStatus,
            )
          }
        >
          <p className="eyebrow">Storage locations</p>
          <h3>Add storage location</h3>
          <label className="field">
            <span>Room</span>
            <select name="location_group_external_id" required>
              <option value="">Select a room</option>
              {rooms.map((room) => (
                <option key={room.external_id} value={room.external_id}>
                  {room.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Storage location</span>
            <input name="name" placeholder="Top shelf" required />
          </label>
          {rooms.length === 0 ? <p className="section-copy">Create a room first.</p> : null}
          {locationStatus.error ? <p className="error-text">{locationStatus.error}</p> : null}
          {locationStatus.success ? <p className="status-note">{locationStatus.success}</p> : null}
          <button
            type="submit"
            className="primary-button"
            disabled={locationStatus.pending || rooms.length === 0}
          >
            {locationStatus.pending ? "Saving..." : "Add storage location"}
          </button>
        </form>
      </div>
    </ModalShell>
  );
}
