const destinations = new Set([
  "/workspace", "/workspace?action=new", "/workspace?view=activity", "/workspace?view=verifications",
  "/profile", "/handoffs", "/advisor", "/admin",
]);

export function accountDestination(value: unknown): string {
  return typeof value === "string" && destinations.has(value) ? value : "/workspace";
}

export function accountHref(mode: "sign-in" | "sign-up", next = "/workspace") {
  const destination = accountDestination(next);
  return `/${mode}` + (destination === "/workspace" ? "" : "?next=" + encodeURIComponent(destination));
}
