# Why one origin

Komodo serves the whole app from a single origin. Caddy sits in front, hands browser requests for
the UI to the frontend, and forwards `/api` to the backend. To the browser it is all one site.

This is a deliberate choice, and it pays off in three places.

**Cookies.** Auth is a JWT in an HttpOnly cookie. A cookie belongs to an origin. When the page and
the API share one, the cookie travels with every request without special handling. Split them
across two origins and you are into cross-site cookie rules, `SameSite` exceptions, and CORS with
credentials. One origin makes all of that disappear.

**The live stream.** The Now view is fed by Server-Sent Events from the backend. Same-origin, the
`EventSource` connection carries the session cookie like any other request. It just works.

**TLS.** With a domain, Caddy provisions and renews a Let's Encrypt certificate on its own. You set
`APP_ORIGIN` to your hostname and get HTTPS without touching a certificate file.

The cost is one extra container, Caddy, and the discipline of not publishing the backend and
frontend ports directly. That is a small price for an auth story with no sharp edges.

The Kamal path reaches the same place by a different route: there the backend serves the built
frontend itself, so the single origin is the web container. See
[Deploy with Kamal](../how-to/deploy-with-kamal.md).
