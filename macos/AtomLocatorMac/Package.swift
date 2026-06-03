// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "AtomLocatorMac",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "AtomLocatorMac", targets: ["AtomLocatorMac"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(name: "AtomLocatorMac")
    ]
)
