import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  return proxyToBackend(req, "/api/adk");
}

export async function POST(req: NextRequest) {
  return proxyToBackend(req, "/api/adk");
}
