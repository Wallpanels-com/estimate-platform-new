import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  countLabel,
  LANGUAGE_KEY,
  readLanguage,
  writeLanguage,
  translate,
  type Language,
} from "./locale";

const LanguageContext = createContext<{
  language: Language;
  setLanguage: (value: Language) => void;
  t: (text: string, ...values: unknown[]) => string;
  n: (count: number, noun: "items" | "line items" | "estimates") => string;
}>({
  language: "en",
  setLanguage: () => {},
  t: (text) => text,
  n: (count, noun) => countLabel(count, noun, "en"),
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<Language>(readLanguage);
  const setLanguage = useCallback((value: Language) => {
    writeLanguage(value);
    updateLanguage(value);
  }, []);
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
  useEffect(() => {
    const receive = (event: StorageEvent) => {
      if (event.key === LANGUAGE_KEY || event.key === null)
        updateLanguage(readLanguage());
    };
    window.addEventListener("storage", receive);
    return () => window.removeEventListener("storage", receive);
  }, []);
  const value = useMemo(
    () => ({
      language,
      setLanguage,
      n: (count: number, noun: "items" | "line items" | "estimates") =>
        countLabel(count, noun, language),
      t: (text: string, ...values: unknown[]) =>
        translate(text, language, ...values),
    }),
    [language, setLanguage],
  );
  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useI18n = () => useContext(LanguageContext);

export function LanguageSwitch() {
  const { language, setLanguage, t } = useI18n();
  return (
    <div
      className="language-switch"
      role="group"
      aria-label={t("Interface language")}
      title={t("Interface language. Presentations stay in English.")}
    >
      {(["en", "ru"] as const).map((value) => (
        <button
          key={value}
          type="button"
          lang={value}
          aria-label={value === "en" ? "English" : "Русский"}
          aria-pressed={language === value}
          onClick={() => setLanguage(value)}
        >
          {value.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
