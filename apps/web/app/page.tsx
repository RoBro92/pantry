import { redirect } from "next/navigation";
import { getSession, getSetupStatus } from "../lib/server-auth";

export default async function HomePage() {
  const [session, setupStatus] = await Promise.all([getSession(), getSetupStatus()]);

  if (!setupStatus.is_initialized) {
    redirect("/setup");
  }

  if (session) {
    redirect("/app");
  }

  redirect("/login");
}
