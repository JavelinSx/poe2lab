// Who is signed in, before the first page is drawn: the header, the review form and the cabinet depend on it.
export default defineNuxtPlugin(async () => { await loadMe(); });
