export function outreachLine(line: string) {
  const match = line.match(
    /^(Вітаю!?|Про компанію|Про вакансію|Наступний крок|Умови|Сайт|Instagram|Інстаграм)([:!]?(?:\s|$).*)?$/u,
  );
  if (!match) return { heading: "", rest: line };
  const suffix = match[2] || "";
  const punctuation = suffix.match(/^[:!]/)?.[0] || "";
  return {
    heading: match[1] + punctuation,
    rest: suffix.slice(punctuation.length),
  };
}
const escape = (text: string) =>
  text.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
export function outreachHtml(message: string) {
  return (
    "<div>" +
    message
      .split("\n")
      .map((line) => {
        const { heading, rest } = outreachLine(line);
        return (
          (heading ? "<strong>" + escape(heading) + "</strong>" : "") +
          escape(rest)
        );
      })
      .join("<br>") +
    "</div>"
  );
}
export async function copyOutreach(message: string): Promise<"rich" | "plain"> {
  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/plain": new Blob([message], { type: "text/plain" }),
          "text/html": new Blob([outreachHtml(message)], { type: "text/html" }),
        }),
      ]);
      return "rich";
    } catch {
      /* Older clients can still copy readable plain text. */
    }
  }
  await navigator.clipboard.writeText(message);
  return "plain";
}
