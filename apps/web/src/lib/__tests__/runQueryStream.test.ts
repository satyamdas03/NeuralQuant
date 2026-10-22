import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: null } }) },
  }),
}));

import { api, QueryServerError } from "../api";

function sseResponse(events: string[]): Response {
  const body = events.map((e) => `data: ${e}\n\n`).join("");
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runQueryStream", () => {
  it("throws QueryServerError on a server error event and does not re-run on /query/v2", async () => {
    const fetchMock = vi.fn(async () =>
      sseResponse([
        JSON.stringify({ status: "running" }),
        JSON.stringify({
          status: "error",
          code: "NQ_QUERY_TIMEOUT",
          message: "The AI took too long to respond. Please try again with a shorter question.",
        }),
        "[DONE]",
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const err = await api
      .runQueryStream({ question: "What about AAPL?" }, new AbortController().signal, () => {})
      .catch((e: unknown) => e);

    expect(err).toBeInstanceOf(QueryServerError);
    expect((err as QueryServerError).code).toBe("NQ_QUERY_TIMEOUT");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns the result on a done event", async () => {
    const result = { verdict: "HOLD", summary: "ok" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sseResponse([JSON.stringify({ status: "done", result }), "[DONE]"])),
    );

    const res = await api.runQueryStream(
      { question: "What about AAPL?" },
      new AbortController().signal,
      () => {},
    );
    expect(res).toEqual(result);
  });
});
