// render_frames.swift: ui-motion template for verifying a SwiftUI port against its seek(t) page.
// Copy it into a tools/ folder as main.swift (top-level code is only allowed in main.swift),
// replace `makeView(t:reduced:)` with the view under test (a pure function of t), then:
//   xcrun -sdk macosx swiftc -O -swift-version 5 -target arm64-apple-macos15.0 \
//       MotionSpring.swift YourView.swift tools/main.swift -o render_frames
//   ./render_frames out/swiftui 0.3 0.9 1.2 [--reduced]      # times as separate arguments
// and compare with: python scripts/contact_sheet.py <project> --times 0.3,0.9,1.2
import SwiftUI
import AppKit

@MainActor func makeView(t: Double, reduced: Bool) -> some View {
    Text(String(format: "replace makeView: t=%.2f", t)).frame(width: 390, height: 844)   // ← your view here
}

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: render_frames <outdir> <t> [t ...] [--reduced]"); exit(2) }
let outDir = URL(fileURLWithPath: args[1])
let reduced = args.contains("--reduced")
let times = args.dropFirst(2).compactMap { Double($0) }   // pass times as separate arguments
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

MainActor.assumeIsolated {
    for t in times {
        let renderer = ImageRenderer(content: makeView(t: t, reduced: reduced).environment(\.colorScheme, .light))
        renderer.scale = 1
        guard let cg = renderer.cgImage else { print("render failed at \(t)"); exit(1) }
        let url = outDir.appendingPathComponent(String(format: "swiftui-t%.3f.png", t))
        try! NSBitmapImageRep(cgImage: cg).representation(using: .png, properties: [:])!.write(to: url)
        print(url.path)
    }
}
