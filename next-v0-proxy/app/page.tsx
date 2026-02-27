"use client";

import { FormEvent, useState } from "react";

const ENDPOINTS = [
  "rhythm",
  "structure",
  "classification",
  "tonal",
  "vocals",
  "full"
] as const;

type Endpoint = (typeof ENDPOINTS)[number];

export default function HomePage() {
  const [endpoint, setEndpoint] = useState<Endpoint>("full");
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<string>("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];

    if (!file) {
      setOutput("Select an audio file first.");
      return;
    }

    setLoading(true);
    setOutput("");
    try {
      const body = new FormData();
      body.append("file", file);

      const response = await fetch(`/api/essentia/${endpoint}`, {
        method: "POST",
        body
      });

      const text = await response.text();
      setOutput(text);
    } catch (error) {
      setOutput(
        JSON.stringify(
          { error: error instanceof Error ? error.message : "Unknown error" },
          null,
          2
        )
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Essentia Proxy (Next.js)</h1>
      <p>
        This app proxies requests to your FastAPI Essentia service using server-side
        credentials. Use this in v0/Next.js deployments.
      </p>

      <form onSubmit={onSubmit}>
        <label>
          Endpoint
          <select
            name="endpoint"
            value={endpoint}
            onChange={(event) => setEndpoint(event.target.value as Endpoint)}
          >
            {ENDPOINTS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Audio file
          <input name="file" type="file" accept="audio/*" />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </form>

      {output ? <pre>{output}</pre> : null}
    </main>
  );
}
