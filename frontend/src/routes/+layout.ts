// Mino is a client-rendered SPA (all data is fetched in the browser, behind
// the cookie session). Turn off SSR and prerendering; the static adapter emits
// a single index.html the backend serves for every route.
export const ssr = false;
export const prerender = false;
