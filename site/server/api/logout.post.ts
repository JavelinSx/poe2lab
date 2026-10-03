// Signing out of this browser.
export default defineEventHandler(async (e) => {
  await endSession(e);
  return { ok: true };
});
