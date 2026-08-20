/**
 * Browser-download helper — first download flow in this frontend (Export
 * downloads always used to be Streamlit's st.download_button; there's no
 * server-side persistence anywhere in this app, so this stays client-only).
 */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
