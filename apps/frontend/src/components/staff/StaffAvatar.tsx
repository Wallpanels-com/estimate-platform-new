import { tokenStorage } from "../../lib/portal";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { API_ORIGIN, TOKEN_KEY } from "../../lib/api";
import type { StaffMember } from "../../lib/staff";

/** Same HR-protected photo is shared between table, chart and profile in memory. */
export default function StaffAvatar({
  person,
  className = "staff-avatar",
}: {
  person: Pick<StaffMember, "id" | "name" | "avatar_url">;
  className?: string;
}) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  const path = person.avatar_url;
  const image = useQuery({
    queryKey: ["staff-avatar", path],
    enabled: !!path?.startsWith(`/api/v1/hr/staff/${person.id}/avatar?`),
    staleTime: Infinity,
    gcTime: 60_000,
    retry: false,
    queryFn: async ({ signal }) => {
      const response = await fetch(`${API_ORIGIN}${path}`, {
        headers: {
          Authorization: `Bearer ${tokenStorage.getItem(TOKEN_KEY) || ""}`,
        },
        signal,
      });
      if (response.status === 401)
        window.dispatchEvent(new Event("wallpanels:unauthorized"));
      if (response.status === 403)
        window.dispatchEvent(new Event("wallpanels:access-changed"));
      return response.ok && response.status !== 204 ? response.blob() : null;
    },
  });
  useEffect(() => {
    setFailed(false);
    if (!image.data) {
      setUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(image.data);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [image.data, path]);
  return (
    <span className={`${className} staff-avatar-photo`} aria-hidden="true">
      {person.name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((n) => n[0])
        .join("")}
      {url && !failed && (
        <img
          src={url}
          alt=""
          decoding="async"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}
