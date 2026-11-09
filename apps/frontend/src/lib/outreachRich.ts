export function outreachLine(line: string) {
  const match = line.match(
    /^(Вітаю!?|Про компанію|Про вакансію|Наступний крок|Умови|Сайт|Instagram|Інстаграм|Hello!?|About the company|About the role|Next step|Working arrangements|Website)([:!]?(?:\s|$).*)?$/iu,
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
          (heading
            ? '<strong style="font-weight:700">' + escape(heading) + "</strong>"
            : "") + escape(rest)
        );
      })
      .join("<br>") +
    "</div>"
  );
}
// RTF uses UTF-16 signed escapes, preserving Ukrainian letters and emoji.
const rtfText = (text: string) => {
  let result = "";
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (text[i] === "\\" || text[i] === "{" || text[i] === "}")
      result += "\\" + text[i];
    else if (code > 127) result += `\\u${code > 32767 ? code - 65536 : code}?`;
    else if (text[i] === "\t") result += "\\tab ";
    else result += text[i];
  }
  return result;
};
export function outreachRtf(message: string) {
  const body = message
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => {
      const { heading, rest } = outreachLine(line);
      return (heading ? `{\\b ${rtfText(heading)}}` : "") + rtfText(rest);
    })
    .join("\\par\n");
  return `{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\uc1\\f0\\fs24\n${body}}`;
}
export async function copyOutreach(message: string): Promise<"rich" | "plain"> {
  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    const formats = {
      "text/plain": new Blob([message], { type: "text/plain" }),
      "text/html": new Blob([outreachHtml(message)], { type: "text/html" }),
    };
    // Browsers usually prohibit native RTF writes. Never disguise an unsupported
    // MIME type as a custom web format: native Telegram would not receive it.
    if (ClipboardItem.supports?.("text/rtf")) {
      try {
        await navigator.clipboard.write([
          new ClipboardItem({
            ...formats,
            "text/rtf": new Blob([outreachRtf(message)], { type: "text/rtf" }),
          }),
        ]);
        return "rich";
      } catch {
        /* Retry the standard HTML payload below. */
      }
    }
    try {
      await navigator.clipboard.write([new ClipboardItem(formats)]);
      return "rich";
    } catch {
      /* Plain text remains available when rich copying is denied. */
    }
  }
  await navigator.clipboard.writeText(message);
  return "plain";
}
