/** The same application is served on two names: the field-monitoring dashboard and the
 *  Monitoring & Evaluation address (censusme.statistics.sl). Pages brand themselves by host. */
export const isMeSite = typeof window !== "undefined" && /^censusme\./i.test(window.location.hostname);

export const siteTitle = isMeSite ? "Monitoring & Evaluation" : "Field Monitor Error Follow-up";
export const siteSubtitle = isMeSite ? "Training evaluations and results" : "Dashboard and reports";

if (typeof document !== "undefined" && isMeSite) document.title = "Statistics Sierra Leone · Monitoring & Evaluation";
