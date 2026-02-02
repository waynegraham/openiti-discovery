import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { locales } from "../../i18n";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const messages = await getMessages({ locale });
  const direction = locale === "ar" ? "rtl" : "ltr";

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div lang={locale} dir={direction} className="min-h-screen">
        {children}
      </div>
    </NextIntlClientProvider>
  );
}
