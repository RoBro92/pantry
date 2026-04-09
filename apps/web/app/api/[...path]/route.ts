import type { NextRequest } from "next/server";
import { appConfig } from "../../../lib/app-config";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const hopByHopHeaders = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade"
]);

async function resolvePathSegments(context: RouteContext): Promise<string[]> {
  const params = await context.params;
  return params.path;
}

function buildUpstreamUrl(request: NextRequest, pathSegments: string[]): URL {
  const upstreamUrl = new URL(
    `/api/${pathSegments.map(encodeURIComponent).join("/")}`,
    appConfig.internalApiBaseUrl
  );
  upstreamUrl.search = request.nextUrl.search;
  return upstreamUrl;
}

function copyForwardHeaders(headers: Headers): Headers {
  const forwardedHeaders = new Headers(headers);

  hopByHopHeaders.forEach((header) => {
    forwardedHeaders.delete(header);
  });
  forwardedHeaders.delete("host");

  return forwardedHeaders;
}

function copyResponseHeaders(headers: Headers): Headers {
  const responseHeaders = new Headers(headers);

  hopByHopHeaders.forEach((header) => {
    responseHeaders.delete(header);
  });

  return responseHeaders;
}

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<Response> {
  const pathSegments = await resolvePathSegments(context);
  const upstreamUrl = buildUpstreamUrl(request, pathSegments);
  const upstreamResponse = await fetch(upstreamUrl, {
    method: request.method,
    headers: copyForwardHeaders(request.headers),
    body:
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual"
  });

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: copyResponseHeaders(upstreamResponse.headers)
  });
}

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}

export async function HEAD(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyRequest(request, context);
}
