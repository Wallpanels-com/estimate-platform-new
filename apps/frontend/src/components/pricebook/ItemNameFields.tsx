import { useEffect, useRef, useState } from "react";
import { Field } from "../ui";
import { useI18n } from "../../lib/i18n";
import russian from "../../lib/ru.json";

type Translator = {
  translate: (text: string) => Promise<string>;
  destroy?: () => void;
};
type Factory = {
  create: (options: {
    sourceLanguage: string;
    targetLanguage: string;
  }) => Promise<Translator>;
};

export default function ItemNameFields({
  initialName,
  initialRussian,
  onTranslating,
}: {
  initialName: string;
  initialRussian: string;
  onTranslating: (busy: boolean) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(initialName);
  const [nameRu, setNameRu] = useState(initialRussian);
  const [status, setStatus] = useState<"idle" | "pending" | "unavailable">(
    "idle",
  );
  const manual = useRef(Boolean(initialRussian.trim()));
  const task = useRef<Promise<Translator | null> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const generation = useRef(0);

  function schedule(source: string) {
    clearTimeout(timer.current);
    const id = ++generation.current;
    if (manual.current) {
      setStatus("idle");
      return;
    }
    const text = source.trim();
    if (!text) {
      setNameRu("");
      setStatus("idle");
      return;
    }
    const known = (russian as Record<string, string>)[text];
    if (known) {
      setNameRu(known);
      setStatus("idle");
      return;
    }
    const factory = (window as unknown as { Translator?: Factory }).Translator;
    if (!factory) {
      setNameRu("");
      setStatus("unavailable");
      return;
    }
    setStatus("pending");
    // Start creation directly in the input event, preserving browser activation
    // for the first local language-model download. Never send names to a server.
    if (!task.current) {
      try {
        task.current = factory
          .create({ sourceLanguage: "en", targetLanguage: "ru" })
          .catch(() => {
            task.current = null;
            return null;
          });
      } catch {
        setNameRu("");
        setStatus("unavailable");
        return;
      }
    }
    const currentTask = task.current;
    timer.current = setTimeout(async () => {
      try {
        const translator = await currentTask;
        const translated = translator
          ? (await translator.translate(text)).trim()
          : "";
        if (id !== generation.current || manual.current) return;
        if (!translated || translated.length > 200) {
          setNameRu("");
          setStatus("unavailable");
          return;
        }
        setNameRu(translated);
        setStatus("idle");
      } catch {
        if (task.current === currentTask) task.current = null;
        if (id === generation.current && !manual.current) {
          setNameRu("");
          setStatus("unavailable");
        }
      }
    }, 450);
  }
  useEffect(() => {
    schedule(initialName);
    return () => {
      clearTimeout(timer.current);
      ++generation.current;
      const previous = task.current;
      task.current = null;
      void previous?.then((t) => t?.destroy?.());
    };
  }, []);
  useEffect(() => {
    onTranslating(status === "pending");
    return () => onTranslating(false);
  }, [status, onTranslating]);
  return (
    <>
      <Field label={t("Item name (EN)")}>
        <input
          name="name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            schedule(e.target.value);
          }}
          onFocus={() => {
            if (status === "unavailable" && !manual.current) schedule(name);
          }}
          required
          maxLength={200}
        />
      </Field>
      <Field
        label={t("Item name (RU)")}
        hint={t(
          status === "pending"
            ? "Translating locally in your browser…"
            : status === "unavailable"
              ? "Automatic translation is unavailable in this browser. Enter the Russian name manually."
              : "Translated automatically. You can correct the Russian name.",
        )}
      >
        <input
          name="name_ru"
          value={nameRu}
          onChange={(e) => {
            manual.current = Boolean(e.target.value.trim());
            ++generation.current;
            clearTimeout(timer.current);
            setNameRu(e.target.value);
            setStatus("idle");
            if (!manual.current) schedule(name);
          }}
          maxLength={200}
          aria-busy={status === "pending"}
        />
      </Field>
    </>
  );
}
