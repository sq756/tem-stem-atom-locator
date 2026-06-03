import SwiftUI

struct ImageItem: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let url: URL
}

struct RunSummary: Decodable {
    let run_id: String
    let output_dir: String
    let image_count: Int
    let site_count: Int
    let results: [RunResult]
}

struct RunResult: Decodable, Identifiable {
    var id: String { image }
    let image: String
    let site_count: Int
    let json: String
    let csv: String
    let overlay: String
    let preprocessed: String
}

struct DetectionSettings {
    var mode = "bright"
    var sigmaMin = "1.0"
    var sigmaMax = "6.0"
    var numSigma = "10"
    var thresholdRel = "0.08"
    var minDistance = "4"
    var backgroundSigma = "30"
    var refineMethod = "centroid"
    var refineWindow = "7"
    var neighborsK = "6"
}

struct ContentView: View {
    @State private var projectRoot = ProjectPaths.defaultRoot()
    @State private var images: [ImageItem] = []
    @State private var selectedImage: ImageItem?
    @State private var selectedResult: RunResult?
    @State private var summary: RunSummary?
    @State private var settings = DetectionSettings()
    @State private var isRunning = false
    @State private var errorMessage = ""

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        .onAppear(perform: reloadImages)
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("TEM/STEM")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
                Text("Atom Locator")
                    .font(.largeTitle.weight(.semibold))
            }

            TextField("Project root", text: $projectRoot)
                .textFieldStyle(.roundedBorder)
                .onSubmit(reloadImages)

            Picker("图像", selection: $selectedImage) {
                ForEach(images) { image in
                    Text(image.name).tag(Optional(image))
                }
            }

            Picker("峰模式", selection: $settings.mode) {
                Text("亮峰").tag("bright")
                Text("暗峰").tag("dark")
            }
            .pickerStyle(.segmented)

            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 10) {
                SettingField("sigma min", value: $settings.sigmaMin)
                SettingField("sigma max", value: $settings.sigmaMax)
                SettingField("num sigma", value: $settings.numSigma)
                SettingField("threshold", value: $settings.thresholdRel)
                SettingField("min dist", value: $settings.minDistance)
                SettingField("bg sigma", value: $settings.backgroundSigma)
                SettingField("window", value: $settings.refineWindow)
                SettingField("neighbors", value: $settings.neighborsK)
            }

            Picker("精修", selection: $settings.refineMethod) {
                Text("centroid").tag("centroid")
                Text("gaussian").tag("gaussian")
            }
            .pickerStyle(.segmented)

            HStack {
                Button("刷新图像", action: reloadImages)
                Button(isRunning ? "检测中..." : "运行检测", action: runDetection)
                    .buttonStyle(.borderedProminent)
                    .disabled(selectedImage == nil || isRunning)
            }

            if !errorMessage.isEmpty {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .textSelection(.enabled)
            }

            Spacer()
        }
        .padding(20)
        .navigationSplitViewColumnWidth(min: 320, ideal: 360, max: 420)
    }

    private var detail: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Run")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)
                    Text(summary?.run_id ?? "尚未运行")
                        .font(.title2.weight(.semibold))
                }
                Spacer()
                MetricView(label: "图像", value: summary?.image_count ?? 0)
                MetricView(label: "位点", value: summary?.site_count ?? 0)
            }

            ZStack {
                Rectangle()
                    .fill(Color.black.opacity(0.92))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                if let result = selectedResult, let image = NSImage(contentsOfFile: result.overlay) {
                    Image(nsImage: image)
                        .resizable()
                        .scaledToFit()
                        .padding(8)
                } else {
                    Text("选择 TIFF 图像并运行检测")
                        .foregroundStyle(.secondary)
                }
            }

            if let summary {
                VStack(alignment: .leading, spacing: 10) {
                    ScrollView(.horizontal) {
                        HStack {
                            ForEach(summary.results) { result in
                                Button(result.image) {
                                    selectedResult = result
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                    if let result = selectedResult {
                        HStack(spacing: 14) {
                            Text("\(result.site_count) 个候选原子柱位点")
                                .font(.headline)
                            Button("打开 JSON") { NSWorkspace.shared.open(URL(fileURLWithPath: result.json)) }
                            Button("打开 CSV") { NSWorkspace.shared.open(URL(fileURLWithPath: result.csv)) }
                            Button("打开 Overlay") { NSWorkspace.shared.open(URL(fileURLWithPath: result.overlay)) }
                        }
                    }
                }
                .padding(12)
                .background(.background)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(20)
    }

    private func reloadImages() {
        let rawURL = URL(fileURLWithPath: projectRoot).appending(path: "experimental_data/raw_tif")
        do {
            let urls = try FileManager.default.contentsOfDirectory(at: rawURL, includingPropertiesForKeys: nil)
            images = urls
                .filter { ["tif", "tiff"].contains($0.pathExtension.lowercased()) }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
                .map { ImageItem(name: $0.lastPathComponent, url: $0) }
            selectedImage = images.first
            errorMessage = images.isEmpty ? "没有在 raw_tif 中找到 TIFF 图像。" : ""
        } catch {
            images = []
            selectedImage = nil
            errorMessage = "读取图像目录失败：\(error.localizedDescription)"
        }
    }

    private func runDetection() {
        guard let selectedImage else { return }
        isRunning = true
        errorMessage = ""
        summary = nil
        selectedResult = nil
        let rootSnapshot = projectRoot
        let imagePathSnapshot = selectedImage.url.path
        let settingsSnapshot = settings

        Task.detached {
            let result = await ProcessRunner.run(
                projectRoot: rootSnapshot,
                imagePath: imagePathSnapshot,
                settings: settingsSnapshot
            )
            await MainActor.run {
                isRunning = false
                switch result {
                case .success(let runSummary):
                    summary = runSummary
                    selectedResult = runSummary.results.first
                case .failure(let error):
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}

struct SettingField: View {
    let label: String
    @Binding var value: String

    init(_ label: String, value: Binding<String>) {
        self.label = label
        self._value = value
    }

    var body: some View {
        GridRow {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField(label, text: $value)
                .textFieldStyle(.roundedBorder)
                .frame(width: 86)
        }
    }
}

struct MetricView: View {
    let label: String
    let value: Int

    var body: some View {
        VStack(alignment: .leading) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("\(value)")
                .font(.title2.weight(.semibold))
        }
        .frame(width: 82, alignment: .leading)
        .padding(10)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

enum ProjectPaths {
    static func defaultRoot() -> String {
        let cwd = FileManager.default.currentDirectoryPath
        if cwd.hasSuffix("macos/AtomLocatorMac") {
            return URL(fileURLWithPath: cwd).deletingLastPathComponent().deletingLastPathComponent().path
        }
        return cwd
    }
}

enum ProcessRunner {
    static func run(projectRoot: String, imagePath: String, settings: DetectionSettings) async -> Result<RunSummary, Error> {
        do {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
            let venvPython = URL(fileURLWithPath: projectRoot).appending(path: ".venv/bin/python").path
            let pythonExecutable = FileManager.default.isExecutableFile(atPath: venvPython) ? venvPython : "python3"
            process.environment = [
                "PYTHONPATH": projectRoot,
                "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            ]
            process.arguments = [
                pythonExecutable, "-m", "atom_locator.cli",
                imagePath,
                "--output-root", URL(fileURLWithPath: projectRoot).appending(path: "experimental_data/results").path,
                "--mode", settings.mode,
                "--sigma-min", settings.sigmaMin,
                "--sigma-max", settings.sigmaMax,
                "--num-sigma", settings.numSigma,
                "--threshold-rel", settings.thresholdRel,
                "--min-distance", settings.minDistance,
                "--background-sigma", settings.backgroundSigma,
                "--refine-method", settings.refineMethod,
                "--refine-window", settings.refineWindow,
                "--neighbors-k", settings.neighborsK
            ]

            let output = Pipe()
            let errorOutput = Pipe()
            process.standardOutput = output
            process.standardError = errorOutput
            try process.run()
            process.waitUntilExit()

            let stdout = String(data: output.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let stderr = String(data: errorOutput.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            guard process.terminationStatus == 0 else {
                throw RunnerError.processFailed(stderr.isEmpty ? stdout : stderr)
            }
            guard let line = stdout.split(separator: "\n").last else {
                throw RunnerError.processFailed("Python CLI did not return JSON.")
            }
            let data = Data(String(line).utf8)
            return .success(try JSONDecoder().decode(RunSummary.self, from: data))
        } catch {
            return .failure(error)
        }
    }
}

enum RunnerError: LocalizedError {
    case processFailed(String)

    var errorDescription: String? {
        switch self {
        case .processFailed(let message):
            return message
        }
    }
}
