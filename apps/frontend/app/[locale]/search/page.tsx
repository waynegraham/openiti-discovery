import { getTranslations, setRequestLocale } from "next-intl/server";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";

const results = [
  {
    id: "p-001",
    title: "Qawa'id al-fiqhiyya: On the foundations of jurisprudence",
    author: "Taqi al-Din Ibn Taymiyya",
    work: "Majmu' al-Fatawa",
    period: "7th/13th c.",
    region: "Damascus",
    type: "Passage",
    version: "PRI",
    snippet:
      "The passage outlines foundational legal maxims and their role in resolving disputed rulings when evidence is dispersed.",
    tags: ["Legal theory", "Maxims", "Method"],
    score: "0.91",
  },
  {
    id: "p-002",
    title: "Ma hiya al-sinema: A debate on depiction",
    author: "Muhammad Rashid Rida",
    work: "Al-Manar",
    period: "14th/20th c.",
    region: "Cairo",
    type: "Passage",
    version: "ALT",
    snippet:
      "A reflective inquiry into film as a medium, considering depiction, imitation, and public ethics.",
    tags: ["Modernity", "Media", "Ethics"],
    score: "0.86",
  },
  {
    id: "p-003",
    title: "Ulum al-hadith: Definitions and scope",
    author: "Ibn al-Salah",
    work: "Muqaddima",
    period: "7th/13th c.",
    region: "Damascus",
    type: "Passage",
    version: "PRI",
    snippet:
      "Defines the objectives of hadith studies, outlining classification, transmission, and evaluative practices.",
    tags: ["Hadith", "Classification", "Transmission"],
    score: "0.82",
  },
];

const facets = {
  type: ["Passage", "Work", "Author", "Version"],
  period: [
    "1st-3rd/7th-9th c.",
    "4th-6th/10th-12th c.",
    "7th-9th/13th-15th c.",
    "10th-14th/16th-20th c.",
  ],
  region: ["Hijaz", "Iraq", "Levant", "Maghreb", "Yemen"],
  language: ["Arabic", "Persian", "Ottoman Turkish"],
  collection: ["Legal theory", "Hadith", "History", "Poetry"],
  version: ["PRI", "ALT", "OCR"],
  focus: ["Law", "Theology", "Literature", "Philosophy"],
};

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams?: Promise<{ q?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "search" });
  const resolvedSearchParams = await (searchParams ?? Promise.resolve({}));
  const query = resolvedSearchParams.q?.trim() || t("defaultQuery");

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
                {results.length} {t("matchesLabel")}
              </Badge>
              <label className="flex items-center gap-2">
                <span>{t("sortLabel")}</span>
                <select className="h-10 rounded-full border border-input bg-background/80 px-3 text-foreground shadow-sm">
                  <option>{t("sortRelevance")}</option>
                  <option>{t("sortRecency")}</option>
                  <option>{t("sortLength")}</option>
                </select>
              </label>
            </div>
          </div>
          <form className="flex w-full flex-col gap-3 sm:flex-row">
            <label htmlFor="search-query" className="sr-only">
              {t("queryLabel")}
            </label>
            <Input
              id="search-query"
              type="search"
              placeholder={t("queryPlaceholder")}
              defaultValue={query}
              className="h-12 flex-1 rounded-full bg-background/80 px-5 text-base"
            />
            <Button type="submit" className="h-12 rounded-full px-6 text-base">
              {t("searchButton")}
            </Button>
          </form>
        </header>

        <section className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside>
            <Card className="rounded-3xl bg-card/70 backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  {t("filtersTitle")}
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs font-semibold text-muted-foreground"
                >
                  {t("clearFilters")}
                </Button>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    {t("activeFilters")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Badge className="rounded-full">Passage</Badge>
                    <Badge className="rounded-full">7th-9th/13th-15th c.</Badge>
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterType")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.type.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterPeriod")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.period.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterRegion")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.region.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterLanguage")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.language.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterCollection")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.collection.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterVersion")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.version.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold">{t("filterTags")}</p>
                  <div className="flex flex-wrap gap-2">
                    {facets.focus.map((item) => (
                      <Badge
                        key={item}
                        variant="outline"
                        className="border-border/70 text-muted-foreground"
                      >
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>
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
                    { label: t("statAuthors"), value: "38" },
                    { label: t("statWorks"), value: "112" },
                    { label: t("statPassages"), value: "1,204" },
                    { label: t("statPeriods"), value: "5" },
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
                {results.map((result) => (
                  <Card
                    key={result.id}
                    className="rounded-3xl bg-card/80 transition hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <CardHeader className="space-y-3">
                      <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        <Badge className="rounded-full">{result.type}</Badge>
                        <span>{result.period}</span>
                        <span>{result.region}</span>
                        <span>{result.version}</span>
                        <span>{result.score}</span>
                      </div>
                      <CardTitle className="text-xl">{result.title}</CardTitle>
                      <CardDescription className="text-sm">
                        {result.author} - {result.work}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-sm leading-6 text-foreground/80">
                        {result.snippet}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {result.tags.map((tag) => (
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
                        <Button className="rounded-full">{t("openPassage")}</Button>
                        <Button variant="outline" className="rounded-full">
                          {t("viewWork")}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>

            <section>
              <Card className="rounded-3xl bg-card/70">
                <CardHeader>
                  <CardTitle className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {t("relatedTitle")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-3">
                  {[t("relatedOne"), t("relatedTwo"), t("relatedThree")].map(
                    (item) => (
                      <Card key={item} className="rounded-2xl bg-background/80">
                        <CardContent className="px-4 py-3 text-sm font-semibold text-foreground/80">
                          {item}
                        </CardContent>
                      </Card>
                    )
                  )}
                </CardContent>
              </Card>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
