"use client";

import { useRouter } from "next/navigation";
import { appConfig } from "../lib/app-config";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    await fetch(`${appConfig.apiBaseUrl}/api/auth/logout`, {
      method: "POST",
      credentials: "include"
    });

    router.push("/login");
    router.refresh();
  }

  return (
    <button type="button" className="ghost-button" onClick={handleLogout}>
      Logout
    </button>
  );
}

