import { NextRequest, NextResponse } from "next/server";

const ALLOWED_ANALYSES = new Set([
  "rhythm",
  "structure",
  "classification",
  "tonal",
  "vocals",
  "full"
]);

function getProxyConfig() {
  const baseUrl = process.env.ESSENTIA_API_BASE_URL;
  const apiKey = process.env.ESSENTIA_API_KEY;

  if (!baseUrl || !apiKey) {
    throw new Error("Missing ESSENTIA_API_BASE_URL or ESSENTIA_API_KEY");
  }

  return { baseUrl, apiKey };
}

function joinUrl(baseUrl: string, pathname: string): string {
  const base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  return `${base}${pathname}`;
}

export async function proxyAnalysis(
  request: NextRequest,
  analysis: string
): Promise<NextResponse> {
  if (!ALLOWED_ANALYSES.has(analysis)) {
    return NextResponse.json({ error: "Unknown analysis endpoint" }, { status: 404 });
  }

  let config: { baseUrl: string; apiKey: string };
  try {
    config = getProxyConfig();
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Proxy config error" },
      { status: 500 }
    );
  }

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Missing file field in multipart form data" }, { status: 400 });
  }

  const upstreamBody = new FormData();
  upstreamBody.append("file", file, file.name || "upload.bin");

  const query = request.nextUrl.searchParams.toString();
  const endpointUrl = joinUrl(
    config.baseUrl,
    `/analyze/${analysis}${query ? `?${query}` : ""}`
  );

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(endpointUrl, {
      method: "POST",
      headers: {
        "X-API-Key": config.apiKey
      },
      body: upstreamBody,
      cache: "no-store"
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to reach upstream Essentia API", detail: String(error) },
      { status: 502 }
    );
  }

  const text = await upstreamResponse.text();
  const contentType =
    upstreamResponse.headers.get("content-type") ?? "application/json; charset=utf-8";

  return new NextResponse(text, {
    status: upstreamResponse.status,
    headers: {
      "content-type": contentType
    }
  });
}

export async function proxyHealth(): Promise<NextResponse> {
  let config: { baseUrl: string; apiKey: string };
  try {
    config = getProxyConfig();
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Proxy config error" },
      { status: 500 }
    );
  }

  const endpointUrl = joinUrl(config.baseUrl, "/health");
  try {
    const upstreamResponse = await fetch(endpointUrl, { cache: "no-store" });
    const text = await upstreamResponse.text();
    const contentType =
      upstreamResponse.headers.get("content-type") ?? "application/json; charset=utf-8";

    return new NextResponse(text, {
      status: upstreamResponse.status,
      headers: { "content-type": contentType }
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to reach upstream Essentia API", detail: String(error) },
      { status: 502 }
    );
  }
}
