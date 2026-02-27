import { NextRequest } from "next/server";
import { proxyAnalysis } from "../../../../lib/essentia-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ analysis: string }> }
) {
  const { analysis } = await context.params;
  return proxyAnalysis(request, analysis);
}
