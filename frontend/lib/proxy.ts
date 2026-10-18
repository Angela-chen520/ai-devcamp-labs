import { GoogleAuth } from "google-auth-library";
import { NextRequest, NextResponse } from "next/server";

const auth = new GoogleAuth({
  scopes: ["https://www.googleapis.com/auth/cloud-platform"],
});

/**
 * Proxies an incoming NextRequest to the backend (local or Agent Runtime).
 * Automatically acquires and attaches a Google Cloud bearer token when targeting Google Cloud.
 */
export async function proxyToBackend(req: NextRequest, subpath: string): Promise<Response> {
  const origin = (process.env.ADK_BACKEND_ORIGIN || "http://localhost:8000").replace(/\/+$/, "");
  const targetUrl = `${origin}${subpath.startsWith("/") ? subpath : `/${subpath}`}`;

  const headers = new Headers();
  
  // Forward essential headers
  const forwardHeaderList = ["content-type", "accept", "user-agent"];
  for (const h of forwardHeaderList) {
    const val = req.headers.get(h);
    if (val) {
      headers.set(h, val);
    }
  }

  // Security: Only attach Google Cloud Bearer token if targeting a Google Cloud endpoint
  if (origin.includes("googleapis.com")) {
    try {
      const client = await auth.getClient();
      const token = (await client.getAccessToken()).token;
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    } catch (err) {
      console.error("[Proxy] Failed to acquire Google Cloud access token:", err);
      return new NextResponse("Authentication failed", { status: 502 });
    }
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const fetchOptions: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    cache: "no-store",
  };

  if (hasBody) {
    fetchOptions.body = req.body;
    fetchOptions.duplex = "half";
  }

  try {
    const upstreamRes = await fetch(targetUrl, fetchOptions);

    // Forward upstream response headers (Content-Type, Cache-Control, etc.)
    const resHeaders = new Headers();
    const contentType = upstreamRes.headers.get("content-type");
    if (contentType) {
      resHeaders.set("content-type", contentType);
    }
    const cacheControl = upstreamRes.headers.get("cache-control");
    if (cacheControl) {
      resHeaders.set("cache-control", cacheControl);
    } else {
      resHeaders.set("cache-control", "no-cache");
    }

    return new Response(upstreamRes.body, {
      status: upstreamRes.status,
      statusText: upstreamRes.statusText,
      headers: resHeaders,
    });
  } catch (err) {
    console.error(`[Proxy] Error forwarding request to ${targetUrl}:`, err);
    return new NextResponse(`Proxy error: ${String(err)}`, { status: 502 });
  }
}
