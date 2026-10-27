/**
 * Dynamic Catalog & Dropdown Hydration Module (Phase 3 Remediation).
 * Replaces static hardcoded <select> options with live database records from GET /admissions/metadata.
 */
import { apiFetch } from "./api.js";

function formatCurrencyKzt(amount) {
  if (!amount && amount !== 0) return "";
  return Number(amount).toLocaleString("ru-RU").replace(/,/g, " ");
}

export async function hydrateDynamicCatalogDropdowns() {
  const { ok, data } = await apiFetch("/admissions/metadata");
  if (!ok || !data) return;

  const programs = Array.isArray(data.programs) ? data.programs : [];
  const untSubjects = Array.isArray(data.unt_subjects) ? data.unt_subjects : [];

  // 1. Hydrate Tuition Calculator Program Select (#tuition-program-select)
  const tuitionSelect = document.getElementById("tuition-program-select");
  if (tuitionSelect && programs.length > 0) {
    const previousValue = tuitionSelect.value || "sdu-cs";
    tuitionSelect.innerHTML = "";

    const bachelorPrograms = programs.filter(
      (p) => !p.degree || p.degree.toLowerCase().includes("bachelor")
    );
    const listToRender = bachelorPrograms.length > 0 ? bachelorPrograms : programs;

    for (const prog of listToRender) {
      const opt = document.createElement("option");
      opt.value = prog.id;
      const costFormatted = formatCurrencyKzt(prog.approx_cost_per_year_kzt);
      opt.textContent = costFormatted
        ? `${prog.name} (${costFormatted} ₸/yr)`
        : prog.name;
      if (prog.id === previousValue) {
        opt.selected = true;
      }
      tuitionSelect.appendChild(opt);
    }
  }

  // 2. Hydrate UNT Subject Selects (#unt-subject-1 and #unt-subject-2)
  const subj1 = document.getElementById("unt-subject-1");
  const subj2 = document.getElementById("unt-subject-2");

  if (untSubjects.length > 0) {
    if (subj1) {
      const prev1 = subj1.value || "Mathematics";
      subj1.innerHTML = "";
      for (const s of untSubjects) {
        const opt = document.createElement("option");
        opt.value = s.value;
        opt.textContent = s.label;
        if (s.value === prev1) opt.selected = true;
        subj1.appendChild(opt);
      }
    }
    if (subj2) {
      const prev2 = subj2.value || "Computer Science";
      subj2.innerHTML = "";
      for (const s of untSubjects) {
        const opt = document.createElement("option");
        opt.value = s.value;
        opt.textContent = s.label;
        if (s.value === prev2) opt.selected = true;
        subj2.appendChild(opt);
      }
    }
  }
}
