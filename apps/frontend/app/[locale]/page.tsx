import { useTranslations } from "next-intl";

export default function Home() {
  const t = useTranslations("landing");

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#f6f1e9] text-[#1e1a14]">
      <div className="pointer-events-none absolute -left-24 -top-28 h-96 w-96 rounded-full bg-[#f7c59f]/45 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 right-0 h-[28rem] w-[28rem] rounded-full bg-[#9ab3f5]/35 blur-3xl" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.6),_rgba(246,241,233,0)_55%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-20 sm:px-10">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-[#6b5f53]">
          {t("eyebrow")}
        </p>
        <h1 className="mt-6 max-w-2xl text-4xl font-semibold leading-tight sm:text-5xl">
          {t("title")}
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-[#4f463b]">
          {t("description")}
        </p>

        <form className="mt-10 flex w-full max-w-2xl flex-col gap-3 sm:flex-row">
          <label htmlFor="discovery-search" className="sr-only">
            {t("searchLabel")}
          </label>
          <input
            id="discovery-search"
            type="search"
            placeholder={t("searchPlaceholder")}
            className="h-12 flex-1 rounded-full border border-[#d9cdbf] bg-white/80 px-5 text-base text-[#1e1a14] shadow-sm outline-none transition focus:border-[#9ab3f5] focus:bg-white focus:ring-2 focus:ring-[#9ab3f5]/30"
          />
          <button
            type="submit"
            className="h-12 rounded-full bg-[#1e1a14] px-6 text-base font-semibold text-[#f6f1e9] transition hover:translate-y-[-1px] hover:bg-[#2c251d]"
          >
            {t("searchButton")}
          </button>
        </form>

        <p className="mt-4 text-sm text-[#6b5f53]">{t("helper")}</p>
        <p className="mt-2 text-sm text-[#6b5f53]">{t("examples")}</p>
      </main>
    </div>
  );
}
