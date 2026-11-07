/** Labels/structured questionnaire choices only; original application data is never rewritten. */
const answers: Record<string, string> = {
  "a1–a2 (начальный)": "A1–A2 (beginner)",
  "b1 (средний)": "B1 (intermediate)",
  "b2 (выше среднего)": "B2 (upper intermediate)",
  "c1–c2 (продвинутый)": "C1–C2 (advanced)",
  "свободное владение": "Fluent",
  "1–3 года": "1–3 years",
  "3–5 лет": "3–5 years",
  "5–8 лет": "5–8 years",
  "более 3 лет": "More than 3 years",
  "более 5 лет": "More than 5 years",
  "более 8 лет": "More than 8 years",
  "менее 1 года": "Less than 1 year",
  "до 1 года": "Less than 1 year",
  нет: "No",
  да: "Yes",
  "могу вести рабочую коммуникацию (b1–b2)": "Working proficiency (B1–B2)",
  "могу свободно общаться с клиентами (b2+)":
    "Confident client communication (B2+)",
  "не использую английский в работе": "Do not use English at work",
  "понимаю английский, но не говорю свободно":
    "Understand English; limited speaking proficiency",
  "есть базовый опыт": "Basic experience",
  "нет опыта": "No experience",
  "хорошо читаю и понимаю": "Read and understand confidently",
  "нет, работал(а) самостоятельно": "Worked independently",
  "управлял(а) командой 2–5 человек": "Managed a team of 2–5",
  "управлял(а) командой более 5 человек": "Managed a team of more than 5",
  "управлял(а) подрядчиками": "Managed contractors",
  "да, интерьерные проекты и ремонты": "Yes, interiors and renovation",
  "да, проекты по изготовлению мебели на заказ":
    "Yes, custom furniture projects",
  "какой у вас уровень английского?": "English level",
  "какой у вас уровень разговорного английского?": "Spoken English level",
  "есть ли у вас опыт работы с американским рынком?": "US market experience",
  "насколько хорошо вы читаете технические чертежи?":
    "Technical drawing skills",
  "сколько лет опыта у вас в управлении проектами (project management)?":
    "Project management experience",
  "был ли у вас опыт управления маркетинговой командой или подрядчиками?":
    "Marketing team or contractor management",
  "есть ли у вас опыт работы в мебельной или интерьерной сфере?":
    "Furniture or interiors experience",
};
export const criteria: Record<string, string> = {
  experience: "Experience",
  english: "English",
  us_market: "US market",
  drawings: "Technical drawings",
};
export function hrText(value: string, language: string) {
  const clean = value.replaceAll("_", " ");
  return language === "en"
    ? answers[clean.toLowerCase().trim()] || clean
    : clean;
}
