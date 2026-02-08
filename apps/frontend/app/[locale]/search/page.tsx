import { getTranslations, setRequestLocale } from "next-intl/server";

import { Badge } from "../../../components/ui/badge";
import { buttonVariants } from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { cn } from "../../../lib/utils";

type FacetBucket = {
  key: string;
  label?: string;
  count: number;
};

type SearchHit = {
  chunk_id: string;
  score: number;
  source?: Record<string, unknown>;
  highlight?: Record<string, string[]>;
};

type SearchResponse = {
  query: string;
  requested_mode: string;
  effective_mode: string;
  warnings: string[];
  total: number;
  page: number;
  size: number;
  results: SearchHit[];
  facets: Record<string, FacetBucket[]>;
  embedding_model: string;
  embedding_model_version: string;
  normalization_version: string;
};

const SIZE_OPTIONS = [20, 50, 100];
const MODE_OPTIONS = [
  { value: "bm25", label: "BM25", disabled: false },
  { value: "vector", label: "Vector", disabled: false },
  { value: "hybrid", label: "Hybrid", disabled: false },
];

function getApiBase() {
  return (
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000"
  );
}

function buildSearchUrl(base: string, params: Record<string, string>) {
  const qs = new URLSearchParams(params);
  return `${base.replace(/\/$/, "")}/search?${qs.toString()}`;
}

function safeInt(value: string | undefined, fallback: number) {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseCsvParam(value?: string) {
  if (!value) return [] as string[];
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function toCsvParam(values: string[]) {
  return values.join(",");
}

function toggleValue(values: string[], value: string) {
  return values.includes(value)
    ? values.filter((v) => v !== value)
    : [...values, value];
}

function highlightSnippet(hit: SearchHit) {
  const h = hit.highlight || {};
  const content = h["content"]?.[0] || h["content.nostem"]?.[0];
  if (content) {
    return { html: content, isHtml: true };
  }
  const src = hit.source || {};
  const fallback = typeof src.content === "string" ? src.content : "";
  return {
    html: fallback ? `${fallback.slice(0, 280)}...` : "",
    isHtml: false,
  };
}

function formatDate(ah?: number | null, ce?: number | null) {
  if (!ah && !ce) return null;
  if (ah && ce) return `${ah} AH / ${ce} CE`;
  if (ah) return `${ah} AH`;
  return `${ce} CE`;
}

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams?: Promise<{
    q?: string;
    page?: string;
    size?: string;
    mode?: string;
    period?: string;
    region?: string;
    tags?: string;
    langs?: string;
    version?: string;
  }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "search" });
  const resolvedSearchParams = await (searchParams ?? Promise.resolve({}));
  const query = resolvedSearchParams.q?.trim() || t("defaultQuery");
  const requestedMode =
    resolvedSearchParams.mode &&
    ["bm25", "vector", "hybrid"].includes(resolvedSearchParams.mode)
      ? resolvedSearchParams.mode
      : "bm25";
  const size = SIZE_OPTIONS.includes(
    safeInt(resolvedSearchParams.size, SIZE_OPTIONS[0])
  )
    ? safeInt(resolvedSearchParams.size, SIZE_OPTIONS[0])
    : SIZE_OPTIONS[0];
  const page = Math.max(1, safeInt(resolvedSearchParams.page, 1));

  const selectedPeriod = parseCsvParam(resolvedSearchParams.period);
  const selectedRegion = parseCsvParam(resolvedSearchParams.region);
  const selectedTags = parseCsvParam(resolvedSearchParams.tags);
  const selectedLangs = parseCsvParam(resolvedSearchParams.langs);
  const selectedVersion = parseCsvParam(resolvedSearchParams.version);

  const apiParams: Record<string, string> = {
    q: query,
    mode: requestedMode,
    size: String(size),
    page: String(page),
  };
  if (selectedPeriod.length) apiParams.period = toCsvParam(selectedPeriod);
  if (selectedRegion.length) apiParams.region = toCsvParam(selectedRegion);
  if (selectedTags.length) apiParams.tags = toCsvParam(selectedTags);
  if (selectedLangs.length) apiParams.langs = toCsvParam(selectedLangs);
  if (selectedVersion.length) apiParams.version = toCsvParam(selectedVersion);

  const apiUrl = buildSearchUrl(getApiBase(), apiParams);

  let data: SearchResponse | null = null;
  try {
    const res = await fetch(apiUrl, { cache: "no-store" });
    if (res.ok) {
      data = (await res.json()) as SearchResponse;
    }
  } catch {
    data = null;
  }

  const results = data?.results ?? [];
  const effectiveMode = data?.effective_mode ?? requestedMode;
  const showFacets = effectiveMode === "bm25";
  const facets = showFacets ? data?.facets ?? {} : {};
  const total = data?.total ?? results.length;
  const totalPages = Math.max(1, Math.ceil(total / size));

  const facetList = (key: string) => facets[key] || [];
  const counts = {
    periods: facetList("period").length,
    regions: facetList("region").length,
    tags: facetList("tags").length,
  };

  const baseParams = {
    q: query,
    mode: requestedMode,
    size: String(size),
    ...(selectedPeriod.length ? { period: toCsvParam(selectedPeriod) } : {}),
    ...(selectedRegion.length ? { region: toCsvParam(selectedRegion) } : {}),
    ...(selectedTags.length ? { tags: toCsvParam(selectedTags) } : {}),
    ...(selectedLangs.length ? { langs: toCsvParam(selectedLangs) } : {}),
    ...(selectedVersion.length ? { version: toCsvParam(selectedVersion) } : {}),
  };

  const buildPageHref = (params: Record<string, string>) =>
    `/${locale}/search?${new URLSearchParams(params).toString()}`;

  const facetQueryFor = (facet: string, value: string) => {
    const next = {
      period: selectedPeriod,
      region: selectedRegion,
      tags: selectedTags,
      lang: selectedLangs,
      version: selectedVersion,
    };

    if (facet === "period") next.period = toggleValue(next.period, value);
    if (facet === "region") next.region = toggleValue(next.region, value);
    if (facet === "tags") next.tags = toggleValue(next.tags, value);
    if (facet === "lang") next.lang = toggleValue(next.lang, value);
    if (facet === "version") next.version = toggleValue(next.version, value);

    return {
      q: query,
      mode: requestedMode,
      size: String(size),
      page: "1",
      ...(next.period.length ? { period: toCsvParam(next.period) } : {}),
      ...(next.region.length ? { region: toCsvParam(next.region) } : {}),
      ...(next.tags.length ? { tags: toCsvParam(next.tags) } : {}),
      ...(next.lang.length ? { langs: toCsvParam(next.lang) } : {}),
      ...(next.version.length ? { version: toCsvParam(next.version) } : {}),
    };
  };

  const activeFilters = [
    ...selectedPeriod.map((key) => ({ facet: "period", key })),
    ...selectedRegion.map((key) => ({ facet: "region", key })),
    ...selectedTags.map((key) => ({ facet: "tags", key })),
    ...selectedLangs.map((key) => ({ facet: "lang", key })),
    ...selectedVersion.map((key) => ({ facet: "version", key })),
  ];

  const prevPageUrl =
    page > 1
      ? buildPageHref({
          ...baseParams,
          page: String(page - 1),
        })
      : null;
  const nextPageUrl =
    page < totalPages
      ? buildPageHref({
          ...baseParams,
          page: String(page + 1),
        })
      : null;

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute -left-20 top-10 h-72 w-72 rounded-full bg-[color:var(--color-secondary)]/50 blur-3xl" />
      <div className="pointer-events-none absolute right-[-120px] top-32 h-96 w-96 rounded-full bg-[color:var(--color-accent)]/40 blur-[120px]" />
      <div className="pointer-events-none absolute bottom-[-140px] left-1/3 h-[28rem] w-[28rem] rounded-full bg-[color:var(--color-muted)]/60 blur-[130px]" />

      <main className="relative mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-14 sm:px-10 lg:px-12">
        <header className="space-y-6">
          <Badge
            variant="outline"
            className="w-fit border-border/70 bg-background/70 px-4 py-2 text-[10px] uppercase tracking-[0.3em] text-muted-foreground"
          >
            {t("eyebrow")}
          </Badge>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">
                {t("title")}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t("resultCount", { query })}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Badge variant="secondary" className="rounded-full px-3 py-1">
                {total} {t("matchesLabel")}
              </Badge>
            </div>
          </div>
          <form
            className="flex w-full flex-col gap-3 lg:flex-row lg:items-center"
            action={`/${locale}/search`}
            method="get"
          >
            <label htmlFor="search-query" className="sr-only">
              {t("queryLabel")}
            </label>
            <Input
              id="search-query"
              type="search"
              name="q"
              placeholder={t("queryPlaceholder")}
              defaultValue={query}
              className="h-12 flex-1 rounded-full bg-background/80 px-5 text-base"
            />
            <input type="hidden" name="mode" value={requestedMode} />
            {selectedPeriod.length ? (
              <input type="hidden" name="period" value={toCsvParam(selectedPeriod)} />
            ) : null}
            {selectedRegion.length ? (
              <input type="hidden" name="region" value={toCsvParam(selectedRegion)} />
            ) : null}
            {selectedTags.length ? (
              <input type="hidden" name="tags" value={toCsvParam(selectedTags)} />
            ) : null}
            {selectedLangs.length ? (
              <input type="hidden" name="langs" value={toCsvParam(selectedLangs)} />
            ) : null}
            {selectedVersion.length ? (
              <input type="hidden" name="version" value={toCsvParam(selectedVersion)} />
            ) : null}
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                <span>{t("modeLabel")}</span>
                <select
                  name="mode"
                  defaultValue={requestedMode}
                  className="h-11 rounded-full border border-input bg-background/80 px-3 text-foreground shadow-sm"
                >
                  {MODE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {effectiveMode}
              </span>
              <label className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                <span>{t("pageSizeLabel")}</span>
                <select
                  name="size"
                  defaultValue={size}
                  className="h-11 rounded-full border border-input bg-background/80 px-3 text-foreground shadow-sm"
                >
                  {SIZE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                className={cn(
                  buttonVariants({ size: "lg" }),
                  "h-12 rounded-full px-6 text-base"
                )}
              >
                {t("searchButton")}
              </button>
            </div>
          </form>
          {data?.warnings?.length ? (
            <div className="text-sm text-amber-700">
              {data.warnings
                .map((code) =>
                  code === "qdrant_unavailable_fallback_bm25"
                    ? t("warningQdrantFallback")
                    : code
                )
                .join(", ")}
            </div>
          ) : null}
        </header>

        <section className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside>
            <Card className="rounded-3xl bg-card/70 backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  {t("filtersTitle")}
                </CardTitle>
                <a
                  href={buildPageHref({
                    q: query,
                    mode: requestedMode,
                    size: String(size),
                    page: "1",
                  })}
                  className="text-xs font-semibold text-muted-foreground hover:text-foreground"
                >
                  {t("clearFilters")}
                </a>
              </CardHeader>
              <CardContent className="space-y-5">
                {showFacets ? (
                  <>
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        {t("activeFilters")}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {activeFilters.length ? (
                          activeFilters.map((af) => (
                            <a
                              key={`${af.facet}:${af.key}`}
                              href={buildPageHref(facetQueryFor(af.facet, af.key))}
                              className={cn(
                                buttonVariants({ variant: "secondary", size: "sm" }),
                                "rounded-full"
                              )}
                            >
                              {af.key}
                            </a>
                          ))
                        ) : (
                          <Badge className="rounded-full">{t("noActiveFilters")}</Badge>
                        )}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-sm font-semibold">{t("filterPeriod")}</p>
                      <div className="flex flex-wrap gap-2">
                        {facetList("period").map((item) => (
                          <a
                            key={item.key}
                            href={buildPageHref(facetQueryFor("period", item.key))}
                            className={cn(
                              buttonVariants({
                                variant: selectedPeriod.includes(item.key)
                                  ? "secondary"
                                  : "outline",
                                size: "sm",
                              }),
                              "rounded-full"
                            )}
                          >
                            {item.label || item.key} ({item.count})
                          </a>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-sm font-semibold">{t("filterRegion")}</p>
                      <div className="flex flex-wrap gap-2">
                        {facetList("region").map((item) => (
                          <a
                            key={item.key}
                            href={buildPageHref(facetQueryFor("region", item.key))}
                            className={cn(
                              buttonVariants({
                                variant: selectedRegion.includes(item.key)
                                  ? "secondary"
                                  : "outline",
                                size: "sm",
                              }),
                              "rounded-full"
                            )}
                          >
                            {item.label || item.key} ({item.count})
                          </a>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-sm font-semibold">{t("filterLanguage")}</p>
                      <div className="flex flex-wrap gap-2">
                        {facetList("lang").map((item) => (
                          <a
                            key={item.key}
                            href={buildPageHref(facetQueryFor("lang", item.key))}
                            className={cn(
                              buttonVariants({
                                variant: selectedLangs.includes(item.key)
                                  ? "secondary"
                                  : "outline",
                                size: "sm",
                              }),
                              "rounded-full"
                            )}
                          >
                            {item.label || item.key} ({item.count})
                          </a>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-sm font-semibold">{t("filterVersion")}</p>
                      <div className="flex flex-wrap gap-2">
                        {facetList("version").map((item) => (
                          <a
                            key={item.key}
                            href={buildPageHref(facetQueryFor("version", item.key))}
                            className={cn(
                              buttonVariants({
                                variant: selectedVersion.includes(item.key)
                                  ? "secondary"
                                  : "outline",
                                size: "sm",
                              }),
                              "rounded-full"
                            )}
                          >
                            {item.label || item.key} ({item.count})
                          </a>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-sm font-semibold">{t("filterTags")}</p>
                      <div className="flex flex-wrap gap-2">
                        {facetList("tags").map((item) => (
                          <a
                            key={item.key}
                            href={buildPageHref(facetQueryFor("tags", item.key))}
                            className={cn(
                              buttonVariants({
                                variant: selectedTags.includes(item.key)
                                  ? "secondary"
                                  : "outline",
                                size: "sm",
                              }),
                              "rounded-full"
                            )}
                          >
                            {item.label || item.key} ({item.count})
                          </a>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">{t("facetsBm25Only")}</div>
                )}
              </CardContent>
            </Card>
          </aside>

          <div className="space-y-8">
            <section>
              <Card className="rounded-3xl bg-card/70">
                <CardHeader>
                  <CardTitle className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {t("statsTitle")}
                  </CardTitle>
                  <CardDescription>{t("statsDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 sm:grid-cols-4">
                  {[
                    { label: t("statPassages"), value: String(total) },
                    { label: t("statPeriods"), value: String(counts.periods) },
                    { label: t("statRegions"), value: String(counts.regions) },
                    { label: t("statTags"), value: String(counts.tags) },
                  ].map((item) => (
                    <Card key={item.label} className="rounded-2xl bg-background/80">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-semibold text-foreground">
                          {item.value}
                        </p>
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                          {item.label}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
                </CardContent>
              </Card>
            </section>

            <section className="space-y-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {t("resultsTitle")}
              </h2>
              <div className="space-y-4">
                {results.map((result) => {
                  const src = (result.source || {}) as Record<string, unknown>;
                  const title =
                    (src.work_title_lat as string) ||
                    (src.work_title_ar as string) ||
                    (src.title as string) ||
                    result.chunk_id;
                  const author =
                    (src.author_name_lat as string) ||
                    (src.author_name_ar as string) ||
                    "";
                  const work =
                    (src.work_title_lat as string) ||
                    (src.work_title_ar as string) ||
                    "";
                  const dateLabel = formatDate(
                    src.date_ah as number | null,
                    src.date_ce as number | null
                  );
                  const period = src.period as string | undefined;
                  const regions = Array.isArray(src.region)
                    ? (src.region as string[])
                    : [];
                  const tags = Array.isArray(src.tags) ? (src.tags as string[]) : [];
                  const version = (src.version_label as string) || "";
                  const type = (src.type as string) || "Passage";
                  const snippet = highlightSnippet(result);

                  return (
                    <Card
                      key={result.chunk_id}
                      className="rounded-3xl bg-card/80 transition hover:-translate-y-0.5 hover:shadow-md"
                    >
                      <CardHeader className="space-y-3">
                        <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                          <Badge className="rounded-full">{type}</Badge>
                          {period ? <span>{period}</span> : null}
                          {dateLabel ? <span>{dateLabel}</span> : null}
                          {regions.length ? <span>{regions.join(", ")}</span> : null}
                          {version ? <span>{version}</span> : null}
                          <span>{result.score.toFixed(2)}</span>
                        </div>
                        <CardTitle className="text-xl">{title}</CardTitle>
                        <CardDescription className="text-sm">
                          {author && work ? `${author} - ${work}` : author || work}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {snippet.html ? (
                          <p
                            className="text-sm leading-6 text-foreground/80"
                            {...(snippet.isHtml
                              ? { dangerouslySetInnerHTML: { __html: snippet.html } }
                              : { children: snippet.html })}
                          />
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                          {tags.map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className="border-border/70 text-muted-foreground"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                        <div className="flex flex-wrap gap-3 text-sm">
                          <button className={cn(buttonVariants(), "rounded-full")}>
                            {t("openPassage")}
                          </button>
                          <button
                            className={cn(
                              buttonVariants({ variant: "outline" }),
                              "rounded-full"
                            )}
                          >
                            {t("viewWork")}
                          </button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>

            <section className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-muted-foreground">
                {t("pageLabel", { page, totalPages })}
              </div>
              <div className="flex gap-2">
                {prevPageUrl ? (
                  <a
                    href={prevPageUrl}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  >
                    {t("prevPage")}
                  </a>
                ) : (
                  <span
                    className={cn(
                      buttonVariants({ variant: "outline", size: "sm" }),
                      "cursor-not-allowed opacity-50"
                    )}
                  >
                    {t("prevPage")}
                  </span>
                )}
                {nextPageUrl ? (
                  <a
                    href={nextPageUrl}
                    className={cn(buttonVariants({ size: "sm" }))}
                  >
                    {t("nextPage")}
                  </a>
                ) : (
                  <span
                    className={cn(
                      buttonVariants({ size: "sm" }),
                      "cursor-not-allowed opacity-50"
                    )}
                  >
                    {t("nextPage")}
                  </span>
                )}
              </div>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
