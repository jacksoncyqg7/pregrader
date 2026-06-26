import { useState } from "react";
import "./DefectReport.css";

export default function DefectReport({
  report,
  frontImage,
  backImage,
  frontSurfaceImage,
  backSurfaceImage,
}) {
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [embossment, setEmbossment] = useState(100);

  if (!report) return null;

  const normalizedReport = normalizeReport(report);
  const canInspect = Boolean(frontImage || backImage);

  return (
    <main className="defect-page">
      <div className="report-shell">
        <section className="hero-grid">
          <button
            type="button"
            className="card-preview"
            onClick={() => setIsInspectorOpen(true)}
            disabled={!canInspect}
            aria-label="Open embossed front and back card inspector"
          >
            {frontImage ? (
              <>
                <img src={frontImage} alt="Front card preview" className="preview-card-image" />
                <span className="preview-inspection-hint">
                  Tap for detailed inspection of card
                </span>
              </>
            ) : (
              <span className="preview-placeholder">No image</span>
            )}
          </button>

          <div className="hero-main">
            <div className="hero-heading">
              <p className="eyebrow">AI Card Review</p>
              <h1>Visible Defect Report</h1>
              <p>
                AI-assisted review of front and back condition, surface,
                centering, corners, and edges.
              </p>
            </div>

            <div className="score-grid">
              <ScoreCard
                title="Centering"
                score={normalizedReport.scores.centering}
                icon="+"
                accent="blue"
              />
              <ScoreCard
                title="Corners"
                score={normalizedReport.scores.corners}
                icon="L"
                accent="purple"
              />
              <ScoreCard
                title="Edges"
                score={normalizedReport.scores.edges}
                icon="|"
                accent="cyan"
              />
              <ScoreCard
                title="Surface"
                score={normalizedReport.scores.surface}
                icon="*"
                accent="green"
              />
            </div>
          </div>

          <GradeBadge
            grade={normalizedReport.estimatedGrade}
            label={normalizedReport.gradeLabel}
          />
        </section>

        <section className="insight-card">
          <div className="insight-icon">*</div>
          <div>
            <h2>AI Summary Insight</h2>
            <p>{normalizedReport.summary}</p>
          </div>
        </section>

          <ReportSection
            title="Front"
            findings={normalizedReport.front}
          />
          <ReportSection
            title="Back"
            findings={normalizedReport.back}
          />

        {normalizedReport.limitations.length > 0 && (
          <section className="defect-report-card">
            <div className="section-title">
              <span>!</span>
              <h2>Inspection Limitations</h2>
            </div>

            <div className="finding-list">
              {normalizedReport.limitations.map((limitation, index) => (
                <article className="finding-row limitation-row" key={`limit-${index}`}>
                  <div className="finding-icon limitation">!</div>
                  <div className="finding-name">
                    <h3>Limitation {index + 1}</h3>
                  </div>
                  <p className="finding-description">{limitation}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>

      {isInspectorOpen && (
        <CardInspector
          frontImage={frontImage}
          backImage={backImage}
          frontSurfaceImage={frontSurfaceImage}
          backSurfaceImage={backSurfaceImage}
          embossment={embossment}
          setEmbossment={setEmbossment}
          onClose={() => setIsInspectorOpen(false)}
        />
      )}
    </main>
  );
}

function CardInspector({
  frontImage,
  backImage,
  frontSurfaceImage,
  backSurfaceImage,
  embossment,
  setEmbossment,
  onClose,
}) {
  return (
    <div
      className="inspector-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div className="inspector-panel" onClick={(event) => event.stopPropagation()}>
        <div className="inspector-header">
          <div>
            <p className="eyebrow">Embossed Images</p>
            <h2>Front and Back Inspection</h2>
          </div>
        </div>

        <div className="inspector-body">
          <div className="inspector-images">
            <InspectableCard
              title="Front"
              image={frontImage}
              surfaceImage={frontSurfaceImage}
              embossment={embossment}
            />
            <InspectableCard
              title="Back"
              image={backImage}
              surfaceImage={backSurfaceImage}
              embossment={embossment}
            />
          </div>

          <div className="embossment-control">
            <input
              type="range"
              min="0"
              max="100"
              value={embossment}
              onChange={(event) => setEmbossment(Number(event.target.value))}
              aria-label="Embossment overlay intensity"
            />
            <span>{embossment}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function InspectableCard({ title, image, surfaceImage, embossment }) {
  return (
    <section className="inspect-card">
      <h3>{title}</h3>
      <div className="inspect-image-shell">
        {image ? (
          <img
            src={image}
            alt={`${title} card`}
            className="inspect-image"
          />
        ) : (
          <div className="inspect-placeholder">
            No {title.toLowerCase()} image
          </div>
        )}

        {surfaceImage && (
          <img
            src={surfaceImage}
            alt={`${title} embossed overlay`}
            className="inspect-surface-image"
            style={{ opacity: embossment / 100 }}
          />
        )}
      </div>
    </section>
  );
}

function normalizeReport(report) {
  return {
    estimatedGrade: Number(report.estimatedGrade ?? report.estimated_grade ?? 0),
    gradeLabel: report.gradeLabel ?? report.grade_band ?? "Pre-grade estimate",
    summary: report.summary ?? "No summary returned.",
    limitations: Array.isArray(report.limitations) ? report.limitations : [],
    scores: {
      centering: Number(report.scores?.centering ?? report.subgrades?.centering ?? 0),
      corners: Number(report.scores?.corners ?? report.subgrades?.corners ?? 0),
      edges: Number(report.scores?.edges ?? report.subgrades?.edges ?? 0),
      surface: Number(report.scores?.surface ?? report.subgrades?.surface ?? 0),
    },
    front: normalizeFindings(report.front ?? report.front_findings),
    back: normalizeFindings(report.back ?? report.back_findings),
  };
}

function normalizeFindings(findings) {
  if (!Array.isArray(findings) || findings.length === 0) {
    return [
      {
        type: "none",
        category: "No visible defects reported",
        severity: "None",
        confidence: 0,
        description: "The model did not report visible defects for this side.",
      },
    ];
  }

  return findings.map((finding) => ({
    type: normalizeType(finding.type),
    category: finding.category ?? formatCategory(finding.type, finding.location),
    severity: finding.severity ?? "Minor",
    confidence: normalizeConfidence(finding.confidence),
    description: finding.description ?? "No description returned.",
  }));
}

function normalizeType(type) {
  const value = String(type ?? "").toLowerCase();

  if (value.includes("corner")) return "corner";
  if (value.includes("edge")) return "edge";
  if (value.includes("surface") || value.includes("scratch") || value.includes("dent")) {
    return "surface";
  }
  if (value.includes("center")) return "centering";
  if (value === "none") return "none";

  return "surface";
}

function formatCategory(type, location) {
  const label = String(type ?? "Finding")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

  return location ? `${label} - ${location}` : label;
}

function normalizeConfidence(confidence) {
  const value = Number(confidence || 0);

  if (value <= 1) {
    return Math.round(value * 100);
  }

  return Math.round(value);
}

function ScoreCard({ title, score, icon, accent }) {
  const safeScore = Number(score || 0);
  const percent = Math.min(safeScore * 10, 100);

  return (
    <article className={`score-card ${accent}`}>
      <div className="score-top">
        <span className="score-icon">{icon}</span>
        <span>{title}</span>
      </div>

      <div className="score-value">
        {safeScore.toFixed(1)}
        <span>/10</span>
      </div>

      <div className="score-bar">
        <div style={{ width: `${percent}%` }} />
      </div>
    </article>
  );
}

function GradeBadge({ grade, label }) {
  const safeGrade = Number(grade || 0);
  const gradeDegrees = Math.max(0, Math.min(safeGrade, 10)) * 36;

  return (
    <aside className="grade-card" style={{ "--grade-degrees": `${gradeDegrees}deg` }}>
      <p>Estimated Grade</p>

      <div className="grade-ring">
        <div>
          <strong>{safeGrade.toFixed(1)}</strong>
          <span>{label}</span>
        </div>
      </div>
    </aside>
  );
}

function ReportSection({ title, findings }) {
  return (
    <section className="defect-report-card">
      <div className="section-title">
        <span>{title === "Front" ? "F" : "B"}</span>
        <h2>{title}</h2>
      </div>

      <div className="finding-list">
        {findings.map((finding, index) => (
          <FindingRow key={`${title}-${index}`} finding={finding} />
        ))}
      </div>
    </section>
  );
}

function FindingRow({ finding }) {
  return (
    <article className="finding-row">
      <div className={`finding-icon ${finding.type}`}>
        {getFindingIcon(finding.type)}
      </div>

      <div className="finding-name">
        <h3>{finding.category}</h3>
      </div>

      <SeverityBadge severity={finding.severity} />

      <div className="confidence-pill">{finding.confidence}% confidence</div>

      <p className="finding-description">{finding.description}</p>
    </article>
  );
}

function SeverityBadge({ severity }) {
  const normalized = String(severity || "minor").toLowerCase();

  return <span className={`severity-badge ${normalized}`}>{severity}</span>;
}

function getFindingIcon(type) {
  switch (type) {
    case "centering":
      return "+";
    case "corner":
      return "L";
    case "edge":
      return "|";
    case "surface":
      return "*";
    case "none":
      return "-";
    default:
      return ".";
  }
}
