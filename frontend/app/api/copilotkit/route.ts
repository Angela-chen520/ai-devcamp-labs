import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

// Bridges the browser to the ADK backend's AG-UI endpoint.
// In Step 6, when ADK_BACKEND_ORIGIN is set, route through our own /api/adk proxy handler
// so that ADC Google Cloud bearer tokens are attached server-side without leaking to client.
const port = process.env.PORT || "3000";
const defaultAdkUrl = process.env.ADK_BACKEND_ORIGIN
  ? `http://127.0.0.1:${port}/api/adk`
  : "http://localhost:8000/api/adk";

const runtime = new CopilotRuntime({
  agents: {
    social_poster: new HttpAgent({
      url: process.env.ADK_BACKEND_URL || defaultAdkUrl,
    }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new ExperimentalEmptyAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
