import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type ImageInfo = {
  name: string;
  size_bytes: number;
  path: string;
};

type RunResult = {
  image: string;
  image_key: string;
  site_count: number;
  json: string;
  csv: string;
  overlay: string;
  preprocessed: string;
  mask: string;
};

type RunSummary = {
  run_id: string;
  image_count: number;
  site_count: number;
  results: RunResult[];
  autotune?: AutoTunePayload;
};

type Roi = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type RoiBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type AutoTuneCandidate = {
  score: number;
  site_count: number;
  nearest_neighbor_distance_px: number | null;
  distance_std_px: number | null;
  parameters: Params & {
    mask_bottom_fraction: number;
    mask_dark_threshold: number;
  };
};

type AutoTunePayload = {
  roi: Roi;
  best_parameters: AutoTuneCandidate["parameters"];
  top_candidates: AutoTuneCandidate[];
};

type Site = {
  id: number;
  x_px: number;
  y_px: number;
  intensity?: number;
  confidence?: number;
  filled?: boolean;
  periodic_filled?: boolean;
};

type EditTool = "point" | "box-delete" | "box-redetect";

type Params = {
  mode: "bright" | "dark";
  sigma_min: number;
  sigma_max: number;
  num_sigma: number;
  threshold_rel: number;
  min_distance: number;
  background_sigma: number;
  refine_method: "centroid" | "gaussian";
  refine_window: number;
  neighbors_k: number;
  fill_lattice: boolean;
  fill_strength: number;
  fill_iterations: number;
};

const defaultParams: Params = {
  mode: "bright",
  sigma_min: 1,
  sigma_max: 6,
  num_sigma: 10,
  threshold_rel: 0.08,
  min_distance: 4,
  background_sigma: 30,
  refine_method: "centroid",
  refine_window: 7,
  neighbors_k: 6,
  fill_lattice: true,
  fill_strength: 0.35,
  fill_iterations: 1
};

type SliderParam = {
  key: keyof Pick<
    Params,
    | "sigma_min"
    | "sigma_max"
    | "num_sigma"
    | "threshold_rel"
    | "min_distance"
    | "background_sigma"
    | "refine_window"
    | "neighbors_k"
    | "fill_strength"
    | "fill_iterations"
  >;
  label: string;
  min: number;
  max: number;
  step: number;
  unit?: string;
  decimals?: number;
};

const sliderParams: SliderParam[] = [
  { key: "sigma_min", label: "sigma min", min: 0.5, max: 8, step: 0.1, decimals: 1 },
  { key: "sigma_max", label: "sigma max", min: 1, max: 12, step: 0.1, decimals: 1 },
  { key: "num_sigma", label: "num sigma", min: 3, max: 24, step: 1 },
  { key: "threshold_rel", label: "threshold", min: 0.01, max: 0.5, step: 0.01, decimals: 2 },
  { key: "min_distance", label: "min dist", min: 1, max: 30, step: 1, unit: "px" },
  { key: "background_sigma", label: "bg sigma", min: 1, max: 120, step: 1, unit: "px" },
  { key: "refine_window", label: "window", min: 3, max: 25, step: 1, unit: "px" },
  { key: "neighbors_k", label: "neighbors", min: 1, max: 12, step: 1 },
  { key: "fill_strength", label: "fill strength", min: 0.05, max: 0.6, step: 0.01, decimals: 2 },
  { key: "fill_iterations", label: "fill rounds", min: 0, max: 4, step: 1 }
];

function App() {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [images, setImages] = useState<ImageInfo[]>([]);
  const [selectedImage, setSelectedImage] = useState<string>("");
  const [params, setParams] = useState<Params>(defaultParams);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [selectedResult, setSelectedResult] = useState<RunResult | null>(null);
  const [editableSites, setEditableSites] = useState<Site[]>([]);
  const [editMode, setEditMode] = useState(false);
  const [editTool, setEditTool] = useState<EditTool>("point");
  const [dragSiteId, setDragSiteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [tuning, setTuning] = useState(false);
  const [imagesLoading, setImagesLoading] = useState(true);
  const [error, setError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [roi, setRoi] = useState<Roi | null>(null);
  const [roiBox, setRoiBox] = useState<RoiBox | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    reloadImages();
  }, []);

  const activeResult = useMemo(
    () => selectedResult ?? run?.results[0] ?? null,
    [selectedResult, run]
  );
  const viewerSrc = activeResult
    ? editMode
      ? activeResult.preprocessed
      : activeResult.overlay
    : selectedImage
      ? `/api/images/${encodeURIComponent(selectedImage)}/preview`
      : "";

  useEffect(() => {
    setRoi(null);
    setRoiBox(null);
    setRun(null);
    setSelectedResult(null);
  }, [selectedImage]);

  useEffect(() => {
    if (!activeResult) {
      setEditableSites([]);
      setEditMode(false);
      setEditMessage("");
      return;
    }
    apiFetch(activeResult.json)
      .then((response) => response.json())
      .then((payload) => setEditableSites(payload.sites ?? []))
      .catch((err) => setError(String(err)));
  }, [activeResult]);

  useEffect(() => {
    setEditTool("point");
    setEditMessage("");
  }, [editMode]);

  async function uploadImage(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await apiFetch("/api/images/upload", { method: "POST", body });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json();
      await reloadImages(payload.image?.name);
    } catch (err) {
      setError(String(err));
    } finally {
      event.target.value = "";
    }
  }

  async function reloadImages(selectName?: string) {
    setImagesLoading(true);
    try {
      const response = await apiFetch("/api/images");
      const payload = await response.json();
      const nextImages = payload.images ?? [];
      setImages(nextImages);
      setSelectedImage(selectName ?? nextImages[0]?.name ?? "");
      setError(nextImages.length === 0 ? "raw_tif 目录中没有找到 TIFF 图像。" : "");
    } catch (err) {
      setError(String(err));
    } finally {
      setImagesLoading(false);
    }
  }

  async function runDetection() {
    setLoading(true);
    setError("");
    setRun(null);
    setSelectedResult(null);
    try {
      const response = await apiFetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: selectedImage, ...params })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const summary = (await response.json()) as RunSummary;
      setRun(summary);
      setSelectedResult(summary.results[0] ?? null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function runAutoTune() {
    if (!roi) {
      setError("请先在图像上拖动框选一块晶格清楚的 ROI。");
      return;
    }
    setTuning(true);
    setError("");
    setRun(null);
    setSelectedResult(null);
    try {
      const response = await apiFetch("/api/autotune", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: selectedImage, roi, ...params })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const summary = (await response.json()) as RunSummary;
      if (summary.autotune?.best_parameters) {
        setParams(normalizeParams(summary.autotune.best_parameters));
      }
      setRun(summary);
      setSelectedResult(summary.results[0] ?? null);
    } catch (err) {
      setError(String(err));
    } finally {
      setTuning(false);
    }
  }

  function updateSlider(key: SliderParam["key"], value: string) {
    const nextValue = Number(value);
    setParams((current) => normalizeParams({ ...current, [key]: nextValue }));
  }

  function handleImageMouseDown(event: React.MouseEvent<HTMLDivElement>) {
    if (!imageRef.current || loading || tuning) return;
    if (editMode && activeResult) {
      const point = imagePoint(event);
      if (!point) return;
      if (editTool === "point") {
        addManualSite(point.imageX, point.imageY);
        return;
      }
      beginRoi(point);
      return;
    }
    const point = imagePoint(event);
    if (!point) return;
    beginRoi(point);
  }

  function handleImageMouseMove(event: React.MouseEvent<HTMLDivElement>) {
    if (editMode && dragSiteId !== null) {
      const point = imagePoint(event);
      if (!point) return;
      setEditableSites((sites) =>
        sites.map((site) =>
          site.id === dragSiteId ? { ...site, x_px: point.imageX, y_px: point.imageY } : site
        )
      );
      return;
    }
    if (!dragStart || !imageRef.current) return;
    const point = imagePoint(event);
    if (!point) return;
    updateRoi(point);
  }

  async function handleImageMouseUp() {
    setDragSiteId(null);
    setDragStart(null);
    if (roi && (roi.width < 16 || roi.height < 16)) {
      setRoi(null);
      setRoiBox(null);
      return;
    }
    if (editMode && roi && editTool === "box-delete") {
      deleteSitesInRoi(roi);
    }
    if (editMode && roi && editTool === "box-redetect") {
      await replaceSitesInRoi(roi);
    }
  }

  function beginRoi(point: NonNullable<ReturnType<typeof imagePoint>>) {
    setDragStart({ x: point.imageX, y: point.imageY });
    setRoi({ x: point.imageX, y: point.imageY, width: 1, height: 1 });
    setRoiBox({ left: point.viewX, top: point.viewY, width: 1, height: 1 });
  }

  function updateRoi(point: NonNullable<ReturnType<typeof imagePoint>>) {
    if (!dragStart) return;
    const x = Math.min(dragStart.x, point.imageX);
    const y = Math.min(dragStart.y, point.imageY);
    const width = Math.abs(point.imageX - dragStart.x);
    const height = Math.abs(point.imageY - dragStart.y);
    const viewStart = imageViewPoint(dragStart.x, dragStart.y);
    const left = Math.min(viewStart.x, point.viewX);
    const top = Math.min(viewStart.y, point.viewY);
    setRoi({ x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) });
    setRoiBox({ left, top, width: Math.abs(point.viewX - viewStart.x), height: Math.abs(point.viewY - viewStart.y) });
  }

  function addManualSite(x: number, y: number) {
    const nextId = Math.max(0, ...editableSites.map((site) => site.id)) + 1;
    setEditableSites((sites) => [
      ...sites,
      {
        id: nextId,
        x_px: Math.round(x),
        y_px: Math.round(y),
        intensity: 0,
        confidence: 1,
        filled: false,
        periodic_filled: false
      }
    ]);
  }

  function deleteSite(id: number) {
    setEditableSites((sites) => sites.filter((site) => site.id !== id).map((site, index) => ({ ...site, id: index + 1 })));
  }

  function deleteSitesInRoi(box: Roi) {
    setEditableSites((sites) => {
      const kept = sites.filter((site) => !siteInRoi(site, box));
      const removed = sites.length - kept.length;
      setEditMessage(`框选删除 ${removed} 个点，当前 ${kept.length} 个点。`);
      return renumberSites(kept);
    });
  }

  async function replaceSitesInRoi(box: Roi) {
    if (!activeResult || !selectedImage) return;
    setLoading(true);
    setError("");
    setEditMessage("正在重新识别框选区域...");
    try {
      const response = await apiFetch("/api/roi-detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: selectedImage, roi: box, ...params })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      const newSites = (payload.sites ?? []) as Site[];
      setEditableSites((sites) => {
        const outside = sites.filter((site) => !siteInRoi(site, box));
        const replaced = sites.length - outside.length;
        const merged = renumberSites([...outside, ...newSites]);
        setEditMessage(`框选区域替换：删除 ${replaced} 个旧点，加入 ${newSites.length} 个新点，当前 ${merged.length} 个点。`);
        return merged;
      });
    } catch (err) {
      setError(String(err));
      setEditMessage("");
    } finally {
      setLoading(false);
    }
  }

  function exportEditedCsv() {
    const rows = [
      ["site_id", "x_px", "y_px", "intensity", "confidence", "filled", "periodic_filled"],
      ...editableSites.map((site, index) => [
        String(index + 1),
        String(site.x_px),
        String(site.y_px),
        String(site.intensity ?? ""),
        String(site.confidence ?? ""),
        String(Boolean(site.filled)),
        String(Boolean(site.periodic_filled))
      ])
    ];
    const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeResult?.image_key ?? "atom_sites"}_edited_sites.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function imagePoint(event: React.MouseEvent<HTMLDivElement>) {
    const image = imageRef.current;
    if (!image) return null;
    const rect = image.getBoundingClientRect();
    const clientX = Math.min(Math.max(event.clientX, rect.left), rect.right);
    const clientY = Math.min(Math.max(event.clientY, rect.top), rect.bottom);
    const viewX = clientX - rect.left;
    const viewY = clientY - rect.top;
    return {
      imageX: Math.round((viewX / rect.width) * image.naturalWidth),
      imageY: Math.round((viewY / rect.height) * image.naturalHeight),
      viewX,
      viewY
    };
  }

  function imageViewPoint(imageX: number, imageY: number) {
    const image = imageRef.current;
    if (!image) return { x: 0, y: 0 };
    const rect = image.getBoundingClientRect();
    return {
      x: (imageX / image.naturalWidth) * rect.width,
      y: (imageY / image.naturalHeight) * rect.height
    };
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">TEM/STEM</p>
          <h1>Atom Locator</h1>
        </div>

        <div className="image-picker">
          <div className="image-picker-head">
            <span>图像</span>
            <strong>{imagesLoading ? "加载中" : `${images.length} 张`}</strong>
          </div>
          <label className="upload-button">
            上传 TIFF
            <input type="file" accept=".tif,.tiff,image/tiff" onChange={uploadImage} />
          </label>
          <div className="image-list">
            {images.map((image) => (
              <button
                key={image.name}
                className={selectedImage === image.name ? "active" : ""}
                type="button"
                onClick={() => setSelectedImage(image.name)}
                title={image.name}
              >
                <span>{image.name}</span>
                <small>{formatBytes(image.size_bytes)}</small>
              </button>
            ))}
            {!imagesLoading && images.length === 0 && (
              <div className="image-empty">没有找到 TIFF 图像</div>
            )}
          </div>
        </div>

        <div className="segmented">
          <button
            className={params.mode === "bright" ? "active" : ""}
            onClick={() => setParams((current) => ({ ...current, mode: "bright" }))}
          >
            亮峰
          </button>
          <button
            className={params.mode === "dark" ? "active" : ""}
            onClick={() => setParams((current) => ({ ...current, mode: "dark" }))}
          >
            暗峰
          </button>
        </div>

        <div className="slider-panel">
          {sliderParams.map((slider) => (
            <SliderField
              key={slider.key}
              spec={slider}
              value={params[slider.key]}
              onChange={(value) => updateSlider(slider.key, value)}
            />
          ))}
        </div>

        <div className="param-status" aria-live="polite">
          <span>{params.mode === "bright" ? "亮峰" : "暗峰"}</span>
          <span>σ {formatValue(params.sigma_min, 1)}-{formatValue(params.sigma_max, 1)}</span>
          <span>阈值 {formatValue(params.threshold_rel, 2)}</span>
          <span>间距 {params.min_distance}px</span>
          <span>邻居 {params.neighbors_k}</span>
          <span>{params.fill_lattice ? `补点 ${formatValue(params.fill_strength, 2)}` : "不补点"}</span>
        </div>

        <label className="toggle-field">
          <input
            type="checkbox"
            checked={params.fill_lattice}
            onChange={(event) => setParams((current) => ({ ...current, fill_lattice: event.target.checked }))}
          />
          <span>晶格补点</span>
        </label>

        <div className="roi-status">
          <strong>ROI</strong>
          {roi ? (
            <span>
              x {roi.x}, y {roi.y}, {roi.width} x {roi.height}px
            </span>
          ) : (
            <span>在图像上拖动框选清晰晶格区域</span>
          )}
          {roi && (
            <button type="button" onClick={() => { setRoi(null); setRoiBox(null); }}>
              清除
            </button>
          )}
        </div>

        <label className="field">
          <span>精修</span>
          <select
            value={params.refine_method}
            onChange={(event) =>
              setParams((current) => ({
                ...current,
                refine_method: event.target.value as Params["refine_method"]
              }))
            }
          >
            <option value="centroid">centroid</option>
            <option value="gaussian">gaussian</option>
          </select>
        </label>

        <button className="primary" disabled={!selectedImage || loading} onClick={runDetection}>
          {loading ? "检测中..." : "运行检测"}
        </button>
        <button className="secondary" disabled={!selectedImage || !roi || tuning || loading} onClick={runAutoTune}>
          {tuning ? "自动调参中..." : "自动调参并检测"}
        </button>
        {error && <p className="error">{error}</p>}
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Run</p>
            <h2>{run ? run.run_id : "尚未运行"}</h2>
          </div>
          <div className="metrics">
            <Metric label="图像" value={run?.image_count ?? 0} />
            <Metric label="位点" value={run?.site_count ?? 0} />
          </div>
        </header>

        <div
          className="viewer"
          onMouseDown={handleImageMouseDown}
          onMouseMove={handleImageMouseMove}
          onMouseUp={handleImageMouseUp}
          onMouseLeave={handleImageMouseUp}
        >
          {viewerSrc ? (
            <div className="image-stage">
              <img ref={imageRef} src={viewerSrc} alt="Atom detection view" draggable={false} />
              {roiBox && (
                <div
                  className="roi-box"
                  style={{
                    left: roiBox.left,
                    top: roiBox.top,
                    width: roiBox.width,
                    height: roiBox.height
                  }}
                />
              )}
              {editMode && activeResult && (
                <svg className="edit-layer" viewBox={`0 0 ${imageRef.current?.naturalWidth ?? 1} ${imageRef.current?.naturalHeight ?? 1}`}>
                  {editableSites.map((site) => (
                    <circle
                      key={site.id}
                      cx={site.x_px}
                      cy={site.y_px}
                      r={5}
                      className={site.periodic_filled || site.filled ? "site-dot filled" : "site-dot"}
                      onMouseDown={(event) => {
                        event.stopPropagation();
                        setDragSiteId(site.id);
                      }}
                      onDoubleClick={(event) => {
                        event.stopPropagation();
                        deleteSite(site.id);
                      }}
                    />
                  ))}
                </svg>
              )}
            </div>
          ) : (
            <div className="empty">选择 TIFF 图像并运行检测</div>
          )}
        </div>

        {run && (
          <div className="results-panel">
            <div className="result-tabs">
              {run.results.map((result) => (
                <button
                  key={result.image_key}
                  className={activeResult?.image_key === result.image_key ? "active" : ""}
                  onClick={() => setSelectedResult(result)}
                >
                  {result.image}
                </button>
              ))}
            </div>
            {activeResult && (
              <div className="result-details">
                <strong>{activeResult.site_count}</strong>
                <span> 个候选原子柱位点</span>
                <a href={activeResult.json} target="_blank">JSON</a>
                <a href={activeResult.csv} target="_blank">CSV</a>
                <a href={activeResult.preprocessed} target="_blank">预处理图</a>
                <a href={activeResult.mask} target="_blank">Mask</a>
                <button type="button" onClick={() => setEditMode((value) => !value)}>
                  {editMode ? "退出编辑" : "手动编辑"}
                </button>
                {editMode && <button type="button" onClick={exportEditedCsv}>导出编辑 CSV</button>}
              </div>
            )}
            {editMode && (
              <div className="edit-help">
                <div className="edit-toolbar">
                  <button className={editTool === "point" ? "active" : ""} type="button" onClick={() => setEditTool("point")}>
                    单点
                  </button>
                  <button className={editTool === "box-delete" ? "active" : ""} type="button" onClick={() => setEditTool("box-delete")}>
                    框删
                  </button>
                  <button className={editTool === "box-redetect" ? "active" : ""} type="button" onClick={() => setEditTool("box-redetect")}>
                    框选重识别
                  </button>
                </div>
                <div className="legend-row">
                  <span><i className="legend-dot red" />红点：原始检测</span>
                  <span><i className="legend-dot yellow" />黄点：晶格/周期补点</span>
                </div>
                <p>
                  {editTool === "point" && "单击空白处添加点，拖动点移动，双击点删除。"}
                  {editTool === "box-delete" && "拖动框选区域，松开鼠标后删除框内所有点。"}
                  {editTool === "box-redetect" && "拖动框选区域，松开鼠标后用当前参数重新识别并替换框内点。"}
                  当前 {editableSites.length} 个点。
                </p>
                {editMessage && <p className="edit-message">{editMessage}</p>}
              </div>
            )}
            {run.autotune && (
              <div className="tune-panel">
                <strong>自动调参 Top 5</strong>
                <div className="tune-list">
                  {run.autotune.top_candidates.map((candidate, index) => (
                    <button
                      key={`${candidate.score}-${index}`}
                      onClick={() => setParams(normalizeParams(candidate.parameters))}
                    >
                      #{index + 1} 分数 {candidate.score.toFixed(2)} / 点 {candidate.site_count} / 阈值{" "}
                      {candidate.parameters.threshold_rel.toFixed(2)} / 距离 {candidate.parameters.min_distance}px
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

function SliderField(props: { spec: SliderParam; value: number; onChange: (value: string) => void }) {
  const display = formatValue(props.value, props.spec.decimals);
  return (
    <label className="slider-field">
      <span className="slider-label">
        <span>{props.spec.label}</span>
        <strong>{display}{props.spec.unit ? ` ${props.spec.unit}` : ""}</strong>
      </span>
      <input
        type="range"
        value={props.value}
        min={props.spec.min}
        max={props.spec.max}
        step={props.spec.step}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </label>
  );
}

function normalizeParams(next: Params): Params {
  const sigmaMin = Math.min(next.sigma_min, next.sigma_max - 0.1);
  const sigmaMax = Math.max(next.sigma_max, sigmaMin + 0.1);
  return {
    ...next,
    sigma_min: round(sigmaMin, 1),
    sigma_max: round(sigmaMax, 1),
    num_sigma: Math.round(next.num_sigma),
    min_distance: Math.round(next.min_distance),
    background_sigma: Math.round(next.background_sigma),
    refine_window: Math.round(next.refine_window),
    neighbors_k: Math.round(next.neighbors_k),
    fill_iterations: Math.round(next.fill_iterations)
  };
}

function siteInRoi(site: Site, roi: Roi) {
  return (
    site.x_px >= roi.x &&
    site.x_px <= roi.x + roi.width &&
    site.y_px >= roi.y &&
    site.y_px <= roi.y + roi.height
  );
}

function renumberSites(sites: Site[]) {
  return sites.map((site, index) => ({ ...site, id: index + 1 }));
}

function round(value: number, decimals: number) {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function formatValue(value: number, decimals = 0) {
  return decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));
}

async function apiFetch(path: string, init?: RequestInit) {
  try {
    const response = await fetch(path, init);
    if (response.ok || response.status !== 404) {
      return response;
    }
  } catch {
    // Fall back to the backend port below.
  }
  return fetch(`http://127.0.0.1:8000${path}`, init);
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function csvCell(value: string) {
  if (/[",\n]/.test(value)) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

function Metric(props: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
