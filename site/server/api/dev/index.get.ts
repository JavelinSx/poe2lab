// Whether this server signs in by a nick (the sign-in page asks: the production build is the same on the test server).
export default defineEventHandler((e) => {
  requireDev(e);
  return { devLogin: true };
});
