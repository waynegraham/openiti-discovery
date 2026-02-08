import { render, screen } from "@testing-library/react";
import React from "react";

import SearchPage from "../app/[locale]/search/page";

vi.mock("next-intl/server", () => ({
  getTranslations: async () => (key: string, args?: Record<string, string>) => {
    if (key === "resultCount") return `Results for "${args?.query || ""}"`;
    const map: Record<string, string> = {
      defaultQuery: "default",
      searchButton: "Search",
      openPassage: "Open passage",
      viewWork: "View work",
      matchesLabel: "matches",
      title: "Title",
      eyebrow: "Eyebrow",
      queryLabel: "query",
      queryPlaceholder: "placeholder",
      modeLabel: "Mode",
      pageSizeLabel: "Page size",
      warningQdrantFallback: "fallback",
      filtersTitle: "Filters",
      clearFilters: "Clear",
      activeFilters: "Active",
      noActiveFilters: "None",
      filterPeriod: "Period",
      filterRegion: "Region",
      filterLanguage: "Language",
      filterVersion: "Version",
      filterTags: "Tags",
      facetsBm25Only: "BM25 only",
      statsTitle: "Stats",
      statsDescription: "Description",
      statPassages: "Passages",
      statPeriods: "Periods",
      statRegions: "Regions",
      statTags: "Tags",
      resultsTitle: "Results",
      pageLabel: "Page",
      prevPage: "Previous",
      nextPage: "Next",
    };
    return map[key] || key;
  },
  setRequestLocale: () => undefined,
}));

describe("search page integration", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        ({
          ok: true,
          json: async () => ({
            query: "abc",
            requested_mode: "bm25",
            effective_mode: "bm25",
            warnings: [],
            total: 1,
            page: 1,
            size: 20,
            facets: {
              period: [],
              region: [],
              tags: [],
              lang: [],
              version: [],
            },
            results: [
              {
                chunk_id: "c1",
                score: 1.0,
                source: {
                  work_id: "w1",
                  work_title_lat: "Work 1",
                  author_name_lat: "Author 1",
                  content: "Snippet",
                },
              },
            ],
            embedding_model: "m",
            embedding_model_version: "v",
            normalization_version: "n",
          }),
        }) as Response
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("wires open passage and view work links for en locale", async () => {
    const ui = await SearchPage({
      params: Promise.resolve({ locale: "en" }),
      searchParams: Promise.resolve({ q: "abc" }),
    });
    render(ui);

    expect(screen.getByRole("link", { name: "Open passage" })).toHaveAttribute(
      "href",
      "/en/passage/c1",
    );
    expect(screen.getByRole("link", { name: "View work" })).toHaveAttribute(
      "href",
      "/en/work/w1",
    );
  });

  it("wires locale-aware links for ar locale", async () => {
    const ui = await SearchPage({
      params: Promise.resolve({ locale: "ar" }),
      searchParams: Promise.resolve({ q: "abc" }),
    });
    render(ui);

    expect(screen.getByRole("link", { name: "Open passage" })).toHaveAttribute(
      "href",
      "/ar/passage/c1",
    );
    expect(screen.getByRole("link", { name: "View work" })).toHaveAttribute(
      "href",
      "/ar/work/w1",
    );
  });
});
