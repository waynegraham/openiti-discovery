import { getRequestConfig } from "next-intl/server";

export const locales = ["en", "ar"] as const;
export const defaultLocale = "en" as const;

export default getRequestConfig(async ({ locale }) => {
  const resolvedLocale = locales.includes(locale as (typeof locales)[number])
    ? locale
    : defaultLocale;

  return {
    locale: resolvedLocale,
    messages: (await import(`./messages/${resolvedLocale}.json`)).default,
  };
});
