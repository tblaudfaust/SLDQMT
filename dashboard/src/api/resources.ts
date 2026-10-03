import { api } from "./client";

export interface Resource {
  key: string;
  title: string;
  description: string;
  file_name: string;
  kind: "pdf" | "docx" | "apk" | string;
  opens_in_tab: boolean;
  available: boolean;
  size_bytes?: number | null;
  updated_at?: string | null;
}

/** Ask the server for a short-lived link, then open it in a new tab (PDF) or start the download. */
export async function openResource(r: Pick<Resource, "key" | "opens_in_tab" | "file_name">) {
  const { url } = await api.post<{ url: string }>(`/resources/${r.key}/link`);
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  if (r.opens_in_tab) a.target = "_blank";
  else a.download = r.file_name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export async function openResourceByKey(key: string) {
  const list = await api.get<Resource[]>("/resources");
  const r = list.find((x) => x.key === key);
  if (!r) throw new Error("Unknown resource");
  if (!r.available) throw new Error(`${r.title} has not been uploaded to the server yet`);
  await openResource(r);
}
