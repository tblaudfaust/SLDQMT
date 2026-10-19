import { registerSW } from "virtual:pwa-register";

/* ------------------------------------------------------------------------------------------------
 * Web app updates on the devices. The service worker precaches the app; a new build is picked up by
 * checking the server when the app opens, comes back online, returns to the front (Android), every
 * 30 minutes, and when the officer taps "Check for updates". When a new version has installed the
 * page reloads itself, except while the officer is in the form: then the reload waits until they
 * leave it (drafts are saved on every change anyway).
 * ---------------------------------------------------------------------------------------------- */

const FORM_PATH = /^\/me\/kpi\/(new|report\/)/;
let reloadPending = false;
let reg: ServiceWorkerRegistration | undefined;

export const isFormPath = (path = window.location.pathname) => FORM_PATH.test(path);

/** Called on every route change: apply a deferred reload once the officer is out of the form. */
export function reloadIfPending(path: string) {
  if (reloadPending && !isFormPath(path)) {
    reloadPending = false;
    window.location.reload();
  }
}

/** Ask the server for a newer build. "updating" means one was found and is installing (the page reloads by itself). */
export async function checkForUpdate(): Promise<"updating" | "current" | "offline" | "unavailable"> {
  if (!navigator.onLine) return "offline";
  if (!reg) return "unavailable";
  try {
    await reg.update();
    return reg.installing || reg.waiting ? "updating" : "current";
  } catch {
    return "offline";
  }
}

export function installAppUpdates() {
  registerSW({
    immediate: true,
    onNeedReload() {
      if (isFormPath()) reloadPending = true;
      else window.location.reload();
    },
    onRegisteredSW(_url, r) {
      if (!r) return;
      reg = r;
      const check = () => { if (navigator.onLine) r.update().catch(() => undefined); };
      window.setInterval(check, 30 * 60 * 1000);
      window.addEventListener("online", check);
      window.addEventListener("slphc:resume", check);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") check(); });
    },
  });
}
