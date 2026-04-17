"use client";

import { useRouter } from "next/navigation";
import { appConfig } from "../lib/app-config";

export function LogoutButton() {
  return <LogoutButtonInner />;
}

type LogoutButtonProps = {
  className?: string;
};

export function LogoutButtonInner({ className }: LogoutButtonProps = {}) {
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
    <button type="button" className={className ?? "ghost-button"} onClick={handleLogout}>
      Logout
    </button>
  );
}
