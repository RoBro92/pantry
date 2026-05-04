import type { NextRequest } from "next/server";
import { appConfig } from "../../../lib/app-config";
import {
  copyAllowedForwardHeaders,
  copyAllowedResponseHeaders,
  isAllowedProxyPath,
  isCrossOriginMutation
} from "../../../lib/proxy-policy";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

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

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<Response> {
  const pathSegments = await resolvePathSegments(context);
  if (!isAllowedProxyPath(pathSegments)) {
    return Response.json({ detail: "API path is not available through this proxy." }, { status: 404 });
  }

  const originMethod =
    request.method === "OPTIONS"
      ? request.headers.get("access-control-request-method") ?? request.method
      : request.method;
  if (
    isCrossOriginMutation(
      originMethod,
      request.nextUrl.origin,
      request.headers.get("origin"),
      request.headers.get("referer")
    )
  ) {
    return Response.json(
      { detail: "Cross-origin mutating API requests are not allowed." },
      { status: 403 }
    );
  }

  const upstreamUrl = buildUpstreamUrl(request, pathSegments);
  const upstreamResponse = await fetch(upstreamUrl, {
    method: request.method,
    headers: copyAllowedForwardHeaders(request.headers),
    body:
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual"
  });
  const responseBody =
    request.method === "HEAD" ||
    upstreamResponse.status === 204 ||
    upstreamResponse.status === 304
      ? null
      : await upstreamResponse.arrayBuffer();

  return new Response(responseBody, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: copyAllowedResponseHeaders(upstreamResponse.headers)
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
