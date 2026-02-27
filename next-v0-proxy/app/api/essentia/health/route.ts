import { proxyHealth } from "../../../../lib/essentia-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return proxyHealth();
}
