const form = document.querySelector("#scoreForm");
const resumeInput = document.querySelector("#resume");
const jobsInput = document.querySelector("#jobs");
const resumeCount = document.querySelector("#resumeCount");
const jobsCount = document.querySelector("#jobsCount");
const resumeFile = document.querySelector("#resumeFile");
const fileStatus = document.querySelector("#fileStatus");
const resumeCard = document.querySelector("#resumeCard");
const statusLine = document.querySelector("#status");
const submitButton = document.querySelector("#submitButton");
const sampleButton = document.querySelector("#sampleButton");
const heroSample = document.querySelector("#heroSample");
const resultsSection = document.querySelector("#results");
const resultMeta = document.querySelector("#resultMeta");
const rankingList = document.querySelector("#rankingList");
const jobDetail = document.querySelector("#jobDetail");
const copyButton = document.querySelector("#copyButton");
const downloadButton = document.querySelector("#downloadButton");

let latestResult = null;
let latestSamplePromise = null;
let selectedJobIndex = 0;
const demoMode = new URLSearchParams(window.location.search).get("demo");
if (demoMode) document.body.dataset.demo = demoMode;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function updateCounts() {
  resumeCount.textContent = `${resumeInput.value.length.toLocaleString()} characters`;
  jobsCount.textContent = `${jobsInput.value.length.toLocaleString()} characters`;
}

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function fitClass(label) {
  if (label === "Strong fit") return "";
  if (label === "Worth tailoring") return "tailoring";
  if (label === "Stretch") return "stretch";
  return "low";
}

function loadSample(scroll = true) {
  if (!latestSamplePromise) {
    latestSamplePromise = fetch("/api/sample").then((response) => {
      if (!response.ok) throw new Error("The example could not be loaded.");
      return response.json();
    });
  }
  setStatus("Loading the fictional example…");
  return latestSamplePromise
    .then((sample) => {
      resumeInput.value = sample.resume;
      jobsInput.value = sample.jobs;
      updateCounts();
      setStatus("Example loaded. Press “Rank my roles” to build the shortlist.");
      if (scroll) {
        document.querySelector("#workspace").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    })
    .catch((error) => setStatus(error.message, true));
}

async function importResume(file) {
  if (!file) return;
  if (file.size > 8_000_000) {
    fileStatus.textContent = "File is larger than 8 MB.";
    fileStatus.classList.add("error");
    return;
  }
  fileStatus.textContent = `Reading ${file.name} locally…`;
  fileStatus.classList.remove("error");
  try {
    const response = await fetch(`/api/extract?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "This file could not be read.");
    resumeInput.value = payload.text;
    updateCounts();
    fileStatus.textContent = `${file.name} · ${payload.characters.toLocaleString()} characters`;
    setStatus("Resume imported locally. Review the extracted text before ranking jobs.");
  } catch (error) {
    fileStatus.textContent = error.message;
    fileStatus.classList.add("error");
    setStatus(error.message, true);
  } finally {
    resumeFile.value = "";
  }
}

async function score(scroll = true) {
  const resume = resumeInput.value.trim();
  const jobs = jobsInput.value.trim();
  if (resume.length < 20) {
    setStatus("Add a little more resume text so evidence can be compared.", true);
    resumeInput.focus();
    return false;
  }
  if (!jobs) {
    setStatus("Add at least one job description.", true);
    jobsInput.focus();
    return false;
  }

  submitButton.disabled = true;
  setStatus("Matching requirements against your resume…");
  try {
    const response = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume, jobs }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "The analysis could not be completed.");
    latestResult = payload;
    renderResults(payload, scroll);
    setStatus(`Ranked ${payload.jobs.length} role${payload.jobs.length === 1 ? "" : "s"} locally.`);
    return true;
  } catch (error) {
    setStatus(error.message, true);
    return false;
  } finally {
    submitButton.disabled = false;
  }
}

function renderRanking(jobs) {
  rankingList.replaceChildren();
  jobs.forEach((job, index) => {
    const button = element("button", "ranking-item");
    button.type = "button";
    button.dataset.index = String(index);
    button.setAttribute("aria-label", `${job.title} at ${job.company}, score ${job.score}`);
    button.setAttribute("aria-pressed", String(index === selectedJobIndex));

    const score = element("span", "ranking-score", job.score);
    const copy = element("span", "ranking-copy");
    copy.append(
      element("strong", "", job.title),
      element("small", "", job.company),
    );
    const gapCount = element(
      "span",
      `gap-count${job.missing_must.length ? " has-gaps" : ""}`,
      job.missing_must.length ? `${job.missing_must.length} gaps` : "clear",
    );

    button.append(score, copy, gapCount);
    button.addEventListener("click", () => selectJob(index));
    rankingList.append(button);
  });
}

function evidenceSection(matched) {
  if (!matched.length) return null;
  const section = element("section", "detail-section");
  section.append(element("h4", "", "Why this role matched"));
  const list = element("div", "evidence-list");
  for (const match of matched.slice(0, 8)) {
    const details = element("details", "evidence-item");
    const summary = element("summary");
    summary.append(
      element("span", "", match.skill),
      element(
        "span",
        "evidence-priority",
        match.priority === "must" ? "MUST-HAVE" : "PREFERRED",
      ),
    );
    details.append(summary);
    for (const evidence of match.evidence) {
      details.append(element("p", "evidence-copy", evidence));
    }
    list.append(details);
  }
  section.append(list);
  return section;
}

function gapSection(job) {
  if (!job.missing_must.length && !job.missing_preferred.length) return null;
  const section = element("section", "detail-section");
  section.append(element("h4", "", "What is missing"));
  const grid = element("div", "gap-grid");

  if (job.missing_must.length) {
    const column = element("div", "gap-column");
    column.append(element("h5", "", "Must-have"));
    const chips = element("div", "chip-list");
    for (const gap of job.missing_must) chips.append(element("span", "chip must-gap", gap));
    column.append(chips);
    grid.append(column);
  }

  if (job.missing_preferred.length) {
    const column = element("div", "gap-column");
    column.append(element("h5", "", "Preferred"));
    const chips = element("div", "chip-list");
    for (const gap of job.missing_preferred) chips.append(element("span", "chip", gap));
    column.append(chips);
    grid.append(column);
  }
  section.append(grid);
  return section;
}

function flagSection(job) {
  if (!job.red_flags.length) return null;
  const section = element("section", "detail-section");
  section.append(element("h4", "", "Check before applying"));
  const list = element("div", "flag-list");
  for (const flag of job.red_flags) {
    const row = element("div", "flag");
    row.append(
      element("strong", "", flag.label),
      element("p", "", flag.detail),
    );
    list.append(row);
  }
  section.append(list);
  return section;
}

function actionSection(actions) {
  const section = element("section", "detail-section");
  section.append(element("h4", "", "Your next best actions"));
  const list = element("ol", "action-list");
  for (const action of actions) list.append(element("li", "", action));
  section.append(list);
  return section;
}

function renderDetail(job) {
  jobDetail.replaceChildren();

  const top = element("header", "detail-top");
  const score = element("div", "detail-score");
  score.style.setProperty("--score", job.score);
  score.append(element("strong", "", job.score));

  const heading = element("div", "detail-heading");
  const badges = element("div", "detail-badges");
  badges.append(
    element("span", `fit-badge ${fitClass(job.label)}`.trim(), job.label),
    element("span", "confidence-badge", `${job.confidence} confidence`),
  );
  heading.append(badges, element("h3", "", job.title));

  const company = element("p", "company-details");
  for (const value of [job.company, job.location, job.salary].filter(Boolean)) {
    company.append(element("span", "", value));
  }
  heading.append(company);
  top.append(score, heading);
  jobDetail.append(top, element("p", "detail-summary", job.summary));

  const metrics = element("div", "metric-grid");
  for (const [value, label] of [
    [`${job.must_coverage}%`, "must-have coverage"],
    [job.requirement_count, "requirements found"],
    [job.matched.length, "evidence matches"],
  ]) {
    const card = element("div", "metric-card");
    card.append(element("strong", "", value), element("span", "", label));
    metrics.append(card);
  }
  jobDetail.append(metrics);

  const evidence = evidenceSection(job.matched);
  if (evidence) jobDetail.append(evidence);
  const gaps = gapSection(job);
  if (gaps) jobDetail.append(gaps);
  const flags = flagSection(job);
  if (flags) jobDetail.append(flags);
  jobDetail.append(actionSection(job.next_actions));
}

function selectJob(index) {
  if (!latestResult?.jobs?.[index]) return;
  selectedJobIndex = index;
  for (const button of rankingList.querySelectorAll(".ranking-item")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.index) === index));
  }
  renderDetail(latestResult.jobs[index]);
}

function renderResults(result, scroll = true) {
  selectedJobIndex = 0;
  const top = result.jobs[0];
  resultMeta.textContent =
    `${result.jobs.length} roles ranked · top match: ${top.title} at ${top.company} · processed locally`;
  renderRanking(result.jobs);
  renderDetail(top);
  resultsSection.hidden = false;
  if (scroll) resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function copyTopSummary() {
  const job = latestResult?.jobs?.[selectedJobIndex];
  if (!job) return;
  const gaps = job.missing_must.length
    ? `Must-have gaps: ${job.missing_must.join(", ")}.`
    : "No recognized must-have gaps.";
  const text =
    `${job.title} @ ${job.company}\n` +
    `Fit ${job.score}/100 (${job.label})\n` +
    `${job.summary}\n${gaps}\nNext: ${job.next_actions[0]}`;
  try {
    await navigator.clipboard.writeText(text);
    setStatus("Shortlist summary copied.");
  } catch {
    setStatus("Clipboard access was blocked. Use Export JSON instead.", true);
  }
}

function downloadJson() {
  if (!latestResult) return;
  const blob = new Blob([JSON.stringify(latestResult, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "applyless-shortlist.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

resumeInput.addEventListener("input", updateCounts);
jobsInput.addEventListener("input", updateCounts);
resumeFile.addEventListener("change", () => importResume(resumeFile.files[0]));
sampleButton.addEventListener("click", () => loadSample());
heroSample.addEventListener("click", () => loadSample());
copyButton.addEventListener("click", copyTopSummary);
downloadButton.addEventListener("click", downloadJson);
form.addEventListener("submit", (event) => {
  event.preventDefault();
  score();
});
resumeCard.addEventListener("dragover", (event) => {
  event.preventDefault();
  resumeCard.classList.add("dragging");
});
resumeCard.addEventListener("dragleave", () => resumeCard.classList.remove("dragging"));
resumeCard.addEventListener("drop", (event) => {
  event.preventDefault();
  resumeCard.classList.remove("dragging");
  importResume(event.dataTransfer.files[0]);
});

updateCounts();

if (demoMode) {
  setTimeout(async () => {
    await loadSample(false);
    if (demoMode === "form") return;
    const didScore = await score(false);
    if (!didScore) return;
    if (demoMode === "evidence") {
      const firstEvidence = document.querySelector(".evidence-item");
      if (firstEvidence) firstEvidence.open = true;
    }
  }, 80);
}
