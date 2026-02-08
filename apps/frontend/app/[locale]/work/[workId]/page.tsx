import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { Badge } from "../../../../components/ui/badge";
import { buttonVariants } from "../../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../../components/ui/card";
import { fetchJson } from "../../../../lib/api";
import { cn } from "../../../../lib/utils";

type WorkResponse = {
  work_id: string;
  author_id: string;
  title_ar?: string | null;
  title_latn?: string | null;
  author_name_ar?: string | null;
  author_name_latn?: string | null;
  death_year_ah?: number | null;
  death_year_ce?: number | null;
  work_year_start_ce?: number | null;
  work_year_end_ce?: number | null;
};

type WorkVersion = {
  version_id: string;
  work_id: string;
  lang: string;
  is_pri: boolean;
  source_uri?: string | null;
  repo_path: string;
};

type ResolveResponse = {
  resolved_chunk_id: string;
  resolved_chunk_index: number;
};

function parseCsv(value?: string) {
  if (!value) return [] as string[];
  return value.split(",").map((v) => v.trim()).filter(Boolean);
}

function normalizeRouteParam(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function labels(locale: string) {
  if (locale === "ar") {
    return {
      title: "نظرة عامة على العمل",
      versions: "الإصدارات",
      open: "افتح",
      unavailable: "غير متاح عند هذا الموضع",
      by: "المؤلف",
      date: "التاريخ",
    };
  }
  return {
    title: "Work overview",
    versions: "Versions",
    open: "Open",
    unavailable: "Unavailable at this context",
    by: "Author",
    date: "Date",
  };
}

export default async function WorkPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; workId: string }>;
  searchParams?: Promise<{ target_chunk_index?: string; langs?: string }>;
}) {
  const { locale, workId } = await params;
  const normalizedWorkId = normalizeRouteParam(workId);
  setRequestLocale(locale);
  const copy = labels(locale);
  const resolvedSearchParams = await (searchParams ?? Promise.resolve({}));
  const targetChunkIndex = Number.parseInt(resolvedSearchParams.target_chunk_index || "0", 10);
  const safeTargetChunkIndex = Number.isFinite(targetChunkIndex) && targetChunkIndex >= 0
    ? targetChunkIndex
    : 0;
  const langs = parseCsv(resolvedSearchParams.langs);

  const work = await fetchJson<WorkResponse>(`/works/${encodeURIComponent(normalizedWorkId)}`);
  if (!work) notFound();

  const versionPath = new URLSearchParams({ locale });
  if (langs.length) versionPath.set("preferred_langs", langs.join(","));
  const versions =
    (await fetchJson<WorkVersion[]>(
      `/works/${encodeURIComponent(normalizedWorkId)}/versions?${versionPath.toString()}`
    )) || [];

  const resolvedByVersion = await Promise.all(
    versions.map(async (v) => {
      const resolved = await fetchJson<ResolveResponse>(
        `/works/${encodeURIComponent(normalizedWorkId)}/versions/${encodeURIComponent(v.version_id)}/chunks/resolve?target_chunk_index=${safeTargetChunkIndex}`
      );
      return {
        version: v,
        resolved,
      };
    })
  );

  const title = work.title_latn || work.title_ar || work.work_id;
  const author = work.author_name_latn || work.author_name_ar || work.author_id;
  const dateLabel = work.work_year_start_ce || work.work_year_end_ce
    ? `${work.work_year_start_ce ?? "?"} - ${work.work_year_end_ce ?? "?"} CE`
    : null;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10 sm:px-10">
      <div className="space-y-2">
        <Badge className="rounded-full">{copy.title}</Badge>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">
          {copy.by}: {author}
          {dateLabel ? ` • ${copy.date}: ${dateLabel}` : ""}
        </p>
      </div>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            {copy.versions}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {resolvedByVersion.map(({ version, resolved }) => (
            <div
              key={version.version_id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/60 p-4"
            >
              <div className="space-y-1">
                <p className="font-medium">
                  {version.version_id} {version.is_pri ? "(PRI)" : ""}
                </p>
                <p className="text-sm text-muted-foreground">{version.lang}</p>
              </div>
              {resolved ? (
                <a
                  href={`/${locale}/passage/${encodeURIComponent(resolved.resolved_chunk_id)}`}
                  className={cn(buttonVariants({ variant: "outline" }), "rounded-full")}
                >
                  {copy.open}
                </a>
              ) : (
                <span className={cn(buttonVariants({ variant: "outline" }), "rounded-full opacity-50")}>
                  {copy.unavailable}
                </span>
              )}
            </div>
          ))}
          {!resolvedByVersion.length ? (
            <p className="text-sm text-muted-foreground">No versions found.</p>
          ) : null}
        </CardContent>
      </Card>
    </main>
  );
}
