import { useState, useEffect, useCallback } from "react";
import { Button, Input, Textarea, Card, makeStyles, tokens, typographyStyles } from "@fluentui/react-components";
import { AddRegular as Add, DeleteRegular as Delete, SparkleRegular as Sparkle } from "@fluentui/react-icons";
import { notifyToast } from "../lib/toast";

const BACKEND = "http://127.0.0.1:8000";

interface GlossaryItem {
  source: string;
  target: string;
}

interface Glossary {
  id: string;
  name: string;
  count: number;
  items?: GlossaryItem[];
}

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", gap: "24px" },
  title: { ...typographyStyles.subtitle1, marginBottom: "8px" },
  list: { display: "flex", flexDirection: "column", gap: "8px" },
  card: { padding: "16px", cursor: "pointer" },
  cardSelected: { padding: "16px", cursor: "pointer", border: `2px solid ${tokens.colorBrandForeground1}` },
  form: { display: "flex", flexDirection: "column", gap: "12px" },
  row: { display: "flex", gap: "8px", alignItems: "center" },
  input: { flex: 1 },
  generateBtn: { marginTop: "12px" },
});

export default function GlossaryManager() {
  const s = useStyles();
  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [selected, setSelected] = useState<Glossary | null>(null);
  const [newName, setNewName] = useState("");
  const [items, setItems] = useState<GlossaryItem[]>([{ source: "", target: "" }]);
  const [isGenerating, setIsGenerating] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND}/api/glossaries/`);
      const d = await r.json();
      setGlossaries(d.glossaries || []);
    } catch (e) {
      console.warn("[GlossaryManager] Failed to load list:", e);
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  const loadGlossary = async (id: string) => {
    try {
      const r = await fetch(`${BACKEND}/api/glossaries/${id}`);
      const d = await r.json();
      setSelected(d);
      setItems(d.items?.length ? d.items : [{ source: "", target: "" }]);
    } catch {
      notifyToast.error("Failed to load glossary");
    }
  };

  const saveGlossary = async () => {
    if (!newName && !selected) return;
    const name = newName || selected?.name || "Untitled";
    try {
      const r = await fetch(`${BACKEND}/api/glossaries/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, items: items.filter(i => i.source || i.target) }),
      });
      const d = await r.json();
      notifyToast.success("Glossary saved", { description: d.id });
      setNewName("");
      loadList();
    } catch {
      notifyToast.error("Failed to save glossary");
    }
  };

  const deleteGlossary = async (id: string) => {
    try {
      await fetch(`${BACKEND}/api/glossaries/${id}`, { method: "DELETE" });
      setSelected(null);
      setItems([{ source: "", target: "" }]);
      loadList();
    } catch {
      notifyToast.error("Failed to delete glossary");
    }
  };

  const generateFromAI = async () => {
    setIsGenerating(true);
    try {
      const r = await fetch(`${BACKEND}/api/glossaries/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: "sample", source_lang: "en", target_lang: "ru" }),
      });
      const d = await r.json();
      if (d.items?.length) {
        setItems(d.items);
        notifyToast.success("AI generated suggestions", { description: `${d.items.length} terms found` });
      }
    } catch {
      notifyToast.error("AI generation failed");
    } finally {
      setIsGenerating(false);
    }
  };

  const addRow = () => setItems(prev => [...prev, { source: "", target: "" }]);
  const removeRow = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i));

  return (
    <div className={s.root}>
      <div>
        <h2 className={s.title}>Saved Glossaries</h2>
        <div className={s.list}>
          {glossaries.map(g => (
            <Card key={g.id} className={selected?.id === g.id ? s.cardSelected : s.card}
              onClick={() => loadGlossary(g.id)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600 }}>{g.name}</span>
                <span style={{ fontSize: 12, color: "var(--colorNeutralForeground3)" }}>{g.count} terms</span>
              </div>
            </Card>
          ))}
          {glossaries.length === 0 && (
            <p style={{ color: "var(--colorNeutralForeground3)", fontSize: 13 }}>No glossaries yet. Create one below.</p>
          )}
        </div>
      </div>

      <div className={s.form}>
        <h2 className={s.title}>{selected ? `Edit: ${selected.name}` : "New Glossary"}</h2>
        {!selected && (
          <Input placeholder="Glossary name (e.g. Teknorob Terms)" value={newName}
            onChange={e => setNewName(e.target.value)} />
        )}
        {items.map((item, i) => (
          <div key={i} className={s.row}>
            <Input className={s.input} placeholder={`Term ${i + 1} (original)`} value={item.source}
              onChange={e => { const copy = [...items]; copy[i].source = e.target.value; setItems(copy); }} />
            <Input className={s.input} placeholder={`Translation ${i + 1}`} value={item.target}
              onChange={e => { const copy = [...items]; copy[i].target = e.target.value; setItems(copy); }} />
            <Button appearance="subtle" icon={<Delete />} onClick={() => removeRow(i)} disabled={items.length <= 1} />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8 }}>
          <Button appearance="outline" icon={<Add />} onClick={addRow}>Add Term</Button>
          <Button appearance="outline" icon={<Sparkle />} onClick={generateFromAI} disabled={isGenerating}>
            {isGenerating ? "Generating..." : "AI Suggest"}
          </Button>
          <Button appearance="primary" onClick={saveGlossary}>Save</Button>
          {selected && (
            <Button appearance="subtle" style={{ color: "var(--colorPaletteRedForeground1)" }}
              onClick={() => deleteGlossary(selected.id)}>Delete</Button>
          )}
        </div>
      </div>
    </div>
  );
}
