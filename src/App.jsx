import { useState } from "react";
import DefectReport from "./components/DefectReport.jsx";
import "./App.css";

function ManualCenteringAdjuster({ title, image, box, setBox }) {
  const displayWidth = 360;
  const displayHeight = 502;

  const outer = box.outer;
  const inner = box.inner;

  const leftBorder = inner.left - outer.left;
  const rightBorder = outer.right - inner.right;
  const topBorder = inner.top - outer.top;
  const bottomBorder = outer.bottom - inner.bottom;

  const horizontalTotal = leftBorder + rightBorder;
  const verticalTotal = topBorder + bottomBorder;

  const leftPercent =
    horizontalTotal <= 0 ? 50 : Math.round((leftBorder / horizontalTotal) * 100);
  const rightPercent = 100 - leftPercent;

  const topPercent =
    verticalTotal <= 0 ? 50 : Math.round((topBorder / verticalTotal) * 100);
  const bottomPercent = 100 - topPercent;

  const startDrag = (boxType, edge, event) => {
    event.preventDefault();

    const wrapper = event.currentTarget
      .closest(".drag-preview-wrapper")
      .getBoundingClientRect();

    const getPointerPosition = (pointerEvent) => {
      if (pointerEvent.touches && pointerEvent.touches.length > 0) {
        return {
          x: pointerEvent.touches[0].clientX - wrapper.left,
          y: pointerEvent.touches[0].clientY - wrapper.top,
        };
      }

      return {
        x: pointerEvent.clientX - wrapper.left,
        y: pointerEvent.clientY - wrapper.top,
      };
    };

    const handleMove = (moveEvent) => {
      moveEvent.preventDefault();

      const { x, y } = getPointerPosition(moveEvent);

      setBox((prev) => {
        const next = structuredClone(prev);

        if (boxType === "outer") {
          if (edge === "left") {
            next.outer.left = Math.max(0, Math.min(x, next.outer.right - 40));
          }

          if (edge === "right") {
            next.outer.right = Math.min(
              displayWidth,
              Math.max(x, next.outer.left + 40)
            );
          }

          if (edge === "top") {
            next.outer.top = Math.max(0, Math.min(y, next.outer.bottom - 40));
          }

          if (edge === "bottom") {
            next.outer.bottom = Math.min(
              displayHeight,
              Math.max(y, next.outer.top + 40)
            );
          }

          // Keep inner box inside outer box
          next.inner.left = Math.max(next.inner.left, next.outer.left + 5);
          next.inner.right = Math.min(next.inner.right, next.outer.right - 5);
          next.inner.top = Math.max(next.inner.top, next.outer.top + 5);
          next.inner.bottom = Math.min(next.inner.bottom, next.outer.bottom - 5);
        }

        if (boxType === "inner") {
          if (edge === "left") {
            next.inner.left = Math.max(
              next.outer.left + 5,
              Math.min(x, next.inner.right - 20)
            );
          }

          if (edge === "right") {
            next.inner.right = Math.min(
              next.outer.right - 5,
              Math.max(x, next.inner.left + 20)
            );
          }

          if (edge === "top") {
            next.inner.top = Math.max(
              next.outer.top + 5,
              Math.min(y, next.inner.bottom - 20)
            );
          }

          if (edge === "bottom") {
            next.inner.bottom = Math.min(
              next.outer.bottom - 5,
              Math.max(y, next.inner.top + 20)
            );
          }
        }

        return next;
      });
    };

    const stopDrag = () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", stopDrag);

      window.removeEventListener("touchmove", handleMove);
      window.removeEventListener("touchend", stopDrag);
      window.removeEventListener("touchcancel", stopDrag);
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", stopDrag);

    window.addEventListener("touchmove", handleMove, { passive: false });
    window.addEventListener("touchend", stopDrag);
    window.addEventListener("touchcancel", stopDrag);
  };

  return (
    <div className="manual-card">
      <h3>{title}</h3>

      <div
        className="drag-preview-wrapper"
        style={{
          width: `${displayWidth}px`,
          height: `${displayHeight}px`,
        }}
      >
        <img src={image} alt={title} className="drag-preview" />

        {/* Outer card border */}
        <div
          className="adjust-box outer-box"
          style={{
            left: `${outer.left}px`,
            top: `${outer.top}px`,
            width: `${outer.right - outer.left}px`,
            height: `${outer.bottom - outer.top}px`,
          }}
        >
          <div
            className="drag-line vertical left outer"
            onMouseDown={(event) => startDrag("outer", "left", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line vertical right outer"
            onMouseDown={(event) => startDrag("outer", "right", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line horizontal top outer"
            onMouseDown={(event) => startDrag("outer", "top", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line horizontal bottom outer"
            onMouseDown={(event) => startDrag("outer", "bottom", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
        </div>

        {/* Inner print border */}
        <div
          className="adjust-box inner-box"
          style={{
            left: `${inner.left}px`,
            top: `${inner.top}px`,
            width: `${inner.right - inner.left}px`,
            height: `${inner.bottom - inner.top}px`,
          }}
        >
          <div
            className="drag-line vertical left inner"
            onMouseDown={(event) => startDrag("inner", "left", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line vertical right inner"
            onMouseDown={(event) => startDrag("inner", "right", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line horizontal top inner"
            onMouseDown={(event) => startDrag("inner", "top", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
          <div
            className="drag-line horizontal bottom inner"
            onMouseDown={(event) => startDrag("inner", "bottom", event)}
            onTouchStart={(event) => startDrag("outer", "left", event)}
          />
        </div>
      </div>

      <div className="manual-result">
        <strong>
          L|R {leftPercent}|{rightPercent}
        </strong>
        <strong>
          T|B {topPercent}|{bottomPercent}
        </strong>
      </div>

      <div className="box-help">
        <p>
          <span className="red-text">Red box</span> = outer card edge
        </p>
        <p>
          <span className="green-text">Green box</span> = inner print border
        </p>
        <p>Drag the border lines directly to align the card.</p>
      </div>
    </div>
  );
}

function App() {
  const [frontImage, setFrontImage] = useState(null);
  const [backImage, setBackImage] = useState(null);
  const [gradeResult, setGradeResult] = useState(null);
  const [page, setPage] = useState("home");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [uploadingSide, setUploadingSide] = useState(null);
  const [frontDebugImage, setFrontDebugImage] = useState(null);
  const [backDebugImage, setBackDebugImage] = useState(null);

  const [manualFrontBox, setManualFrontBox] = useState({
    outer: {
      left: 8,
      top: 8,
      right: 352,
      bottom: 494,
    },
    inner: {
      left: 38,
      top: 45,
      right: 322,
      bottom: 455,
    },
  });

  const [manualBackBox, setManualBackBox] = useState({
    outer: {
      left: 8,
      top: 8,
      right: 352,
      bottom: 494,
    },
    inner: {
      left: 38,
      top: 45,
      right: 322,
      bottom: 455,
    },
  });

  const handleImageUpload = async (event, side) => {
    const file = event.target.files[0];

    if (!file) return;

    setUploadingSide(side);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:8000/straighten-card", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        alert(data.error || "Failed to process image");
        return;
      }

      if (!data.success) {
        alert(
          "Could not perfectly detect the card border. Showing normalized image instead."
        );
      }

      if (side === "front") {
        setFrontImage(data.straightened_image);
        setFrontDebugImage(data.debug_image);
      } else {
        setBackImage(data.straightened_image);
        setBackDebugImage(data.debug_image);
      }
    } catch (error) {
      console.error(error);
      alert("Backend is not running or image processing failed.");
    } finally {
      setUploadingSide(null);
    }
  };

  const generateSurfaceEnhancement = async (image) => {
    if (!image) return null;

    try {
      const response = await fetch("http://127.0.0.1:8000/surface-enhance", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ image }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(data.error || "Failed to generate surface enhancement");
        return null;
      }

      return data.surface_image;
    } catch (error) {
      console.error(error);
      alert("Backend is not running or surface enhancement failed.");
      return null;
    }
  };

  const startGrading = async () => {
    if (!frontImage || !backImage) {
      alert("Please upload both front and back of the card.");
      return;
    }

    setPage("loading");
    setProgress(0);

    try {
      setProgress(25);
      setCurrentStep("Straightening the card");
      await new Promise((resolve) => setTimeout(resolve, 300));

      setProgress(50);
      setCurrentStep("Calculating manual centering");
      const frontManualCentering = calculateManualCentering(manualFrontBox);
      const backManualCentering = calculateManualCentering(manualBackBox);

      await new Promise((resolve) => setTimeout(resolve, 300));

      setProgress(70);
      setCurrentStep("Generating embossed surface layers");
      const frontSurface = await generateSurfaceEnhancement(frontImage);
      const backSurface = await generateSurfaceEnhancement(backImage);

      if (!frontSurface || !backSurface) {
        alert("Failed to generate embossed surface layer.");
        setPage("home");
        return;
      }

      setProgress(90);
      setCurrentStep("Sending original and embossed images to VLM");

      const vlmResponse = await fetch("http://127.0.0.1:8000/vlm-grade-card", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          front_image: frontImage,
          back_image: backImage,
          front_surface_image: frontSurface,
          back_surface_image: backSurface,
          front_centering: frontManualCentering,
          back_centering: backManualCentering,
        }),
      });

      const vlmData = await vlmResponse.json();

      if (!vlmResponse.ok) {
        alert(vlmData.error || "VLM grading failed");
        setPage("home");
        return;
      }

      const vlmReport = vlmData.report;

      setProgress(100);
      setCurrentStep("Preparing report");
      await new Promise((resolve) => setTimeout(resolve, 300));

      setGradeResult({
        success: true,
        openaiReport: vlmReport,
        estimated_grade: vlmReport.estimated_grade,
        grade_band: vlmReport.grade_band,
        confidence: vlmReport.confidence,
        subgrades: vlmReport.subgrades,
        summary: vlmReport.summary,
        limitations: vlmReport.limitations,
        front: {
          centering: frontManualCentering,
          overlay_image: frontImage,
          surface_image: frontSurface,
          manual_box: manualFrontBox,
          vlm_findings: vlmReport.front_findings,
        },
        back: {
          centering: backManualCentering,
          overlay_image: backImage,
          surface_image: backSurface,
          manual_box: manualBackBox,
          vlm_findings: vlmReport.back_findings,
        },
        flaws: [
          ...(vlmReport.front_findings || []).map(
            (item) => `Front ${item.location}: ${item.description}`
          ),
          ...(vlmReport.back_findings || []).map(
            (item) => `Back ${item.location}: ${item.description}`
          ),
        ],
      });

      setPage("report");
    } catch (error) {
      console.error(error);
      alert("Grading failed.");
      setPage("home");
    }
  };

  const calculateManualCentering = (box) => {
    const displayWidth = 360;
    const displayHeight = 502;
    const outer = box.outer;
    const inner = box.inner;

    const leftBorder = inner.left - outer.left;
    const rightBorder = outer.right - inner.right;
    const topBorder = inner.top - outer.top;
    const bottomBorder = outer.bottom - inner.bottom;

    const horizontalTotal = leftBorder + rightBorder;
    const verticalTotal = topBorder + bottomBorder;

    const leftPercent =
      horizontalTotal <= 0 ? 50 : Math.round((leftBorder / horizontalTotal) * 100);

    const rightPercent = 100 - leftPercent;

    const topPercent =
      verticalTotal <= 0 ? 50 : Math.round((topBorder / verticalTotal) * 100);

    const bottomPercent = 100 - topPercent;

    return {
      left: leftPercent,
      right: rightPercent,
      top: topPercent,
      bottom: bottomPercent,
      borderPixels: {
        left: Math.round(leftBorder),
        right: Math.round(rightBorder),
        top: Math.round(topBorder),
        bottom: Math.round(bottomBorder),
      },
      cardBoundaryPercent: {
        left: Math.round((outer.left / displayWidth) * 100),
        top: Math.round((outer.top / displayHeight) * 100),
        right: Math.round((outer.right / displayWidth) * 100),
        bottom: Math.round((outer.bottom / displayHeight) * 100),
      },
    };
  };

  const resetApp = () => {
    setFrontImage(null);
    setBackImage(null);
    setGradeResult(null);
    setProgress(0);
    setCurrentStep("");
    setPage("home");
    setFrontDebugImage(null);
    setBackDebugImage(null);
  };

  const rotateImage180 = (side) => {
    const imageSrc = side === "front" ? frontImage : backImage;

    if (!imageSrc) return;

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");

      canvas.width = img.width;
      canvas.height = img.height;

      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(Math.PI);
      ctx.drawImage(img, -img.width / 2, -img.height / 2);

      const rotatedImage = canvas.toDataURL("image/jpeg", 0.95);

      if (side === "front") {
        setFrontImage(rotatedImage);
      } else {
        setBackImage(rotatedImage);
      }
    };

    img.src = imageSrc;
  };

  if (page === "loading") {
    return (
      <div className="app">
        <div className="loading-card">
          <h1>Grading your card...</h1>

          <div className="progress-bar-background">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            ></div>
          </div>

          <p className="progress-text">{progress}% completed</p>
          <p className="step-text">{currentStep}</p>

          <div className="steps-list">
            <p className={progress >= 25 ? "done" : ""}>
              1. Straightening the card
            </p>
            <p className={progress >= 50 ? "done" : ""}>
              2. Identifying borders and centering
            </p>
            <p className={progress >= 75 ? "done" : ""}>
              3. Adding grading layer
            </p>
            <p className={progress >= 100 ? "done" : ""}>
              4. Detecting indents, whitening, and scratches
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (page === "report") {
    return (
      <>
        <DefectReport
          report={gradeResult?.openaiReport ?? gradeResult}
          frontImage={gradeResult?.front?.overlay_image ?? frontImage}
          backImage={gradeResult?.back?.overlay_image ?? backImage}
          frontSurfaceImage={gradeResult?.front?.surface_image}
          backSurfaceImage={gradeResult?.back?.surface_image}
        />
        <div className="report-actions">
          <button onClick={resetApp} className="secondary-button">
            Grade another card
          </button>
        </div>
      </>
    );

  }

  return (
    <div className="app">
      <div className="home-card">
        <h1>Pokémon Card Pre-Grader</h1>
        <p className="subtitle">
          Upload scanned images of the front and back of your card.
        </p>

        <div className="upload-grid">
          <div className="upload-box">
          <h2>Front of Card</h2>

          {uploadingSide === "front" ? (
            <div className="placeholder">Straightening front card...</div>
          ) : frontImage ? (
            <img src={frontImage} alt="Front preview" className="preview" />
          ) : (
            <div className="placeholder">No front image uploaded</div>
          )}

          {frontDebugImage && (
            <>
              <p className="debug-label">Detected outline</p>
              <img src={frontDebugImage} alt="Front debug" className="debug-preview" />
            </>
          )}

          {frontImage && (
            <button
              type="button"
              className="rotate-button"
              onClick={() => rotateImage180("front")}
            >
              Rotate Front 180°
            </button>
          )}

          {frontImage && (
            <ManualCenteringAdjuster
              title="Adjust Front Borders"
              image={frontImage}
              box={manualFrontBox}
              setBox={setManualFrontBox}
            />
          )}

          <label className="upload-button">
            Upload Front
            <input
              type="file"
              accept="image/*"
              onChange={(event) => handleImageUpload(event, "front")}
            />
          </label>
        </div>

          <div className="upload-box">
            <h2>Back of Card</h2>

            {uploadingSide === "back" ? (
              <div className="placeholder">Straightening back card...</div>
            ) : backImage ? (
              <img src={backImage} alt="Back preview" className="preview" />
            ) : (
              <div className="placeholder">No back image uploaded</div>
            )}

            {backDebugImage && (
              <>
                <p className="debug-label">Detected outline</p>
                <img src={backDebugImage} alt="Back debug" className="debug-preview" />
              </>
            )}

            {backImage && (
              <button
                type="button"
                className="rotate-button"
                onClick={() => rotateImage180("back")}
              >
                Rotate Back 180°
              </button>
            )}

            {backImage && (
              <ManualCenteringAdjuster
                title="Adjust Back Borders"
                image={backImage}
                box={manualBackBox}
                setBox={setManualBackBox}
              />
            )}

            <label className="upload-button">
              Upload Back
              <input
                type="file"
                accept="image/*"
                onChange={(event) => handleImageUpload(event, "back")}
              />
            </label>
          </div>
        </div>

        <button onClick={startGrading} className="grade-button">
          Grade this card
        </button>
      </div>
    </div>
  );
}

export default App;
