// A change asked by the site's own page only: another site's page cannot post in the player's name (its Origin is
// another host). The app sends a token (Bearer) instead of a cookie, and is let through to the routes made for it.
export default defineEventHandler((e) => {
  const path = e.path || "";
  if (!path.startsWith("/api/") || ["GET", "HEAD", "OPTIONS"].includes(e.method)) return;
  if ((getHeader(e, "authorization") || "").startsWith("Bearer ") || path.startsWith("/api/device/start") || path.startsWith("/api/device/token")) return;
  const origin = getHeader(e, "origin");
  const host = getHeader(e, "host");
  if (origin && host && new URL(origin).host !== host) throw createError({ statusCode: 403, message: "Запрос с чужой страницы" });
});
