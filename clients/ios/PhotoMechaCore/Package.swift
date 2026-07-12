// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PhotoMechaCore",
    platforms: [
        .iOS(.v16),
        .macOS(.v13),
    ],
    products: [
        .library(name: "PhotoMechaCore", targets: ["PhotoMechaCore"]),
    ],
    targets: [
        .target(name: "PhotoMechaCore"),
        .testTarget(
            name: "PhotoMechaCoreTests",
            dependencies: ["PhotoMechaCore"]
        ),
    ]
)
