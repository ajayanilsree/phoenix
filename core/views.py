import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

from catalog.models import Category, Product


def home(request):
    categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by("sort_order", "name")[:5]
    featured_products = (
        Product.objects.filter(is_active=True, is_featured=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("featured_order", "-created_at")[:8]
    )
    trending_products = (
        Product.objects.filter(is_active=True, is_trending=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("trending_order", "-created_at")[:8]
    )
    applications = ["Living Room", "Kitchen", "Bedroom", "Office", "Commercial Interiors"]
    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "featured_products": featured_products,
            "trending_products": trending_products,
            "applications": applications,
        },
    )


def about(request):
    return render(request, "core/about.html")


def page_not_found(request, exception=None):
    return render(request, "core/404.html", status=404)


def permission_denied(request, exception=None):
    return render(request, "core/403.html", status=403)


def robots_txt(request):
    return HttpResponse(
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "User-agent: *\n"
        "Disallow: /cart/\n"
        "Disallow: /checkout/\n"
        "Disallow: /auth/\n"
        "Disallow: /account/\n"
        "Disallow: /admin/\n"
        "Disallow: /django-admin/\n"
        "Disallow: /agent/\n"
        "Disallow: /employee/\n"
        "Disallow: /staff/\n"
        "Disallow: /api/\n",
        content_type="text/plain",
    )


def manifest_webmanifest(request):
    manifest = {
        "name": "Phoenix Interior Hub",
        "short_name": "Phoenix",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "theme_color": "#0B2038",
        "background_color": "#F6F4EF",
        "orientation": "any",
        "lang": "en",
        "icons": [
            {"src": f"{settings.STATIC_URL}pwa/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": f"{settings.STATIC_URL}pwa/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": f"{settings.STATIC_URL}pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": f"{settings.STATIC_URL}pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return HttpResponse(json.dumps(manifest), content_type="application/manifest+json")


def service_worker(request):
    script = r"""const CACHE_VERSION = "phoenix-static-v1";
const OFFLINE_PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0B2038"><title>Phoenix Interior Hub</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f6f4ef;color:#0b2038;font:16px system-ui,sans-serif;text-align:center}main{max-width:32rem;padding:2rem}h1{font-family:Georgia,serif;font-size:2.5rem;margin:.5rem 0}p{line-height:1.6;color:#526276}button{border:0;background:#0b2038;color:#fff;padding:.8rem 1.2rem;border-radius:4px;font-weight:700;cursor:pointer}</style></head><body><main><p>PHOENIX INTERIOR HUB</p><h1>You're offline.</h1><p>An internet connection is required to load the latest products, prices and availability.</p><button onclick="location.reload()">Try Again</button></main></body></html>`;

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

const isPrivatePath = (url) => ["/cart/", "/checkout/", "/auth/", "/account/", "/admin/", "/django-admin/", "/agent/", "/employee/", "/staff/", "/api/"].some((path) => url.pathname.startsWith(path));
const isStaticAsset = (url) => url.origin === self.location.origin && url.pathname.startsWith("/static/");

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || isPrivatePath(url) || url.pathname === "/service-worker.js" || url.pathname === "/manifest.webmanifest") return;

  if (isStaticAsset(url)) {
    event.respondWith(caches.open(CACHE_VERSION).then((cache) => cache.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    }))));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => new Response(OFFLINE_PAGE, {headers: {"Content-Type": "text/html; charset=utf-8"}, status: 503})));
  }
});
""";
    return HttpResponse(script, content_type="application/javascript")
