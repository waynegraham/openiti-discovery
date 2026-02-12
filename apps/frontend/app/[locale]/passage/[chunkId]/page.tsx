import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { Badge } from "../../../../components/ui/badge";
import { buttonVariants } from "../../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../../components/ui/card";
import { fetchJson } from "../../../../lib/api";
import { cn } from "../../../../lib/utils";

type ChunkResponse = {
  chunk_id: string;
  version_id: string;
  work_id: string;
  author_id: string;
  chunk_index: number;
  heading_text?: string | null;
  heading_path?: string[] | null;
  text_raw: string;
  prev_chunk_id?: string | null;
  next_chunk_id?: string | null;
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
      title: "المقطع",
      context: "السياق",
      prev: "السابق",
      next: "التالي",
      viewWork: "عرض العمل",
      versions: "الإصدارات",
      unavailable: "لا يوجد مقطع سابق مطابق",
      current: "الحالي",
    };
  }
  return {
    title: "Passage",
    context: "Context",
    prev: "Previous",
    next: "Next",
    viewWork: "View work",
    versions: "Versions",
    unavailable: "No lower matching chunk",
    current: "Current",
  };
}

export default async function PassagePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; chunkId: string }>;
  searchParams?: Promise<{ langs?: string; q?: string }>;
}) {
  const { locale, chunkId } = await params;
  const normalizedChunkId = normalizeRouteParam(chunkId);
  setRequestLocale(locale);
  const copy = labels(locale);
  const resolvedSearchParams = await (searchParams ?? Promise.resolve({}));
  const langs = parseCsv(resolvedSearchParams.langs);

  const chunk = await fetchJson<ChunkResponse>(`/chunks/${encodeURIComponent(normalizedChunkId)}`);
  if (!chunk) notFound();

  const versionPath = new URLSearchParams({ locale });
  if (langs.length) versionPath.set("preferred_langs", langs.join(","));
  const versions =
    (await fetchJson<WorkVersion[]>(
      `/works/${encodeURIComponent(chunk.work_id)}/versions?${versionPath.toString()}`
    )) || [];

  const versionTargets = await Promise.all(
    versions.map(async (v) => {
      if (v.version_id === chunk.version_id) {
        return { versionId: v.version_id, href: `/${locale}/passage/${encodeURIComponent(chunk.chunk_id)}` };
      }
      const resolved = await fetchJson<ResolveResponse>(
        `/works/${encodeURIComponent(chunk.work_id)}/versions/${encodeURIComponent(v.version_id)}/chunks/resolve?target_chunk_index=${chunk.chunk_index}`
      );
      return {
        versionId: v.version_id,
        href: resolved
          ? `/${locale}/passage/${encodeURIComponent(resolved.resolved_chunk_id)}`
          : null,
      };
    })
  );

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10 sm:px-10">
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-2">
          <Badge className="rounded-full">{copy.title}</Badge>
          <h1 className="text-2xl font-semibold">{chunk.chunk_id}</h1>
          <p className="text-sm text-muted-foreground">
            {chunk.version_id} • {chunk.work_id} • #{chunk.chunk_index}
          </p>
        </div>
        <a
          href={`/${locale}/work/${encodeURIComponent(chunk.work_id)}?target_chunk_index=${chunk.chunk_index}${langs.length ? `&langs=${encodeURIComponent(langs.join(","))}` : ""}`}
          className={cn(buttonVariants({ variant: "outline" }), "rounded-full")}
        >
          {copy.viewWork}
        </a>
      </div>

      {chunk.heading_path?.length ? (
        <p className="text-sm text-muted-foreground">{chunk.heading_path.join(" / ")}</p>
      ) : null}

      <Card className="rounded-3xl">
        <CardContent className="p-6">
          <p className="whitespace-pre-wrap leading-8">{chunk.text_raw}</p>
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            {copy.context}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {chunk.prev_chunk_id ? (
            <a
              href={`/${locale}/passage/${encodeURIComponent(chunk.prev_chunk_id)}`}
              className={cn(buttonVariants({ variant: "outline" }), "rounded-full")}
            >
              {copy.prev}
            </a>
          ) : (
            <span className={cn(buttonVariants({ variant: "outline" }), "rounded-full opacity-50")}>
              {copy.prev}
            </span>
          )}
          {chunk.next_chunk_id ? (
            <a
              href={`/${locale}/passage/${encodeURIComponent(chunk.next_chunk_id)}`}
              className={cn(buttonVariants(), "rounded-full")}
            >
              {copy.next}
            </a>
          ) : (
            <span className={cn(buttonVariants(), "rounded-full opacity-50")}>{copy.next}</span>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            {copy.versions}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {versionTargets.map((vt) => (
            vt.href ? (
              <a
                key={vt.versionId}
                href={vt.href}
                className={cn(
                  buttonVariants({ variant: vt.versionId === chunk.version_id ? "secondary" : "outline" }),
                  "rounded-full"
                )}
              >
                {vt.versionId}
                {vt.versionId === chunk.version_id ? ` (${copy.current})` : ""}
              </a>
            ) : (
              <span
                key={vt.versionId}
                className={cn(buttonVariants({ variant: "outline" }), "rounded-full opacity-50")}
              >
                {vt.versionId} - {copy.unavailable}
              </span>
            )
          ))}
        </CardContent>
      </Card>
    </main>
  );
}
