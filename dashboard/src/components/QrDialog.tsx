import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Download, Printer, X } from "lucide-react";

/** A QR code for a share link, large enough to print as a poster or show on a screen, with PNG download. */
export default function QrDialog({ url, title, subtitle, onClose }: { url: string; title: string; subtitle?: string; onClose: () => void }) {
  const [png, setPng] = useState<string | null>(null);
  useEffect(() => {
    QRCode.toDataURL(url, { width: 1024, margin: 2, errorCorrectionLevel: "M", color: { dark: "#1F4E79", light: "#ffffff" } }).then(setPng).catch(() => setPng(null));
  }, [url]);
  const safe = title.replace(/[^\w]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "qr-code";
  const print = () => {
    if (!png) return;
    const w = window.open("", "_blank", "width=800,height=1000");
    if (!w) return;
    w.document.write(`<!doctype html><html><head><title>${title}</title><style>
      body{font-family:Segoe UI,Arial,sans-serif;color:#0f172a;text-align:center;margin:0;padding:32px}
      h1{font-size:28px;margin:0 0 4px;color:#1F4E79} p{margin:4px 0;font-size:16px;color:#334155}
      img{width:min(80vw,560px);height:auto;margin:20px auto;display:block;border:12px solid #fff;border-radius:16px;box-shadow:0 0 0 2px #cbd5e1}
      .url{font-family:Consolas,monospace;font-size:14px;word-break:break-all;color:#475569;margin-top:12px}
      .foot{margin-top:28px;font-size:12px;color:#64748b}
    </style></head><body>
      <p style="letter-spacing:.3em;text-transform:uppercase;font-size:12px">Statistics Sierra Leone · 2026 Population and Housing Census</p>
      <h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ""}
      <img src="${png}" alt="QR code">
      <p><b>Scan with your phone camera to open the form.</b></p>
      <div class="url">${url}</div>
      <div class="foot">Statistics Sierra Leone (Stats SL) · A.J. Momoh Street / Tower Hill · P.M.B. 595, Freetown</div>
      <script>window.onload=function(){setTimeout(function(){window.print()},200)}</script>
    </body></html>`);
    w.document.close();
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-start justify-between gap-3">
          <div><h2 className="text-lg font-semibold">{title}</h2>{subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}</div>
          <button className="text-slate-500 hover:text-slate-800" onClick={onClose} title="Close"><X size={18} /></button>
        </div>
        {png ? <img src={png} alt="QR code" className="mx-auto w-72 max-w-full rounded-md border border-slate-200" /> : <div className="py-10 text-center text-sm text-slate-400">Generating…</div>}
        <p className="mt-2 text-center text-sm text-slate-600">Scan with a phone camera to open the form.</p>
        <p className="mt-1 break-all text-center font-mono text-xs text-slate-500">{url}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {png && <a className="btn-primary" href={png} download={`${safe}-qr.png`}><Download size={16} /> Download PNG</a>}
          <button className="btn-outline" onClick={print} disabled={!png}><Printer size={16} /> Print poster</button>
        </div>
      </div>
    </div>
  );
}
