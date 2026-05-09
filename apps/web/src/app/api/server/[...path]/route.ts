import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.SERVER_API_BASE_URL ?? "http://127.0.0.1:8100";

type Params = {
  params: Promise<{
    path: string[];
  }>;
};

async function proxy(request: NextRequest, { params }: Params) {
  const { path: routePath } = await params;
  const path = routePath.join("/");
  const target = `${API_BASE}/api/${path}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
    redirect: "manual",
  });

  const responseHeaders = new Headers(response.headers);
  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
