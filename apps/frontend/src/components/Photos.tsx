import { useI18n } from "../lib/i18n";
import { useRef, useState } from "react";
import { ImagePlus, Expand, Trash2, Upload, Star } from "lucide-react";
import type { Zone } from "../lib/types";
import { Button, Confirm, Modal, useNotice } from "./ui";
import ActionMenu from "./ActionMenu";
import ProtectedImage from "./ProtectedImage";
export default function Photos({
  zone,
  onUpload,
  onDelete,
  busy,
  finalMode = false,
  presentationSlot,
  onSelectPresentationPhoto,
}: {
  zone: Zone;
  onUpload: (slot: number, file: File) => void;
  onDelete: (slot: number) => void;
  busy: boolean;
  finalMode?: boolean;
  presentationSlot?: number | null;
  onSelectPresentationPhoto?: (slot: number) => void;
}) {
  const { t } = useI18n();

  const [view, setView] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const notify = useNotice();
  const input = useRef<HTMLInputElement>(null);
  const uploadSlot = useRef(1);
  const availableSlot = [1, 2, 3, 4].find(
    (slot) => !zone.images.some((p) => p.slot === slot),
  );
  const selectedSlot = zone.images.some((p) => p.slot === presentationSlot)
    ? presentationSlot
    : [...zone.images].sort((a, b) => a.slot - b.slot)[0]?.slot;
  function choose(slot: number) {
    uploadSlot.current = slot;
    input.current?.click();
  }
  function upload(slot: number, file?: File) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
      return notify("Choose a JPEG, PNG, or WebP image.", true);
    if (file.size > 20 * 1024 * 1024)
      return notify("Choose an image smaller than 20 MB.", true);
    onUpload(slot, file);
  }
  return (
    <section className="photos-panel" aria-label={t("Zone photographs")}>
      <div className="rail-heading">
        <h2>{t("Zone photos")}</h2>
        <span>{zone.images.length} / 4</span>
      </div>
      {finalMode && !zone.images.length ? (
        <p className="rail-footnote" role="status">
          <strong>
            {t(
              "Add at least one photo to this zone to generate a Final Estimate.",
            )}
          </strong>
        </p>
      ) : null}
      <div className="photo-slots">
        {[...zone.images]
          .sort((a, b) => a.slot - b.slot)
          .map((photo) => (
            <div className="photo-slot filled" key={photo.slot}>
              <button
                className="photo-open"
                aria-label={t("View photo {0}", photo.slot)}
                onClick={() => setView(photo.slot)}
              >
                <ProtectedImage
                  imageId={photo.id}
                  alt={photo.original_name || t("Zone photo {0}", photo.slot)}
                  width={420}
                  height={315}
                  loading="lazy"
                />
                <Expand size={17} aria-hidden="true" />
              </button>
              <div className="photo-controls">
                <span title={photo.original_name || undefined}>
                  {t("Photo")} {photo.slot}
                </span>
                <div className="photo-actions">
                  {finalMode ? (
                    <button
                      type="button"
                      className="photo-presentation-choice"
                      aria-pressed={photo.slot === selectedSlot}
                      aria-label={t(
                        "Use photo {0} in this zone’s Final Estimate",
                        photo.slot,
                      )}
                      title={t(
                        photo.slot === selectedSlot
                          ? "Selected for this zone’s Final Estimate"
                          : "Use in this zone’s Final Estimate",
                      )}
                      disabled={busy}
                      onClick={() => onSelectPresentationPhoto?.(photo.slot)}
                    >
                      <Star
                        size={17}
                        fill={
                          photo.slot === selectedSlot ? "currentColor" : "none"
                        }
                        aria-hidden="true"
                      />
                    </button>
                  ) : null}
                  <ActionMenu
                    label={t("Actions for photo {0}", photo.slot)}
                    disabled={busy}
                    actions={[
                      {
                        label: "Replace photo",
                        icon: <Upload size={15} />,
                        onSelect: () => choose(photo.slot),
                      },
                      {
                        label: "Remove photo",
                        icon: <Trash2 size={15} />,
                        danger: true,
                        onSelect: () => setDeleting(photo.slot),
                      },
                    ]}
                  />
                </div>
              </div>
            </div>
          ))}
      </div>
      {availableSlot ? (
        <Button
          className={`photo-add full-width ${zone.images.length ? "" : "photo-add-empty"}`}
          disabled={busy}
          onClick={() => choose(availableSlot)}
        >
          <ImagePlus size={19} aria-hidden="true" />
          {t("Add photo")}
        </Button>
      ) : null}
      <input
        ref={input}
        className="file-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label={t("Upload zone photo")}
        disabled={busy}
        onChange={(e) => {
          upload(uploadSlot.current, e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <p className="rail-footnote">
        {t("Up to 4 photos · JPEG, PNG, WebP")}
        <br />
        {t(
          finalMode
            ? "Only the starred photo is used in this zone’s Final Estimate. The first photo is selected by default."
            : "Included in this zone’s PDF.",
        )}
      </p>
      {view !== null ? (
        <Modal title={t("Photo {0}", view)} onClose={() => setView(null)} wide>
          <div className="photo-view">
            <ProtectedImage
              imageId={zone.images.find((i) => i.slot === view)!.id}
              alt={t("Full photograph {0}", view)}
              width={1000}
              height={750}
            />
          </div>
        </Modal>
      ) : null}
      {deleting !== null ? (
        <Confirm
          title={t("Remove this photo?")}
          action={t("Remove photo")}
          onClose={() => setDeleting(null)}
          onConfirm={() => {
            onDelete(deleting);
            setDeleting(null);
          }}
        >
          {t(
            "The image will be removed from this zone. You can upload it again later.",
          )}
        </Confirm>
      ) : null}
    </section>
  );
}
