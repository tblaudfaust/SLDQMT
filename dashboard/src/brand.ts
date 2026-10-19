/** The same application is served on two names: the field-monitoring dashboard and the
 *  Monitoring & Evaluation address (censusme.statistics.sl). Pages brand themselves by host. */
export const isMeSite = typeof window !== "undefined" && /^censusme\./i.test(window.location.hostname);

/** Field mode: inside the SLPHC M&E Field Tool Android app (or a browser opened with ?app=1) the site shows only
 *  the sign-in, the KPI form and the reports on the device. Remembered on the device once seen. */
export const isAppMode = (() => {
  if (typeof window === "undefined") return false;
  try {
    const q = new URLSearchParams(window.location.search).get("app");
    if (q === "1" || /SLPHCFieldTool/.test(navigator.userAgent)) { localStorage.setItem("fm_app_mode", "1"); return true; }
    if (q === "0") { localStorage.removeItem("fm_app_mode"); return false; }
    return localStorage.getItem("fm_app_mode") === "1";
  } catch { return /SLPHCFieldTool/.test(navigator.userAgent); }
})();

export const siteTitle = isAppMode ? "M&E Field Tool" : isMeSite ? "Monitoring & Evaluation" : "Field Monitor Error Follow-up";
export const siteSubtitle = isAppMode ? "Sign in with your M&E account" : isMeSite ? "Training evaluations and results" : "Dashboard and reports";

if (typeof document !== "undefined" && isAppMode) document.title = "SLPHC M&E Field Tool";
else if (typeof document !== "undefined" && isMeSite) document.title = "Statistics Sierra Leone · Monitoring & Evaluation";
