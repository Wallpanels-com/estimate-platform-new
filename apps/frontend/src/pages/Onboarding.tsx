import { useI18n } from "../lib/i18n";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Layers, Image, FileDown } from "lucide-react";
import { patch, errorMessage } from "../lib/api";
import { Button, PageHeader, useNotice } from "../components/ui";
export default function Onboarding() {
  const { t } = useI18n();

  const navigate = useNavigate();
  const client = useQueryClient();
  const notify = useNotice();
  const [busy, setBusy] = useState(false);
  async function finish() {
    setBusy(true);
    try {
      await patch("/auth/me", { onboarding_completed: true });
      await client.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    } catch (e) {
      notify(errorMessage(e), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title={t("Your estimate workspace")}
        description={t("From a room’s dimensions to a client-ready scope.")}
      />
      <section className="onboarding-guide">
        <div>
          <Layers size={24} />
          <h2>{t("Define the zones")}</h2>
          <p>
            {t(
              "Organize each wall, room, or installation area. Add dimensions and price the scope with your price book.",
            )}
          </p>
        </div>
        <div>
          <Image size={24} />
          <h2>{t("Add the project details")}</h2>
          <p>
            {t(
              "Attach site photos and materials. Review quantities, unit prices, services, and items to be discussed.",
            )}
          </p>
        </div>
        <div>
          <FileDown size={24} />
          <h2>{t("Prepare the estimate")}</h2>
          <p>
            {t(
              "Choose Pre or Final, then download the client PDF and Excel Project Passport.",
            )}
          </p>
        </div>
        <Button variant="primary" busy={busy} onClick={finish}>
          {t("Start estimating")}
        </Button>
      </section>
    </>
  );
}
