import { useCallback, useState } from "react";
import { StudyDrawer } from "@/components/StudyDrawer";

interface StudyTarget {
  topic: string;
  role?: string;
  company?: string;
}

/**
 * Owns the open/closed wiring for a StudyDrawer so call sites only say
 * "study this topic". Four components were repeating the same null-state,
 * `open={topic !== null}` and `topic ?? ""` glue.
 *
 * Usage:
 *   const { openStudy, studyDrawer } = useStudyDrawer();
 *   <button onClick={() => openStudy("RAG", { role: "AI Engineer" })} />
 *   {studyDrawer}
 */
export const useStudyDrawer = () => {
  const [target, setTarget] = useState<StudyTarget | null>(null);

  const openStudy = useCallback((topic: string, context: Omit<StudyTarget, "topic"> = {}) => {
    if (!topic.trim()) return;
    setTarget({ topic: topic.trim(), ...context });
  }, []);

  const closeStudy = useCallback(() => setTarget(null), []);

  const studyDrawer = (
    <StudyDrawer
      open={target !== null}
      onOpenChange={(open) => !open && closeStudy()}
      topic={target?.topic ?? ""}
      role={target?.role}
      company={target?.company}
    />
  );

  return { openStudy, closeStudy, studyDrawer, isOpen: target !== null };
};
