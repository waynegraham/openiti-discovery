import { render, screen } from "@testing-library/react";
import React from "react";

import PassagePage from "../app/[locale]/passage/[chunkId]/page";
import WorkPage from "../app/[locale]/work/[workId]/page";

vi.mock("next-intl/server", () => ({
  setRequestLocale: () => undefined,
}));

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

function mockFetchWithRoutes(routeToBody: Record<string, unknown | null>) {
  const routeEntries = Object.entries(routeToBody).sort((a, b) => b[0].length - a[0].length);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const matched = routeEntries.find(([key]) => url.includes(key));
      if (!matched) {
        return { ok: false, status: 404 } as Response;
      }
      const [, body] = matched;
      if (body === null) {
        return { ok: false, status: 404 } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => body,
      } as Response;
    }),
  );
}

describe("reading routes integration", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders passage navigation and version switching links for en and ar", async () => {
    mockFetchWithRoutes({
      "/chunks/c1": {
        chunk_id: "c1",
        version_id: "v1",
        work_id: "w1",
        author_id: "a1",
        chunk_index: 10,
        text_raw: "Passage body",
        prev_chunk_id: "c0",
        next_chunk_id: "c2",
      },
      "/works/w1/versions?": [
        { version_id: "v1", work_id: "w1", lang: "ara", is_pri: true, repo_path: "x" },
        { version_id: "v2", work_id: "w1", lang: "fas", is_pri: false, repo_path: "y" },
      ],
      "/works/w1/versions/v2/chunks/resolve?target_chunk_index=10": {
        resolved_chunk_id: "v2::9",
        resolved_chunk_index: 9,
      },
    });

    const enUi = await PassagePage({
      params: Promise.resolve({ locale: "en", chunkId: "c1" }),
      searchParams: Promise.resolve({ langs: "ara,fas" }),
    });
    render(enUi);
    expect(screen.getByRole("link", { name: "Previous" })).toHaveAttribute(
      "href",
      "/en/passage/c0",
    );
    expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute("href", "/en/passage/c2");
    expect(screen.getByRole("link", { name: /View work/i })).toHaveAttribute(
      "href",
      "/en/work/w1?target_chunk_index=10&langs=ara%2Cfas",
    );
    expect(screen.getByRole("link", { name: "v2" })).toHaveAttribute("href", "/en/passage/v2%3A%3A9");

    const arUi = await PassagePage({
      params: Promise.resolve({ locale: "ar", chunkId: "c1" }),
      searchParams: Promise.resolve({ langs: "ara,fas" }),
    });
    render(arUi);
    expect(screen.getByRole("link", { name: "السابق" })).toHaveAttribute(
      "href",
      "/ar/passage/c0",
    );
    expect(screen.getByRole("link", { name: "التالي" })).toHaveAttribute("href", "/ar/passage/c2");
  });

  it("renders work overview and version open links for en and ar", async () => {
    mockFetchWithRoutes({
      "/works/w1": {
        work_id: "w1",
        author_id: "a1",
        title_latn: "Work One",
        author_name_latn: "Author One",
      },
      "/works/w1/versions?": [
        { version_id: "v1", work_id: "w1", lang: "ara", is_pri: true, repo_path: "x" },
        { version_id: "v2", work_id: "w1", lang: "fas", is_pri: false, repo_path: "y" },
      ],
      "/works/w1/versions/v1/chunks/resolve?target_chunk_index=0": {
        resolved_chunk_id: "v1::0",
        resolved_chunk_index: 0,
      },
      "/works/w1/versions/v2/chunks/resolve?target_chunk_index=0": null,
    });

    const enUi = await WorkPage({
      params: Promise.resolve({ locale: "en", workId: "w1" }),
      searchParams: Promise.resolve({ target_chunk_index: "0", langs: "ara,fas" }),
    });
    render(enUi);
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/en/passage/v1%3A%3A0");
    expect(screen.getByText("Unavailable at this context")).toBeInTheDocument();

    const arUi = await WorkPage({
      params: Promise.resolve({ locale: "ar", workId: "w1" }),
      searchParams: Promise.resolve({ target_chunk_index: "0", langs: "ara,fas" }),
    });
    render(arUi);
    expect(screen.getByRole("link", { name: "افتح" })).toHaveAttribute("href", "/ar/passage/v1%3A%3A0");
    expect(screen.getByText("غير متاح عند هذا الموضع")).toBeInTheDocument();
  });

  it("decodes encoded dynamic route params before API calls", async () => {
    mockFetchWithRoutes({
      "/chunks/v1%3A%3A0": {
        chunk_id: "v1::0",
        version_id: "v1",
        work_id: "w/1",
        author_id: "a1",
        chunk_index: 0,
        text_raw: "Passage body",
      },
      "/works/w%2F1/versions?": [
        { version_id: "v1", work_id: "w/1", lang: "ara", is_pri: true, repo_path: "x" },
      ],
      "/works/w%2F1/versions/v1/chunks/resolve?target_chunk_index=0": {
        resolved_chunk_id: "v1::0",
        resolved_chunk_index: 0,
      },
      "/works/w%2F1": {
        work_id: "w/1",
        author_id: "a1",
        title_latn: "Work Slash",
        author_name_latn: "Author One",
      },
    });

    const passageUi = await PassagePage({
      params: Promise.resolve({ locale: "en", chunkId: "v1%3A%3A0" }),
      searchParams: Promise.resolve({}),
    });
    render(passageUi);
    expect(screen.getByRole("heading", { name: "v1::0" })).toBeInTheDocument();

    const workUi = await WorkPage({
      params: Promise.resolve({ locale: "en", workId: "w%2F1" }),
      searchParams: Promise.resolve({ target_chunk_index: "0" }),
    });
    render(workUi);
    expect(screen.getByRole("heading", { name: "Work Slash" })).toBeInTheDocument();
  });
});
