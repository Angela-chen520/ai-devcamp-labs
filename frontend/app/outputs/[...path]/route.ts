import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  if (!path || path.length === 0) {
    return new NextResponse("Not Found", { status: 404 });
  }

  // Security: prevent path traversal attacks (e.g. '../', '..%2F')
  for (const segment of path) {
    if (segment === ".." || segment.includes("/") || segment.includes("\\")) {
      return new NextResponse("Invalid path segment", { status: 400 });
    }
  }

  const relativePath = `/outputs/${path.join("/")}`;
  return proxyToBackend(req, relativePath);
}
