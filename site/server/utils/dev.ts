// Signing in by a nick and the example builds: in `npm run dev`, and on the local test server (`npm run test-server`
// gives wrangler TEST_SERVER=1). The real site has neither - its routes answer 404.
import type { H3Event } from "h3";

export const devAllowed = (e: H3Event) => import.meta.dev || cf(e).TEST_SERVER === "1";
export function requireDev(e: H3Event) {
  if (!devAllowed(e)) throw createError({ statusCode: 404 });
}
