import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request, errorMessage } from "../lib/api";
import { type PageKey } from "../lib/access";
import { useI18n } from "../lib/i18n";
import type { User } from "../lib/types";
import { Button, ErrorNotice, Loading, Modal, useNotice } from "./ui";

import PageAccessOptions from "./PageAccessOptions";

type Access = {
  pages: PageKey[];
  updated_at: string;
  protected_owner: boolean;
};
export default function UserAccess({
  user,
  onClose,
}: {
  user: User;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [saving, setSaving] = useState(false);
  const query = useQuery({
    queryKey: ["user-access", user.id],
    queryFn: () => request<Access>(`/users/${user.id}/access`),
    staleTime: 0,
    retry: false,
  });
  return (
    <Modal
      title={t("Page access")}
      onClose={() => {
        if (!saving) onClose();
      }}
    >
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <div className="modal-body">
          <ErrorNotice retry={() => void query.refetch()}>
            {errorMessage(query.error)}
          </ErrorNotice>
        </div>
      ) : query.data ? (
        <AccessForm
          key={query.data.updated_at}
          user={user}
          access={query.data}
          onClose={onClose}
          reload={() => void query.refetch()}
          onSaving={setSaving}
        />
      ) : null}
    </Modal>
  );
}
function AccessForm({
  user,
  access,
  onClose,
  reload,
  onSaving,
}: {
  user: User;
  access: Access;
  onClose: () => void;
  reload: () => void;
  onSaving: (busy: boolean) => void;
}) {
  const { t } = useI18n();
  const notify = useNotice();
  const client = useQueryClient();
  const [pages, setPages] = useState<PageKey[]>(access.pages);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const changed =
    pages.length !== access.pages.length ||
    pages.some((page) => !access.pages.includes(page));
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        onSaving(true);
        setError("");
        try {
          await request(`/users/${user.id}/access`, {
            method: "PUT",
            body: JSON.stringify({
              pages,
              expected_updated_at: access.updated_at,
            }),
          });
          await client.invalidateQueries({ queryKey: ["team-users"] });
          await client.invalidateQueries({ queryKey: ["me"] });
          notify("Page access saved");
          onClose();
        } catch (err) {
          setError(errorMessage(err));
        } finally {
          setBusy(false);
          onSaving(false);
        }
      }}
    >
      <div className="modal-body access-body" aria-busy={busy}>
        <div>
          <strong>{user.name || user.email}</strong>
          <p className="form-hint">{user.email}</p>
        </div>
        <p className="form-hint">
          {t(
            "Choose which pages this employee can open. Changes apply to their current session.",
          )}
        </p>
        {error ? <ErrorNotice retry={reload}>{error}</ErrorNotice> : null}
        <PageAccessOptions
          pages={pages}
          onChange={setPages}
          disabled={busy || access.protected_owner}
        />
        {access.protected_owner ? (
          <p className="form-hint">
            {t("Your account always has access to all pages.")}
          </p>
        ) : !pages.length ? (
          <p className="form-hint">
            {t(
              "No pages selected. This employee will see an access request screen after signing in.",
            )}
          </p>
        ) : null}
      </div>
      <footer className="modal-footer">
        <Button onClick={onClose} disabled={busy}>
          {t("Cancel")}
        </Button>
        <Button
          type="submit"
          variant="primary"
          busy={busy}
          disabled={!changed || access.protected_owner}
        >
          {t("Save access")}
        </Button>
      </footer>
    </form>
  );
}
