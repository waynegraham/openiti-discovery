import { getTranslations, setRequestLocale } from "next-intl/server";

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
    <div className="relative min-h-screen overflow-hidden bg-[#f5efe6] text-[#1f1b16]">
      <div className="pointer-events-none absolute -left-20 top-10 h-72 w-72 rounded-full bg-[#e4c7a2]/60 blur-3xl" />
      <div className="pointer-events-none absolute right-[-120px] top-32 h-96 w-96 rounded-full bg-[#93b8b0]/45 blur-[120px]" />
      <div className="pointer-events-none absolute bottom-[-140px] left-1/3 h-[28rem] w-[28rem] rounded-full bg-[#f0d3b5]/50 blur-[130px]" />

      <main className="relative mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-14 sm:px-10 lg:px-12">
        <header className="space-y-6">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#6a5b4d]">
            {t("eyebrow")}
          </p>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">
                {t("title")}
              </h1>
              <p className="text-sm text-[#6a5b4d]">{t("resultCount", { query })}</p>
            </div>
            <div className="flex items-center gap-3 text-sm text-[#6a5b4d]">
              <span className="rounded-full border border-[#d8c9b9] bg-white/70 px-3 py-1">
                {results.length} {t("matchesLabel")}
              </span>
              <label className="flex items-center gap-2">
                <span>{t("sortLabel")}</span>
                <select className="rounded-full border border-[#d8c9b9] bg-white/80 px-3 py-1 text-[#1f1b16] shadow-sm">
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
            <input
              id="search-query"
              type="search"
              placeholder={t("queryPlaceholder")}
              defaultValue={query}
              className="h-12 flex-1 rounded-full border border-[#d8c9b9] bg-white/80 px-5 text-base text-[#1f1b16] shadow-sm outline-none transition focus:border-[#93b8b0] focus:bg-white focus:ring-2 focus:ring-[#93b8b0]/30"
            />
            <button
              type="submit"
              className="h-12 rounded-full bg-[#1f1b16] px-6 text-base font-semibold text-[#f5efe6] transition hover:translate-y-[-1px] hover:bg-[#2b251f]"
            >
              {t("searchButton")}
            </button>
          </form>
        </header>

        <section className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-6 rounded-3xl border border-[#e1d5c7] bg-white/70 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#6a5b4d]">
                {t("filtersTitle")}
              </h2>
              <button className="text-xs font-semibold text-[#7a6b5c]">
                {t("clearFilters")}
              </button>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7a6b5c]">
                  {t("activeFilters")}
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full bg-[#1f1b16] px-3 py-1 text-xs font-semibold text-[#f5efe6]">
                    Passage
                  </span>
                  <span className="rounded-full bg-[#1f1b16] px-3 py-1 text-xs font-semibold text-[#f5efe6]">
                    7th-9th/13th-15th c.
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterType")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.type.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterPeriod")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.period.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterRegion")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.region.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterLanguage")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.language.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterCollection")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.collection.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterVersion")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.version.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-[#3f372f]">{t("filterTags")}</p>
                <div className="flex flex-wrap gap-2">
                  {facets.focus.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </aside>

          <div className="space-y-8">
            <section className="rounded-3xl border border-[#e1d5c7] bg-white/70 p-6 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#6a5b4d]">
                {t("statsTitle")}
              </h2>
              <p className="mt-2 text-sm text-[#6a5b4d]">{t("statsDescription")}</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-4">
                {[
                  { label: t("statAuthors"), value: "38" },
                  { label: t("statWorks"), value: "112" },
                  { label: t("statPassages"), value: "1,204" },
                  { label: t("statPeriods"), value: "5" },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-[#dbcdbf] bg-[#fdfbf7] p-4 text-center"
                  >
                    <p className="text-2xl font-semibold text-[#1f1b16]">{item.value}</p>
                    <p className="text-xs uppercase tracking-[0.2em] text-[#7a6b5c]">
                      {item.label}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#6a5b4d]">
                {t("resultsTitle")}
              </h2>
              <div className="space-y-4">
                {results.map((result) => (
                  <article
                    key={result.id}
                    className="rounded-3xl border border-[#e1d5c7] bg-white/80 p-6 shadow-sm transition hover:translate-y-[-2px] hover:shadow-md"
                  >
                    <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.2em] text-[#7a6b5c]">
                      <span className="rounded-full bg-[#1f1b16] px-3 py-1 text-xs font-semibold text-[#f5efe6]">
                        {result.type}
                      </span>
                      <span>{result.period}</span>
                      <span>{result.region}</span>
                      <span>{result.version}</span>
                      <span>{result.score}</span>
                    </div>
                    <h3 className="mt-4 text-xl font-semibold text-[#1f1b16]">
                      {result.title}
                    </h3>
                    <p className="mt-2 text-sm text-[#6a5b4d]">
                      {result.author} • {result.work}
                    </p>
                    <p className="mt-4 text-sm leading-6 text-[#4d4339]">
                      {result.snippet}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {result.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-[#dbcdbf] px-3 py-1 text-xs text-[#4d4339]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="mt-5 flex flex-wrap gap-3 text-sm">
                      <button className="rounded-full bg-[#1f1b16] px-4 py-2 font-semibold text-[#f5efe6]">
                        {t("openPassage")}
                      </button>
                      <button className="rounded-full border border-[#d8c9b9] px-4 py-2 text-[#4d4339]">
                        {t("viewWork")}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="rounded-3xl border border-[#e1d5c7] bg-white/70 p-6 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#6a5b4d]">
                {t("relatedTitle")}
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {[t("relatedOne"), t("relatedTwo"), t("relatedThree")].map((item) => (
                  <div
                    key={item}
                    className="rounded-2xl border border-[#dbcdbf] bg-[#fdfbf7] px-4 py-3 text-sm font-semibold text-[#4d4339]"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
