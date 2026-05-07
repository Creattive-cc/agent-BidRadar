import { useEffect, useState } from "react";
import { fetchProfileFiles, fetchProfileContent, saveProfileContent } from "../services/api";

export default function ProfileEditor() {
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadFiles() {
      const listed = await fetchProfileFiles();
      setFiles(listed);
      if (listed.length) setSelected(listed[0]);
    }
    loadFiles().catch(console.error);
  }, []);

  useEffect(() => {
    if (!selected) return;
    fetchProfileContent(selected)
      .then((data) => setContent(data.content))
      .catch(console.error);
  }, [selected]);

  async function handleSave() {
    setSaving(true);
    try {
      await saveProfileContent(selected, content);
      alert("Arquivo salvo com sucesso.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold">Company Profile (.md)</h2>
      <div className="mb-3 flex gap-2">
        <select
          className="rounded border border-slate-300 px-3 py-2"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {files.map((file) => (
            <option key={file} value={file}>
              {file}
            </option>
          ))}
        </select>
        <button
          className="rounded bg-blue-600 px-3 py-2 text-white hover:bg-blue-500 disabled:opacity-50"
          onClick={handleSave}
          disabled={!selected || saving}
        >
          {saving ? "Salvando..." : "Salvar"}
        </button>
      </div>
      <textarea
        className="h-64 w-full rounded border border-slate-300 p-3 font-mono text-sm"
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
    </div>
  );
}
